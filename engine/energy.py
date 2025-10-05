from __future__ import annotations

import numpy as np
from scipy import sparse


def normalized_laplacian(A: np.ndarray | sparse.csr_matrix) -> sparse.csr_matrix:
    if not isinstance(A, sparse.csr_matrix):
        A = sparse.csr_matrix(A)
    d = np.asarray(A.sum(axis=1)).ravel()
    with np.errstate(divide="ignore"):
        dinv_sqrt = 1.0 / np.sqrt(np.maximum(d, 1e-12))
    Dinv = sparse.diags(dinv_sqrt)
    Lsym = sparse.eye(A.shape[0], format="csr") - (Dinv @ A @ Dinv).tocsr()
    return Lsym


def per_node_components(
    Q: np.ndarray,
    X: np.ndarray,
    L: sparse.csr_matrix,
    b: np.ndarray,
    y: np.ndarray,
    lambda_g: float,
    lambda_c: float,
    lambda_q: float,
    normalized: bool = False,
    deg: np.ndarray | None = None,
):
    """Compute per-node energy components (coherence, anchor, ground).

    Parameters
    ----------
    Q : (N, d) optimized embeddings
    X : (N, d) original embeddings
    L : normalized Laplacian (symmetric)
    b : (N,) anchor indicator / weights
    y : (d,) query embedding
    lambda_g, lambda_c, lambda_q : floats weighting ground, coherence, anchor respectively
    normalized : if True, compute coherence attribution using symmetric edge half-splitting
                 with distances in original (already normalized Laplacian) space; if False use
                 legacy asymmetric 0.5/0.25 directed scheme for backward compatibility.

    Returns
    -------
    coh, anc, grd : per-node weighted components (already multiplied by lambdas)
    extra : dict with optional 'coh_norm' unweighted normalized per-node coherence when normalized=False
            or 'coh_legacy' when normalized=True (to allow dual-path diagnostics up-stack)
    """
    N, dim = Q.shape
    identity_mat = sparse.eye(L.shape[0], format="csr")
    Ahat = (identity_mat - L).tocsr()

    indptr = Ahat.indptr
    indices = Ahat.indices
    data = Ahat.data
    row_counts = np.diff(indptr)
    rows = np.repeat(np.arange(N), row_counts)
    cols = indices
    w = data

    # Legacy asymmetric attribution
    coh_legacy = np.zeros(N, dtype=np.float64)
    if len(w) > 0:
        diffs = Q[rows] - Q[cols]
        dist2 = np.einsum("ij,ij->i", diffs, diffs)
        contrib_src = 0.5 * w * dist2
        contrib_dst = 0.25 * w * dist2
        np.add.at(coh_legacy, rows, contrib_src)
        np.add.at(coh_legacy, cols, contrib_dst)

    # Normalized symmetric attribution (each *undirected* edge contributes 0.5 * w * ||Qi/√di - Qj/√dj||^2 to both ends)
    # Implements degree-normalized differences aligned with L_sym = I - D^{-1/2} A D^{-1/2}.
    # NOTE: We prefer true degrees from the *unnormalized* adjacency A. Since only L (or Ahat) is
    # available here, callers should supply `deg` computed as A.sum(axis=1). If `deg` is None we
    # fall back to using row sums of Ahat (which is mathematically inconsistent but retained as a
    # backward-compatible fallback until all call sites pass real degrees).
    coh_norm: np.ndarray | None = None
    if len(w) > 0:
        # Undirected grouping key
        key_src = rows
        key_dst = cols
        u = np.minimum(key_src, key_dst)
        v = np.maximum(key_src, key_dst)
        undirected_key = u.astype(np.int64) * N + v.astype(np.int64)
        # Degree-normalized embeddings (prefer supplied true degrees)
        if deg is None:
            # Fallback (will be close to 1 for many nodes; not theoretically correct)
            degs_eff = np.asarray(Ahat.sum(axis=1)).ravel() + 1e-12
        else:
            degs_eff = deg.astype(np.float64) + 1e-12
        inv_sqrt_d = 1.0 / np.sqrt(degs_eff)
        Qn = Q * inv_sqrt_d[:, None]
        # If future formulations need original X distances under normalization, compute Xn similarly:
        # Xn = X * inv_sqrt_d[:, None]
        diffs2 = Qn[rows] - Qn[cols]
        dist2 = np.einsum("ij,ij->i", diffs2, diffs2)
        wd = w * dist2
        order = np.argsort(undirected_key)
        uk_sorted = undirected_key[order]
        wd_sorted = wd[order]
        u_sorted = u[order]
        v_sorted = v[order]
        coh_norm_raw = np.zeros(N, dtype=np.float64)
        if len(order) > 0:
            boundary = np.concatenate(([True], uk_sorted[1:] != uk_sorted[:-1]))
            idxs = np.nonzero(boundary)[0]
            ps = np.cumsum(wd_sorted)
            grp_starts = idxs
            grp_ends = np.concatenate((idxs[1:], [len(uk_sorted)]))
            for gs, ge in zip(grp_starts, grp_ends):
                total = ps[ge - 1] - (ps[gs - 1] if gs > 0 else 0.0)
                ui = u_sorted[gs]
                vi = v_sorted[gs]
                half = 0.5 * total
                coh_norm_raw[ui] += half
                if vi != ui:
                    coh_norm_raw[vi] += half
        coh_norm = coh_norm_raw

    anc = np.sum((Q - y[None, :]) ** 2, axis=1) * (b[:N] if b.shape[0] >= N else 0.0)
    grd = np.sum((Q - X) ** 2, axis=1)

    if normalized:
        # Provide legacy for comparison
        extra: dict[str, np.ndarray] = {"coh_legacy": coh_legacy}
        coh_out = coh_norm if coh_norm is not None else np.zeros(N)
    else:
        extra = {"coh_norm": coh_norm} if coh_norm is not None else {}
        coh_out = coh_legacy

    return lambda_c * coh_out, lambda_q * anc, lambda_g * grd, extra
