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
    # Callers now supply true degrees (deg) from the unnormalized adjacency; fallback to Ahat row sums
    # is retained only for legacy invocation paths (should be phased out).
    coh_norm: np.ndarray | None = None
    if len(w) > 0:
        # Exact per-node Laplacian energy attribution: Tr(Q^T L Q) = Σ_i Q_i · (L Q)_i
        # This guarantees conservation when differences between two solutions are taken.
        LQ = L @ Q  # sparse matmul
        coh_norm = np.einsum("ij,ij->i", Q, LQ)

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
