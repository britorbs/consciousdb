from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from adaptive.manager import (
    STATE as ADAPTIVE_STATE,
)
from adaptive.manager import (
    bandit_record_reward,
    bandit_select,
    cache_query,
    get_suggested_alpha,
    lookup_query,
    record_feedback,
)
from adaptive.manager import (
    load_state as adaptive_load_state,
)
from adaptive.manager import (
    save_state as adaptive_save_state,
)
from api.schemas import (
    Diagnostics,
    EnergyTerms,
    FeedbackRequest,
    Item,
    Neighbor,
    QueryRequest,
    QueryResponse,
)

# Connectors & embedders
from connectors.registry import get_connector
from embedders.registry import get_embedder
from engine.energy import normalized_laplacian, per_node_components
from engine.rank import zscore

# Engine
from engine.solve import solve_block_cg
from graph.build import knn_adjacency
from infra.logging import setup_logging
from infra.metrics import (
    ADAPTIVE_STATE_LOAD_FAILURE,
    ADAPTIVE_STATE_SAVE_FAILURE,
    BANDIT_ARM_SELECT,
    COHERENCE_MODE_COUNT,
    FALLBACK_REASON,
    observe_adaptive_feedback,
    observe_bandit_snapshot,
    observe_query,
)
from infra.settings import Settings

_BASE_LOG = setup_logging()


class RequestLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):  # noqa: D401
        extra = kwargs.get("extra") or {}
        if "request_id" not in extra and hasattr(self, "request_id"):
            extra["request_id"] = getattr(self, "request_id")
        kwargs["extra"] = extra
        return msg, kwargs


LOG = _BASE_LOG  # default (startup etc.)


def _load_settings():
    return Settings()


SET = _load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation (migrated from deprecated on_event)
    try:
        embedder = get_embedder(SET.embedder)
        probe = embedder.embed_query("health probe")
        dim = int(probe.shape[0])
    except Exception as e:  # pragma: no cover
        LOG.error("embedder_probe_failure", extra={"error": str(e)})
        raise
    expected = SET.expected_dim
    mismatch = expected is not None and expected != dim
    summary = {
        "connector": SET.connector,
        "embedder": SET.embedder,
        "embed_dim": dim,
        "expected_dim": expected,
        "knn_k": SET.knn_k,
        "knn_mutual": SET.knn_mutual,
    }
    if mismatch:
        if SET.fail_on_dim_mismatch:
            LOG.error("startup_dim_mismatch", extra=summary)
            raise RuntimeError(f"Embedding dimension mismatch (expected={expected}, got={dim})")
        else:
            LOG.warning("startup_dim_mismatch_warn", extra=summary)
    else:
        LOG.info("startup_ok", extra=summary)
    app.state.embed_dim = dim
    app.state.expected_dim = expected
    # Adaptive persistence load (best-effort)
    if SET.enable_adaptive:
        try:  # pragma: no cover
            adaptive_load_state(SET.adaptive_state_path)
            # Propagate bandit enable flag into state
            ADAPTIVE_STATE.bandit_enabled = SET.enable_bandit
            LOG.info(
                "adaptive_state_loaded",
                extra={
                    "events": len(ADAPTIVE_STATE.events),
                    "suggested_alpha": ADAPTIVE_STATE.suggested_alpha,
                },
            )
        except Exception as e:  # pragma: no cover
            ADAPTIVE_STATE_LOAD_FAILURE.inc()
            LOG.warning("adaptive_state_load_failed", extra={"error": str(e)})
    yield
    # (Optional) future teardown logic here
    # Persist adaptive state on shutdown (best-effort)
    if SET.enable_adaptive:
        try:  # pragma: no cover
            adaptive_save_state(SET.adaptive_state_path)
            LOG.info("adaptive_state_saved", extra={"events": len(ADAPTIVE_STATE.events)})
        except Exception as e:  # pragma: no cover
            ADAPTIVE_STATE_SAVE_FAILURE.inc()
            LOG.warning("adaptive_state_save_failed", extra={"error": str(e)})


