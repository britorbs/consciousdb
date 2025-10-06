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
):
    """Compute per-node energy components using normalized Laplacian attribution only.

    Phase 3 cleanup removed legacy asymmetric attribution. Coherence component per node i is
    λ_c * Q_i · (L Q)_i which yields exact conservation with the quadratic trace identity.
    Returns λ-scaled per-node coherence, anchor, and ground terms plus empty extras dict for
    backward compatibility with previous signature.
    """
    N, _ = Q.shape
    # Coherence attribution: Tr(Q^T L Q) = Σ_i Q_i · (L Q)_i
    if Q.size == 0:
        coh = np.zeros(0, dtype=np.float64)
    else:
        LQ = L @ Q
        coh = np.einsum("ij,ij->i", Q, LQ)
    anc = np.sum((Q - y[None, :]) ** 2, axis=1) * (b[:N] if b.shape[0] >= N else 0.0)
    grd = np.sum((Q - X) ** 2, axis=1)
    return lambda_c * coh, lambda_q * anc, lambda_g * grd, {}
