from __future__ import annotations
import numpy as np
from engine.rank import zscore


def test_zscore_constant_vector():
    x = np.ones(10, dtype=np.float32)
    z = zscore(x)
    assert np.allclose(z, 0.0), "Z-score of constant vector should be zeros"


def test_zscore_non_constant():
    x = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    z = zscore(x)
    # mean = 2, std = ~0.816; z should sum to ~0 and not be all zeros
    assert not np.allclose(z, 0.0)
    assert abs(float(np.mean(z))) < 1e-6
