from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import cg


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
