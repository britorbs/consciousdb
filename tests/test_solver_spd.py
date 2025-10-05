import numpy as np
from scipy import sparse

from engine.energy import normalized_laplacian
from engine.solve import jacobi_precond_diag


def test_spd_diag():
    A = sparse.csr_matrix([[0,1,0],[1,0,1],[0,1,0]], dtype=float)
    L = normalized_laplacian(A)
    b = np.array([0.1, 0.2, 0.3])
    diag = jacobi_precond_diag(1.0, L, 0.5, b, 4.0)
    assert (diag > 0).all()
