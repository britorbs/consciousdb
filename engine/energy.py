from __future__ import annotations
import numpy as np
from scipy import sparse

def normalized_laplacian(A: np.ndarray | sparse.csr_matrix) -> sparse.csr_matrix:
    if not isinstance(A, sparse.csr_matrix):
        A = sparse.csr_matrix(A)
    d = np.asarray(A.sum(axis=1)).ravel()
    with np.errstate(divide='ignore'):
        dinv_sqrt = 1.0 / np.sqrt(np.maximum(d, 1e-12))
    Dinv = sparse.diags(dinv_sqrt)
    Lsym = sparse.eye(A.shape[0], format="csr") - (Dinv @ A @ Dinv).tocsr()
    return Lsym

def per_node_components(Q: np.ndarray, X: np.ndarray, L: sparse.csr_matrix, b: np.ndarray, y: np.ndarray,
                        lambda_g: float, lambda_c: float, lambda_q: float):
    """Compute per-node energy components (coherence, anchor, ground) with vectorized coherence.

    Coherence semantics preserved from original implementation:
    For each *directed* edge (i -> j) with weight w_ij (from Ahat = I - L = normalized adjacency),
    we add 0.5 * w_ij * ||Qi - Qj||^2 to node i and 0.25 * w_ij * ||Qi - Qj||^2 to node j.
    This matches the previous loop-based behavior exactly (including asymmetric cases).
    """
    N, d = Q.shape
    I = sparse.eye(L.shape[0], format="csr")
    Ahat = (I - L).tocsr()

    # Extract directed edges
    indptr = Ahat.indptr
    indices = Ahat.indices
    data = Ahat.data
    # Build row index array matching indices
    row_counts = np.diff(indptr)
    rows = np.repeat(np.arange(N), row_counts)
    cols = indices
    w = data
    coh = np.zeros(N, dtype=np.float64)
    if len(w) > 0:
        # Compute squared distances for all directed edges
        diffs = Q[rows] - Q[cols]
        dist2 = np.einsum('ij,ij->i', diffs, diffs)
        contrib_src = 0.5 * w * dist2
        contrib_dst = 0.25 * w * dist2
        # Accumulate using np.add.at for potential repeated indices
        np.add.at(coh, rows, contrib_src)
        np.add.at(coh, cols, contrib_dst)
    # Anchor (query) term – only where b has entries
    anc = np.sum((Q - y[None, :])**2, axis=1) * (b[:N] if b.shape[0] >= N else 0.0)
    # Ground (distance to original X)
    grd = np.sum((Q - X)**2, axis=1)
    return lambda_c * coh, lambda_q * anc, lambda_g * grd