app = FastAPI(title="ConsciousDB Sidecar", version="v2.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = rid
    adapter = RequestLoggerAdapter(_BASE_LOG, {"request_id": rid})
    request.state.log = adapter
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    # If no keys configured, auth is disabled
    raw_keys = SET.api_keys.split(",") if SET.api_keys else []
    keys = [k.strip() for k in raw_keys if k.strip()]
    if keys:
        header_name = SET.api_key_header.lower()
        provided = request.headers.get(header_name)
        if not provided or all(not _constant_time_equals(provided, k) for k in keys):
            # Avoid leaking which part failed; log event
            _BASE_LOG.warning("auth_failed", extra={"path": request.url.path})
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


def _constant_time_equals(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    res = 0
    for x, y in zip(a.encode(), b.encode()):
        res |= x ^ y
    return res == 0


## startup validation moved to lifespan


@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "version": app.version,
        "mock": SET.use_mock,
        "connector": SET.connector,
        "embedder": SET.embedder,
        "embed_dim": getattr(app.state, "embed_dim", None),
        "expected_dim": getattr(app.state, "expected_dim", None),
    }


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    t_start = time.perf_counter()
    rlog = getattr(req, "log", LOG)
    # Predeclare qid for later reassignment to avoid UnboundLocalError
    qid = None

    # Embedding
    embed_t0 = time.perf_counter()
    embedder = get_embedder(SET.embedder)
    y = embedder.embed_query(req.query)  # np.ndarray (d,)
    embed_ms = (time.perf_counter() - embed_t0) * 1000.0

    # ANN recall
    ann_t0 = time.perf_counter()
    connector = get_connector(SET.connector, settings=SET)
    hits = connector.top_m(y, req.m)  # List[(id, sim, maybe_vec)]
    if not hits:
        raise HTTPException(status_code=400, detail="No ANN results.")
    ids = [h[0] for h in hits]
    sims = np.array([float(h[1]) for h in hits], dtype=np.float32)
    # If vectors not returned, fetch them
    if len(hits[0]) >= 3 and hits[0][2] is not None:
        X_S = np.stack([h[2] for h in hits]).astype(np.float32)
    else:
        X_S = connector.fetch_vectors(ids).astype(np.float32)
    ann_ms = (time.perf_counter() - ann_t0) * 1000.0

    # Easy-query gate (vector-only if high gap) unless force_fallback explicitly requests full pipeline
    sorted_sims = np.sort(sims)[::-1]
    gap = float(sorted_sims[0] - sorted_sims[min(9, len(sorted_sims) - 1)])
    if (
        gap > req.overrides.similarity_gap_margin
        and not req.overrides.force_fallback  # allow tests / callers to force full path
    ):
        rlog.info("easy_query_gate", extra={"gap": gap})
        qid = str(uuid.uuid4()) if SET.enable_adaptive else None
        applied_alpha = None
        alpha_source = None
        suggested = get_suggested_alpha() if SET.enable_adaptive else None
        # Bandit selection (diagnostic only in easy path; no ranking effect here)
        bandit_alpha = None
        if SET.enable_bandit and SET.enable_adaptive:
            ADAPTIVE_STATE.bandit_enabled = True
            if qid is not None:
                bandit_alpha = bandit_select(qid)  # may be None first few queries if not enabled
            if bandit_alpha is not None:
                BANDIT_ARM_SELECT.labels(alpha=str(bandit_alpha)).inc()
                observe_bandit_snapshot(ADAPTIVE_STATE.bandit_arms)
        if SET.enable_adaptive and SET.enable_adaptive_apply and suggested is not None:
            # Apply suggestion in easy gate only for diagnostic surface (no ranking effect here)
            applied_alpha = suggested
            alpha_source = "suggested"
        elif bandit_alpha is not None and SET.enable_bandit:
            applied_alpha = bandit_alpha
            alpha_source = "bandit"
        items = []
        for i, (id_) in enumerate(ids[: req.k]):
            items.append(
                Item(
                    id=id_,
                    score=float(sims[i]),
                    align=float(sims[i]),
                    baseline_align=float(sims[i]),
                    uplift=0.0,
                    activation=0.0,
                    neighbors=[] if req.receipt_detail == 1 else [],
                    energy_terms=EnergyTerms(
                        coherence_drop=0.0 if req.receipt_detail == 1 else 0.0,
                        anchor_drop=0.0 if req.receipt_detail == 1 else 0.0,
                        ground_penalty=0.0 if req.receipt_detail == 1 else 0.0,
                    ),
                    excerpt=None,
                )
            )
        timings = {"embed": embed_ms, "ann": ann_ms, "build": 0.0, "solve": 0.0, "rank": 1.0}
        resp = QueryResponse(
            items=items,
            diagnostics=Diagnostics(
                similarity_gap=gap,
                coh_drop_total=0.0,
                deltaH_total=0.0,
                # Normalization diagnostics (easy path: zeroed)
                coherence_mode="normalized" if SET.use_normalized_coh else "legacy",
                deltaH_trace=0.0,
                deltaH_rel_diff=None,
                kappa_bound=None,
                suggested_alpha=suggested,
                applied_alpha=applied_alpha,
                alpha_source=alpha_source,
                used_deltaH=False,
                used_expand_1hop=False,
                cg_iters=0,
                residual=0.0,
                fallback=False,
                timings_ms=timings | {"total": sum(timings.values())},
                receipt_version=1,
            ),
            query_id=qid,
            version=app.version,
        )
        # Metrics for easy gate path
        try:
            observe_query(
                latency_ms=sum(timings.values()),
                graph_ms=0.0,
                solve_ms=0.0,
                rank_ms=timings["rank"],
                iterations=[],
                redundancy=0.0,
                mmr_used=False,
                fallback=False,
                easy_gate=True,
                coh_gate=False,
                max_residual=0.0,
                delta_h_total=0.0,
                low_impact_gate=False,
                neighbors_present=False,
            )
        except Exception:  # pragma: no cover
            pass
        if SET.enable_audit_log:
            try:  # pragma: no cover
                audit_evt = {
                    "ts": time.time(),
                    "query": req.query,
                    "k": req.k,
                    "m": req.m,
                    "deltaH_total": 0.0,
                    "fallback": False,
                    "fallback_reason": None,
                    "receipt_version": 1,
                    "easy_gate": True,
                    "low_impact_gate": False,
                    "iter_max": 0,
                    "residual": 0.0,
                    "redundancy": 0.0,
                    "query_id": qid,
                    "suggested_alpha": resp.diagnostics.suggested_alpha,
                    "items": [
                        {"id": it.id, "score": it.score, "coherence_drop": 0.0, "neighbors": []} for it in resp.items
                    ],
                }
                # Optional HMAC signing
                if SET.audit_hmac_key:
                    body = json.dumps(audit_evt, sort_keys=True).encode("utf-8")
                    sig = hmac.new(SET.audit_hmac_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
                    audit_evt["signature"] = sig
                # Rotate audit.log if >5MB
                try:
                    if os.path.exists("audit.log") and os.path.getsize("audit.log") > 5 * 1024 * 1024:
                        try:
                            os.replace("audit.log", "audit.log.1")
                        except Exception:
                            pass
                except Exception:
                    pass
                with open("audit.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps(audit_evt) + "\n")
            except Exception as e:
                LOG.warning("audit_log_write_failed", extra={"error": str(e)})
        # Fallback reason metrics (easy gate always non-fallback, reason none)
        try:  # pragma: no cover
            FALLBACK_REASON.labels(reason="none").inc()
        except Exception:
            pass
        return resp

    # (Removed settings refresh to preserve runtime test overrides on SET)
    # Build kNN adjacency over recalled vectors
    build_t0 = time.perf_counter()
    N, d = X_S.shape
    A_S = knn_adjacency(X_S, k=SET.knn_k, mutual=SET.knn_mutual)
    # Raw (unnormalized) degrees for true degree-normalized coherence attribution
    deg_full = np.asarray(A_S.sum(axis=1)).ravel().astype(np.float64)
    # Conditional 1-hop expansion for context
    used_expand = False
    S_idx = np.arange(N, dtype=int)
    if gap < req.overrides.expand_when_gap_below and N >= 400:
        used_expand = True
        # Mock expand: add a few neighbors (here trivially add ends); in production, use a persisted kNN adjacency.
        S_ctx = np.arange(min(int(1.5 * N), N), dtype=int)
    else:
        S_ctx = S_idx
    # Restrict vectors to context
    X_ctx = X_S[S_ctx]

    # Anchor weights (normalize)
    sims_ctx = sims[S_ctx]
    b = np.maximum(sims_ctx, 0.0).astype(np.float32)
    b = b / (b.sum() + 1e-12)
    build_ms = (time.perf_counter() - build_t0) * 1000.0

    # Solve anchored & baseline
    solve_t0 = time.perf_counter()
    L_ctx = normalized_laplacian(A_S[np.ix_(S_ctx, S_ctx)])
    Q_star, iters_vec, resid = solve_block_cg(
        L=L_ctx,
        B_diag=b,
        X=X_ctx,
        y=y,
        lambda_g=1.0,
        lambda_c=0.5,
        lambda_q=4.0,
        iters_cap=req.overrides.iters_cap,
        residual_tol=req.overrides.residual_tol,
        warm_start=X_ctx,
    )
    Q_base, _, _ = solve_block_cg(
        L=L_ctx,
        B_diag=np.zeros_like(b),
        X=X_ctx,
        y=y,
        lambda_g=1.0,
        lambda_c=0.5,
        lambda_q=0.0,
        iters_cap=req.overrides.iters_cap,
        residual_tol=req.overrides.residual_tol,
        warm_start=X_ctx,
    )
    # Restrict back to S
    pos = {idx: i for i, idx in enumerate(S_ctx)}
    idx_S = np.array([pos[i] for i in S_idx], dtype=int)
    Qs = Q_star[idx_S]
    Qb = Q_base[idx_S]
    # Components on S
    L_S = normalized_laplacian(A_S[np.ix_(S_idx, S_idx)])
    # Feature-flagged normalized coherence attribution
    # For coherent decomposition matching trace identity we evaluate anchor energy at baseline
    # with the same lambda_q used for the optimized solution (even though baseline solve used 0).
    lambda_g = 1.0
    lambda_c = 0.5
    lambda_q = 4.0
    coh_b, anc_b_dummy, grd_b, extra_b = per_node_components(
        Qb,
        X_S,
        L_S,
        np.zeros(N, dtype=np.float32),  # baseline anchor weights effectively 0 in solve
        y,
        lambda_g,
        lambda_c,
        0.0,  # do not scale anchor inside helper; we'll compute separately with lambda_q
        normalized=SET.use_normalized_coh,
        deg=deg_full[idx_S],
    )
    coh_s, anc_s, grd_s, extra_s = per_node_components(
        Qs,
        X_S,
        L_S,
        b[:N],
        y,
        lambda_g,
        lambda_c,
        lambda_q,
        normalized=SET.use_normalized_coh,
        deg=deg_full[idx_S],
    )
    # Recompute baseline anchor energy (with lambda_q) for decomposition:
    diff_b_anchor = Qb - y[None, :]
    anc_b = lambda_q * b[:N] * np.sum(diff_b_anchor * diff_b_anchor, axis=1)
    coh_drop = coh_b - coh_s  # per-node weighted coherence improvement (λ_c scaled)
    anc_drop = anc_b - anc_s  # per-node anchor improvement (λ_q scaled)
    grd_drop = grd_b - grd_s  # per-node ground improvement (λ_g scaled)
    coh_drop_total = float(np.sum(coh_drop))
    coherence_mode = "normalized" if SET.use_normalized_coh else "legacy"
    # Optionally compute reference difference between legacy and normalized totals for diagnostics (Phase 0 collection)
    deltaH_rel_diff = None
    if extra_b.get("coh_norm") is not None and extra_s.get("coh_norm") is not None and not SET.use_normalized_coh:
        # Compare totals if normalized reference available
        legacy_total = coh_drop_total
        norm_total = float(np.sum(extra_b["coh_norm"]) - np.sum(extra_s["coh_norm"]))
        denom = abs(legacy_total) + 1e-12
        deltaH_rel_diff = abs(norm_total - legacy_total) / denom
    elif extra_b.get("coh_legacy") is not None and extra_s.get("coh_legacy") is not None and SET.use_normalized_coh:
        # Symmetric case when normalized is active; compare back to legacy reference
        norm_total = coh_drop_total
        legacy_total = float(np.sum(extra_b["coh_legacy"]) - np.sum(extra_s["coh_legacy"]))
        denom = abs(norm_total) + 1e-12
        deltaH_rel_diff = abs(norm_total - legacy_total) / denom
    solve_ms = (time.perf_counter() - solve_t0) * 1000.0

    # Graph connected components (on S adjacency)
    try:
        # Simple BFS over non-zero edges
        visited = set()
        comp_sizes = []
        for node in range(N):
            if node in visited:
                continue
            stack = [node]
            size = 0
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                size += 1
                row = A_S[cur]
                # neighbors where weight > 0
                neigh_idx = np.where(row > 0)[0]
                for nb in neigh_idx:
                    if nb not in visited:
                        stack.append(int(nb))
            comp_sizes.append(size)
        component_count = len(comp_sizes)
        largest_component_ratio = max(comp_sizes) / N if comp_sizes and N > 0 else None
    except Exception:  # pragma: no cover
        component_count = None
        largest_component_ratio = None

    solver_efficiency = (coh_drop_total / solve_ms) if solve_ms > 1e-9 else None

    # Low-impact gate on coherence drop
    used_deltaH = True
    if coh_drop_total < req.overrides.coh_drop_min:
        used_deltaH = False

    # Fallback logic + reason enumeration
    max_iters_used = int(iters_vec.max()) if iters_vec.size else 0
    reason_parts = []
    if req.overrides.force_fallback:
        reason_parts.append("forced")
    if max_iters_used >= req.overrides.iters_cap:
        reason_parts.append("iters_cap")
    if resid > req.overrides.residual_tol:
        reason_parts.append("residual")
    fallback = len(reason_parts) > 0
    fallback_reason = ",".join(reason_parts) if reason_parts else None

    # Ranking with redundancy + conditional MMR gating
    rank_t0 = time.perf_counter()
    used_mmr = False
    redundancy = 0.0
    # Determine alpha to apply (manual override, adaptive suggestion, future bandit)
    applied_alpha = req.overrides.alpha_deltaH
    alpha_source = "manual"
    suggested = get_suggested_alpha() if SET.enable_adaptive else None
    bandit_alpha = None
    if SET.enable_bandit:
        ADAPTIVE_STATE.bandit_enabled = True
        if qid is None:
            qid = str(uuid.uuid4())
        bandit_alpha = bandit_select(qid)
        if bandit_alpha is not None:
            BANDIT_ARM_SELECT.labels(alpha=str(bandit_alpha)).inc()
            observe_bandit_snapshot(ADAPTIVE_STATE.bandit_arms)
    if SET.enable_adaptive and SET.enable_adaptive_apply and suggested is not None:
        applied_alpha = suggested
        alpha_source = "suggested"
    elif bandit_alpha is not None and SET.enable_bandit:
        applied_alpha = bandit_alpha
        alpha_source = "bandit"

    # Baseline alignment before coherence optimization uplift measurement
    baseline_align_full = sims  # raw similarity as baseline surrogate
    if not used_deltaH or fallback:
        align_smooth = baseline_align_full  # reuse naming
        score_vec = baseline_align_full
        base_order = np.argsort(-score_vec)[: req.k]
    else:
        z = zscore(coh_drop)
        align_smooth = (Qs @ y) / (np.linalg.norm(Qs, axis=1) + 1e-12)
        score_vec = applied_alpha * z + (1.0 - applied_alpha) * align_smooth
        base_order = np.argsort(-score_vec)[: req.k]
    if base_order.size > 1:
        sel = Qs[base_order]
        norms_sel = np.linalg.norm(sel, axis=1, keepdims=True) + 1e-12
        normed_sel = sel / norms_sel
        S = (normed_sel @ normed_sel.T).astype(np.float32)
        n = S.shape[0]
        redundancy = float((S.sum() - n) / (n * (n - 1))) if n > 1 else 0.0
    # Conditional MMR gating
    if req.k > 8 and redundancy > SET.redundancy_threshold and (SET.enable_mmr or req.overrides.use_mmr):
        from engine.rank import mmr as mmr_fn

        mmr_ids = base_order.tolist()
        rel_scores = score_vec[base_order]
        mmr_sel = mmr_fn(mmr_ids, Qs, rel_scores, lambda_mmr=SET.mmr_lambda, k=req.k)
        order = np.array(mmr_sel, dtype=int)
        used_mmr = True
    else:
        order = base_order
    align_out = align_smooth[order]
    score_out = score_vec[order]
    act = np.linalg.norm(Qs - X_S, axis=1)[order]
    rank_ms = (time.perf_counter() - rank_t0) * 1000.0

    # Build neighbor lists (top adjacency weights) for returned items
    items = []
    # Convert adjacency to dense row slices only for selected rows for simplicity (A_S is small ~M)
    # We take the top 5 neighbors by weight excluding self.
    uplifts = []
    for r_idx in order:
        row = A_S[int(r_idx)]
        # row is dense ndarray (since knn_adjacency returns dense); ensure self excluded
        neigh_weights = []
        if row.sum() > 0:
            # Get indices sorted by weight descending
            cand = np.argsort(-row)
            for j in cand:
                if j == r_idx:
                    continue
                w = float(row[j])
                if w <= 0:
                    break
                if req.receipt_detail == 1:
                    neigh_weights.append(Neighbor(id=ids[int(j)], w=w))
                    if len(neigh_weights) >= 5:
                        break
        baseline_align_val = float(baseline_align_full[r_idx])
        uplift_val = float(align_smooth[np.where(order == r_idx)][0] - baseline_align_val)
        uplifts.append(uplift_val)
        if req.receipt_detail == 0:
            neigh_weights = []  # enforce empty neighbors
        items.append(
            Item(
                id=ids[int(r_idx)],
                score=float(score_out[np.where(order == r_idx)][0]),
                align=float(align_out[np.where(order == r_idx)][0]),
                baseline_align=baseline_align_val,
                uplift=uplift_val,
                activation=float(act[np.where(order == r_idx)][0]),
                neighbors=neigh_weights,
                energy_terms=EnergyTerms(
                    coherence_drop=float(coh_drop[r_idx]) if req.receipt_detail == 1 else 0.0,
                    anchor_drop=float(anc_drop[r_idx]) if req.receipt_detail == 1 else 0.0,
                    ground_penalty=float(-(grd_drop[r_idx])) if req.receipt_detail == 1 else 0.0,
                ),
                excerpt=None,
            )
        )

    edge_count = int(np.count_nonzero(A_S))
    avg_degree = float(edge_count / N) if N > 0 else 0.0
    timings = {"embed": embed_ms, "ann": ann_ms, "build": build_ms, "solve": solve_ms, "rank": rank_ms}
    iter_avg = float(iters_vec.mean()) if iters_vec.size else 0.0
    iter_min = int(iters_vec.min()) if iters_vec.size else 0
    iter_max = int(iters_vec.max()) if iters_vec.size else 0
    iter_med = float(np.median(iters_vec)) if iters_vec.size else 0.0
    # SLO guard warnings (non-fatal)
    if iter_max > 12:
        rlog.warning("slo_iter_guard", extra={"iter_max": iter_max, "cap": req.overrides.iters_cap})
    if resid > 2 * req.overrides.residual_tol:
        rlog.warning(
            "slo_residual_guard",
            extra={"residual": float(resid), "tol": req.overrides.residual_tol},
        )

    qid = qid or (str(uuid.uuid4()) if SET.enable_adaptive else None)
    if SET.enable_adaptive:
        if qid is not None:
            cache_query(qid, coh_drop_total, redundancy)
    uplift_avg = float(np.mean(uplifts)) if uplifts else None
    # Exact ΔH trace identity:
    # ΔH = H(Q_base) - H(Q_star) = λ_g(||Qb-X||^2_F - ||Qs-X||^2_F) + λ_c(Tr(Qb^T L Qb) - Tr(Qs^T L Qs))
    #       + λ_q(Σ b_i ||Qb_i - y||^2 - Σ b_i ||Qs_i - y||^2)
    # Top-k conservation identity: sum over returned items of (coh + anchor + ground improvements)
    try:
        deltaH_trace = float(np.sum(coh_drop[order] + anc_drop[order] + grd_drop[order]))
        if deltaH_trace < -1e-8:
            deltaH_trace = coh_drop_total
    except Exception:
        deltaH_trace = coh_drop_total
    # κ(M) bound estimation: M = λ_g I + λ_c L + λ_q B ; λ_min ≥ λ_g (PSD terms added)
    try:
        # Power iteration to estimate largest eigenvalue of (λ_g I + λ_c L + λ_q diag(b))
        L_mat = L_S  # normalized Laplacian over S
        diag_b = b[:N]

        def mv(v: np.ndarray) -> np.ndarray:
            out = lambda_g * v + lambda_c * (L_mat @ v) + lambda_q * (diag_b * v)
            return np.asarray(out, dtype=v.dtype)

        v = np.random.default_rng().standard_normal(N)
        v /= np.linalg.norm(v) + 1e-12
        lam_max = lambda_g
        for _ in range(3):  # few iters sufficient for loose bound
            wv = mv(v)
            nrm = np.linalg.norm(wv) + 1e-12
            v = wv / nrm
            lam_max = float(np.dot(v, mv(v)) / (np.dot(v, v) + 1e-12))
        lam_min = lambda_g  # conservative lower bound
        kappa_bound = float(lam_max / max(lam_min, 1e-12))
    except Exception:
        kappa_bound = None
    # Coherence fraction relative to trace (if available) or deltaH_total
    coherence_fraction = None
    if coh_drop_total > 1e-9:
        denom = deltaH_trace if (deltaH_trace is not None and deltaH_trace > 1e-9) else coh_drop_total
        coherence_fraction = float(min(1.0, max(0.0, coh_drop_total / (denom + 1e-12))))
    resp = QueryResponse(
        items=items,
        diagnostics=Diagnostics(
            similarity_gap=gap,
            coh_drop_total=coh_drop_total,
            deltaH_total=coh_drop_total,
            coherence_mode=coherence_mode,
            deltaH_rel_diff=deltaH_rel_diff,
            deltaH_trace=deltaH_trace,
            kappa_bound=kappa_bound,
            coherence_fraction=coherence_fraction,
            component_count=component_count,
            largest_component_ratio=largest_component_ratio,
            solver_efficiency=solver_efficiency,
            uplift_avg=uplift_avg,
            suggested_alpha=suggested,
            applied_alpha=applied_alpha,
            alpha_source=alpha_source,
            used_deltaH=used_deltaH,
            used_expand_1hop=used_expand,
            cg_iters=int(iter_max),
            residual=float(resid),
            fallback=fallback,
            timings_ms=timings | {"total": sum(timings.values())},
            edge_count=edge_count,
            avg_degree=avg_degree,
            iter_avg=iter_avg,
            iter_min=iter_min,
            iter_max=iter_max,
            iter_med=iter_med,
            redundancy=redundancy,
            used_mmr=used_mmr,
            weights_mode="cos+",
            fallback_reason=fallback_reason,
            receipt_version=1,
        ),
        query_id=qid,
        version=app.version,
    )
    total_ms = (time.perf_counter() - t_start) * 1000.0
    # Metrics observation (best-effort; protect against failures)
    try:  # pragma: no cover - defensive
        observe_query(
            latency_ms=total_ms,
            graph_ms=build_ms,
            solve_ms=solve_ms,
            rank_ms=rank_ms,
            iterations=[int(x) for x in iters_vec.tolist()],
            redundancy=redundancy,
            mmr_used=used_mmr,
            fallback=fallback,
            easy_gate=False,
            coh_gate=not used_deltaH,
            max_residual=float(resid),
            delta_h_total=coh_drop_total,
            low_impact_gate=not used_deltaH,
            neighbors_present=any(len(it.neighbors) > 0 for it in items),
        )
        COHERENCE_MODE_COUNT.labels(mode=coherence_mode).inc()
    except Exception as e:  # pragma: no cover
        LOG.warning("metrics_observe_failed", extra={"error": str(e)})
    rlog.info(
        "query_done",
        extra={
            "total_ms": round(total_ms, 3),
            "embed_ms": round(embed_ms, 3),
            "ann_ms": round(ann_ms, 3),
            "build_ms": round(build_ms, 3),
            "solve_ms": round(solve_ms, 3),
            "rank_ms": round(rank_ms, 3),
            "gap": round(gap, 4),
            "coh_drop_total": round(coh_drop_total, 6),
            "fallback": fallback,
            "used_deltaH": used_deltaH,
            "iter_max": iter_max,
            "residual": round(float(resid), 6),
            "edge_count": edge_count,
            "avg_degree": round(avg_degree, 3),
            "redundancy": round(float(redundancy), 4),
            "used_mmr": used_mmr,
            "fallback_reason": fallback_reason,
        },
    )
    # Audit log (feature-flagged)
    if SET.enable_audit_log:
        try:  # pragma: no cover (best-effort)
            audit_evt = {
                "ts": time.time(),
                "query": req.query,
                "k": req.k,
                "m": req.m,
                "deltaH_total": coh_drop_total,
                "fallback": fallback,
                "fallback_reason": fallback_reason,
                "receipt_version": 1,
                "easy_gate": False,
                "low_impact_gate": not used_deltaH,
                "iter_max": iter_max,
                "residual": float(resid),
                "redundancy": redundancy,
                "query_id": qid,
                "suggested_alpha": resp.diagnostics.suggested_alpha,
                "items": [
                    {
                        "id": it.id,
                        "score": it.score,
                        "coherence_drop": it.energy_terms.coherence_drop,
                        "neighbors": [n.id for n in it.neighbors],
                    }
                    for it in resp.items
                ],
            }
            if SET.audit_hmac_key:
                body = json.dumps(audit_evt, sort_keys=True).encode("utf-8")
                sig = hmac.new(SET.audit_hmac_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
                audit_evt["signature"] = sig
            # Rotate audit.log if >5MB
            try:
                if os.path.exists("audit.log") and os.path.getsize("audit.log") > 5 * 1024 * 1024:
                    try:
                        os.replace("audit.log", "audit.log.1")
                    except Exception:
                        pass
            except Exception:
                pass
            with open("audit.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_evt) + "\n")
        except Exception as e:  # pragma: no cover
            LOG.warning("audit_log_write_failed", extra={"error": str(e)})
    # Fallback reason metrics (explicit reason label(s))
    try:  # pragma: no cover
        reason_label = fallback_reason if fallback_reason else "none"
        FALLBACK_REASON.labels(reason=reason_label).inc()
    except Exception:
        pass
    return resp


@app.get("/metrics")
def metrics():  # pragma: no cover - simple exposition
    data = generate_latest()  # default registry
    return JSONResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    # Append to a local log; replace with durable eventing in managed service
    evt = req.model_dump()
    evt["ts"] = time.time()
    try:
        # Rotate feedback.log if >5MB
        try:
            if os.path.exists("feedback.log") and os.path.getsize("feedback.log") > 5 * 1024 * 1024:
                try:
                    os.replace("feedback.log", "feedback.log.1")
                except Exception:
                    pass
        except Exception:
            pass
        with open("feedback.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(evt) + "\n")
    except Exception as e:
        LOG.warning("feedback log error: %s", e)
    # Adaptive integration using cached query diagnostics
    if SET.enable_adaptive:
        try:  # pragma: no cover (defensive)
            looked = lookup_query(req.query_id)
            if looked is not None:
                dH, red = looked
            else:
                dH, red = 0.05, 0.3  # fallback defaults
            clicked = len(req.clicked_ids)
            record_feedback(deltaH_total=dH, redundancy=red, clicked=clicked, accepted=bool(req.accepted_id))
            observe_adaptive_feedback(
                positive=bool(req.accepted_id or clicked > 0),
                buffer_size=len(ADAPTIVE_STATE.events),
                suggested_alpha=get_suggested_alpha(),
            )
            # Bandit reward: treat acceptance or any click as reward=1 else 0
            if SET.enable_bandit:
                reward = 1.0 if (req.accepted_id or clicked > 0) else 0.0
                bandit_record_reward(req.query_id, reward)
                observe_bandit_snapshot(ADAPTIVE_STATE.bandit_arms)
            # Persist state after feedback mutation (best-effort)
            try:  # pragma: no cover
                adaptive_save_state(SET.adaptive_state_path)
            except Exception:
                ADAPTIVE_STATE_SAVE_FAILURE.inc()
                pass
        except Exception as e:  # pragma: no cover
            LOG.warning("adaptive_record_failed", extra={"error": str(e)})
    return {"ok": True}
