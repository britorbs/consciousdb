import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
from engine.solve import solve_block_cg
from engine.energy import normalized_laplacian

def test_dense_vs_cg():
    N, d = 10, 3
    A = sparse.diags([1]*(N-1), 1) + sparse.diags([1]*(N-1), -1)
    L = normalized_laplacian(A)
    X = np.random.randn(N, d).astype(np.float32)
    y = np.random.randn(d).astype(np.float32)
    b = np.abs(np.random.rand(N).astype(np.float32))

    lam_g, lam_c, lam_q = 1.0, 0.5, 2.0
    M = lam_g*sparse.eye(N) + lam_c*L + lam_q*sparse.diags(b)
    RHS = lam_g*X + lam_q*(b[:,None]*y[None,:])
    Q_dense = np.stack([spsolve(M, RHS[:,k]) for k in range(d)], axis=1)
    Q_cg, iters, resid = solve_block_cg(L, b, X, y, lam_g, lam_c, lam_q, iters_cap=200, residual_tol=1e-10)
    assert np.allclose(Q_dense, Q_cg, rtol=1e-6, atol=1e-6)
