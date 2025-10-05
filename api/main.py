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
SET = Settings()

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
            raise RuntimeError(
                f"Embedding dimension mismatch (expected={expected}, got={dim})"
            )
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
    rlog = getattr(req, 'log', LOG)
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
    gap = float(sorted_sims[0] - sorted_sims[min(9, len(sorted_sims)-1)])
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
        for i, (id_) in enumerate(ids[:req.k]):
            items.append(Item(
                id=id_,
                score=float(sims[i]),
                align=float(sims[i]),
                activation=0.0,
                neighbors=[],
                energy_terms=EnergyTerms(
                    coherence_drop=0.0,
                    anchor_drop=0.0,
                    ground_penalty=0.0
                ),
                excerpt=None
            ))
        timings = {"embed": embed_ms, "ann": ann_ms, "build": 0.0, "solve": 0.0, "rank": 1.0}
        resp = QueryResponse(
            items=items,
            diagnostics=Diagnostics(
                similarity_gap=gap,
                coh_drop_total=0.0,
                deltaH_total=0.0,
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
                        {
                            "id": it.id,
                            "score": it.score,
                            "coherence_drop": 0.0,
                            "neighbors": []
                        } for it in resp.items
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

    # Build kNN adjacency over recalled vectors
    build_t0 = time.perf_counter()
    N, d = X_S.shape
    A_S = knn_adjacency(X_S, k=SET.knn_k, mutual=SET.knn_mutual)
    # Conditional 1-hop expansion for context
    used_expand = False
    S_idx = np.arange(N, dtype=int)
    if gap < req.overrides.expand_when_gap_below and N >= 400:
        used_expand = True
        # Mock expand: add a few neighbors (here trivially add ends); in production, use a persisted kNN adjacency.
        S_ctx = np.arange(min(int(1.5*N), N), dtype=int)
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
        L=L_ctx, B_diag=b, X=X_ctx, y=y,
        lambda_g=1.0, lambda_c=0.5, lambda_q=4.0,
        iters_cap=req.overrides.iters_cap, residual_tol=req.overrides.residual_tol, warm_start=X_ctx
    )
    Q_base, _, _ = solve_block_cg(
        L=L_ctx, B_diag=np.zeros_like(b), X=X_ctx, y=y,
        lambda_g=1.0, lambda_c=0.5, lambda_q=0.0,
        iters_cap=req.overrides.iters_cap, residual_tol=req.overrides.residual_tol, warm_start=X_ctx
    )
    # Restrict back to S
    pos = {idx: i for i, idx in enumerate(S_ctx)}
    idx_S = np.array([pos[i] for i in S_idx], dtype=int)
    Qs = Q_star[idx_S]
    Qb = Q_base[idx_S]
    # Components on S
    L_S = normalized_laplacian(A_S[np.ix_(S_idx, S_idx)])
    coh_b, anc_b, grd_b = per_node_components(Qb, X_S, L_S, np.zeros(N, dtype=np.float32), y, 1.0, 0.5, 0.0)
    coh_s, anc_s, grd_s = per_node_components(Qs, X_S, L_S, b[:N], y, 1.0, 0.5, 4.0)
    coh_drop = coh_b - coh_s
    coh_drop_total = float(np.sum(coh_drop))
    solve_ms = (time.perf_counter() - solve_t0) * 1000.0

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

    if not used_deltaH or fallback:
        align_smooth = sims  # reuse naming
        score_vec = sims
        base_order = np.argsort(-score_vec)[:req.k]
    else:
        z = zscore(coh_drop)
        align_smooth = (Qs @ y) / (np.linalg.norm(Qs, axis=1) + 1e-12)
        score_vec = applied_alpha * z + (1.0 - applied_alpha) * align_smooth
        base_order = np.argsort(-score_vec)[:req.k]
    if base_order.size > 1:
        sel = Qs[base_order]
        norms_sel = np.linalg.norm(sel, axis=1, keepdims=True) + 1e-12
        normed_sel = sel / norms_sel
        S = (normed_sel @ normed_sel.T).astype(np.float32)
        n = S.shape[0]
        redundancy = float((S.sum() - n) / (n * (n - 1))) if n > 1 else 0.0
    # Conditional MMR gating
    if (
        req.k > 8
        and redundancy > SET.redundancy_threshold
        and (SET.enable_mmr or req.overrides.use_mmr)
    ):
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
                neigh_weights.append(Neighbor(id=ids[int(j)], w=w))
                if len(neigh_weights) >= 5:
                    break
        items.append(Item(
            id=ids[int(r_idx)],
            score=float(score_out[np.where(order==r_idx)][0]),
            align=float(align_out[np.where(order==r_idx)][0]),
            activation=float(act[np.where(order==r_idx)][0]),
            neighbors=neigh_weights,
            energy_terms=EnergyTerms(
                coherence_drop=float(coh_drop[r_idx]),
                anchor_drop=float(0.0 - anc_s[r_idx]),
                ground_penalty=float(-(grd_b[r_idx] - grd_s[r_idx])),
            ),
            excerpt=None
        ))

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
        cache_query(qid, coh_drop_total, redundancy)
    resp = QueryResponse(
        items=items,
        diagnostics=Diagnostics(
            similarity_gap=gap,
            coh_drop_total=coh_drop_total,
            deltaH_total=coh_drop_total,
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
