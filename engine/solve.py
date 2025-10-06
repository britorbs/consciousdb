from __future__ import annotations

import time

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import cg

from engine.energy import normalized_laplacian, per_node_components
from engine.rank import zscore
from graph.build import knn_adjacency


def jacobi_precond_diag(
    lambda_g: float,
    L: sparse.csr_matrix,
    lambda_c: float,
    B_diag: np.ndarray,
    lambda_q: float,
) -> np.ndarray:
    diag_L = L.diagonal()
    return np.asarray(lambda_g + lambda_c * diag_L + lambda_q * B_diag, dtype=np.float64)


def apply_M(
    Q: np.ndarray,
    lambda_g: float,
    L: sparse.csr_matrix,
    lambda_c: float,
    B_diag: np.ndarray,
    lambda_q: float,
) -> np.ndarray:
    out = lambda_g * Q + lambda_c * (L @ Q) + lambda_q * (B_diag[:, None] * Q)
    return np.asarray(out, dtype=Q.dtype)


def solve_block_cg(
    L: sparse.csr_matrix,
    B_diag: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    lambda_g: float,
    lambda_c: float,
    lambda_q: float,
    iters_cap: int = 20,
    residual_tol: float = 1e-3,
    warm_start: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Block CG solve returning per-dimension iteration counts.

    Returns:
        Q: (N,d) solved latent vectors
        iters: (d,) iterations used per dimension
        max_residual: maximum relative residual observed across dimensions
    """
    assert L.shape[0] == X.shape[0] == B_diag.shape[0]
    N, d = X.shape
    rhs_block = lambda_g * X + lambda_q * (B_diag[:, None] * y[None, :])
    Q = np.array(warm_start, copy=True) if warm_start is not None else X.copy()
    M_diag = jacobi_precond_diag(lambda_g, L, lambda_c, B_diag, lambda_q)

    max_residual = 0.0
    iters = np.zeros(d, dtype=int)
    M_inv = sparse.diags(1.0 / np.maximum(M_diag, 1e-12))

    for k in range(d):
        rhs = rhs_block[:, k]
        x0 = Q[:, k]

        def mv(v: np.ndarray) -> np.ndarray:  # matvec closure
            return apply_M(v[:, None], lambda_g, L, lambda_c, B_diag, lambda_q).ravel()

        Aop = sparse.linalg.LinearOperator((N, N), matvec=mv)
        iter_counter = {"n": 0}

        def cb(_):  # callback increments on each iteration
            iter_counter["n"] += 1

        # SciPy <1.11 uses 'tol' and ignores 'rtol'; newer versions warn on 'tol' and prefer 'rtol'.
        # We first try modern signature (rtol, atol); if TypeError, fall back to legacy tol.
        try:
            x, info = cg(
                Aop,
                rhs,
                x0=x0,
                rtol=residual_tol,  # preferred in newer SciPy
                maxiter=iters_cap,
                M=M_inv,
                callback=cb,
                atol=0.0,
            )
        except TypeError:
            x, info = cg(
                Aop,
                rhs,
                x0=x0,
                tol=residual_tol,
                maxiter=iters_cap,
                M=M_inv,
                callback=cb,
            )
        # If converged early, iter_counter["n"] is actual iterations; if not converged (info>0) it is == iters_cap
        used = iter_counter["n"] if info == 0 else iters_cap
        iters[k] = used
        r = Aop.matvec(x) - rhs
        res = float(np.linalg.norm(r) / (np.linalg.norm(rhs) + 1e-12))
        max_residual = max(max_residual, res)
        Q[:, k] = x
    return Q, iters, max_residual


def solve_query(
    query: str,
    k: int,
    m: int,
    connector,
    embedder,
    overrides: dict | None = None,
) -> dict:
    """High-level synchronous query orchestration used by the SDK.

    Stable Public API (3.x): Signature / top-level return keys are stable.
    Internal numerical heuristics may evolve (graph params, weighting) but
    returned keys remain: ``items``, ``diagnostics``, ``timings_ms``.

    Parameters
    ----------
    query : str
        Natural language query text.
    k : int
        Number of ranked results to return.
    m : int
        Candidate pool size to retrieve prior to optimization (m >= k).
    connector : object
        Exposes ``top_m(query_vec, m)`` and ``fetch_vectors(ids)``.
    embedder : object
        Exposes ``embed(text) -> np.ndarray``.
    overrides : dict | None
        Optional parameters (alpha, iters_cap, residual_tol, gating, mmr, etc.).

    Returns
    -------
    dict
        ``{"items": [...], "diagnostics": {...}, "timings_ms": {...}}``
    """
    if k <= 0:
        return {"items": [], "diagnostics": {}, "timings_ms": {}}
    if m < k:
        raise ValueError("m must be >= k")

    # (t0 previously used for potential future total timing; removed to satisfy lint.)
    # Default override parameters (kept intentionally small + stable)
    defaults = {
        "similarity_gap_margin": 0.18,
        "force_fallback": False,
        "iters_cap": 20,
        "residual_tol": 1e-3,
        "coh_drop_min": 1e-6,
        "alpha_deltaH": 0.5,
        "expand_when_gap_below": 0.04,
        "use_mmr": False,
        "mmr_lambda": 0.25,
        "redundancy_threshold": 0.35,
    }
    ov = {**defaults, **(overrides or {})}

    timings: dict[str, float] = {}

    # Embedding
    t_embed = time.perf_counter()
    y = embedder.embed(query)
    timings["embed"] = (time.perf_counter() - t_embed) * 1000.0

    # ANN / candidate retrieval
    t_ann = time.perf_counter()
    hits = connector.top_m(y, m)
    if not hits:
        return {"items": [], "diagnostics": {"error": "no_results"}, "timings_ms": timings}
    ids = [h[0] for h in hits]
    sims = np.array([float(h[1]) for h in hits], dtype=np.float32)
    # Accept embedded vectors if provided; else fetch.
    if len(hits[0]) >= 3 and hits[0][2] is not None:
        X_S = np.stack([h[2] for h in hits]).astype(np.float32)
    else:
        X_S = connector.fetch_vectors(ids).astype(np.float32)
    timings["ann"] = (time.perf_counter() - t_ann) * 1000.0

    # Easy path gate (pure similarity) replicating server logic (simplified)
    sorted_sims = np.sort(sims)[::-1]
    gap_index = min(9, len(sorted_sims) - 1)
    gap = float(sorted_sims[0] - sorted_sims[gap_index]) if gap_index >= 0 else 0.0
    if gap > ov["similarity_gap_margin"] and not ov["force_fallback"]:
        order = np.argsort(-sims)[:k]
        items = []
        for idx in order:
            items.append(
                {
                    "id": ids[int(idx)],
                    "score": float(sims[idx]),
                    "align": float(sims[idx]),
                    "baseline_align": float(sims[idx]),
                    "uplift": 0.0,
                    "activation": 0.0,
                    "energy_terms": {"coherence_drop": 0.0, "anchor_drop": 0.0, "ground_penalty": 0.0},
                    "neighbors": [],
                }
            )
        timings.setdefault("build", 0.0)
        timings.setdefault("solve", 0.0)
        timings.setdefault("rank", 1.0)
        timings["total"] = sum(timings.values())
        return {
            "items": items,
            "diagnostics": {
                "similarity_gap": gap,
                "deltaH_total": 0.0,
                "coh_drop_total": 0.0,
                "fallback": False,
                "used_deltaH": False,
            },
            "timings_ms": timings,
        }

    # Graph construction (dense kNN adjacency) and optional expansion (placeholder simplified)
    t_build = time.perf_counter()
    N, d = X_S.shape
    A_S = knn_adjacency(X_S, k=min(10, max(2, int(np.sqrt(N)+1))), mutual=False)  # modest default
    b = np.maximum(sims, 0.0)
    b = b / (b.sum() + 1e-12)
    timings["build"] = (time.perf_counter() - t_build) * 1000.0

    # Solve anchored & baseline
    t_solve = time.perf_counter()
    L_S = normalized_laplacian(A_S)
    lambda_g = 1.0
    lambda_c = 0.5
    lambda_q = 4.0
    Q_star, iters_vec, resid = solve_block_cg(
        L=L_S,
        B_diag=b,
        X=X_S,
        y=y,
        lambda_g=lambda_g,
        lambda_c=lambda_c,
        lambda_q=lambda_q,
        iters_cap=int(ov["iters_cap"]),
        residual_tol=float(ov["residual_tol"]),
        warm_start=X_S,
    )
    Q_base, _, _ = solve_block_cg(
        L=L_S,
        B_diag=np.zeros_like(b),
        X=X_S,
        y=y,
        lambda_g=lambda_g,
        lambda_c=lambda_c,
        lambda_q=0.0,
        iters_cap=int(ov["iters_cap"]),
        residual_tol=float(ov["residual_tol"]),
        warm_start=X_S,
    )
    timings["solve"] = (time.perf_counter() - t_solve) * 1000.0

    # Energy decomposition
    coh_b, _anc_b_d, grd_b, _ = per_node_components(
        Q_base,
        X_S,
        L_S,
        np.zeros_like(b),
        y,
        lambda_g,
        lambda_c,
        0.0,
    )
    coh_s, anc_s, grd_s, _ = per_node_components(
        Q_star,
        X_S,
        L_S,
        b,
        y,
        lambda_g,
        lambda_c,
        lambda_q,
    )
    diff_b_anchor = Q_base - y[None, :]
    anc_b = lambda_q * b * np.sum(diff_b_anchor * diff_b_anchor, axis=1)
    coh_drop = coh_b - coh_s
    anc_drop = anc_b - anc_s
    grd_drop = grd_b - grd_s
    coh_drop_total = float(np.sum(coh_drop))
    deltaH_total = coh_drop_total  # maintain naming for continuity

    # Gating based on improvement threshold
    used_deltaH = coh_drop_total >= ov["coh_drop_min"]
    fallback = False
    max_iter = int(iters_vec.max()) if iters_vec.size else 0
    if max_iter >= ov["iters_cap"] or resid > ov["residual_tol"] or ov["force_fallback"]:
        fallback = True
        used_deltaH = False

    # Ranking
    t_rank = time.perf_counter()
    baseline_align_full = sims
    if not used_deltaH or fallback:
        score_vec = baseline_align_full
        align_smooth = baseline_align_full
    else:
        z = zscore(coh_drop)
        align_smooth = (Q_star @ y) / (np.linalg.norm(Q_star, axis=1) + 1e-12)
        score_vec = ov["alpha_deltaH"] * z + (1.0 - ov["alpha_deltaH"]) * align_smooth
    base_order = np.argsort(-score_vec)[:k]
    # Redundancy & optional MMR
    redundancy = 0.0
    used_mmr = False
    if base_order.size > 1:
        sel = Q_star[base_order]
        norms_sel = np.linalg.norm(sel, axis=1, keepdims=True) + 1e-12
        normed_sel = sel / norms_sel
        S_sim = (normed_sel @ normed_sel.T).astype(np.float32)
        n = S_sim.shape[0]
        redundancy = float((S_sim.sum() - n) / (n * (n - 1))) if n > 1 else 0.0
    order = base_order
    if (
        ov.get("use_mmr")
        and redundancy > ov["redundancy_threshold"]
        and base_order.size > 1
    ):
        try:
            from engine.rank import mmr as mmr_fn  # late import to avoid unnecessary dependency

            rel_scores = score_vec[base_order]
            mmr_sel = mmr_fn(base_order.tolist(), Q_star, rel_scores, lambda_mmr=ov["mmr_lambda"], k=k)
            order = np.array(mmr_sel, dtype=int)
            used_mmr = True
        except Exception:
            pass  # fall back silently
    timings["rank"] = (time.perf_counter() - t_rank) * 1000.0

    # Build neighbor / item structures
    items_out = []
    for r_idx in order:
        # Top weighted neighbors (dense adjacency row)
        row = A_S[int(r_idx)]
        neigh = []
        if isinstance(row, np.ndarray):
            arr = row
        else:
            try:
                arr = np.asarray(row.todense()).ravel()
            except Exception:
                arr = np.array(row).ravel()
        cand = np.argsort(-arr)
        for j in cand:
            if j == r_idx:
                continue
            w = float(arr[j])
            if w <= 0:
                break
            neigh.append({"id": ids[int(j)], "w": w})
            if len(neigh) >= 5:
                break
        baseline_align_val = float(baseline_align_full[r_idx])
        align_val = float(align_smooth[r_idx])
        uplift_val = align_val - baseline_align_val
        items_out.append(
            {
                "id": ids[int(r_idx)],
                "score": float(score_vec[r_idx]),
                "align": align_val,
                "baseline_align": baseline_align_val,
                "uplift": uplift_val,
                "activation": float(np.linalg.norm(Q_star[r_idx] - X_S[r_idx])),
                "energy_terms": {
                    "coherence_drop": float(coh_drop[r_idx]) if used_deltaH else 0.0,
                    "anchor_drop": float(anc_drop[r_idx]) if used_deltaH else 0.0,
                    "ground_penalty": float(-grd_drop[r_idx]) if used_deltaH else 0.0,
                },
                "neighbors": neigh,
            }
        )

    timings["total"] = sum(timings.values())
    diagnostics = {
        "similarity_gap": gap,
        "coh_drop_total": coh_drop_total,
        "deltaH_total": deltaH_total,
        "fallback": fallback,
        "used_deltaH": used_deltaH,
        "cg_iters": max_iter,
        "residual": float(resid),
        "redundancy": redundancy,
        "used_mmr": used_mmr,
    }
    return {"items": items_out, "diagnostics": diagnostics, "timings_ms": timings}
