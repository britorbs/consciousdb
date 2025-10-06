from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def induce_subgraph(A: NDArray[np.float32], idx: np.ndarray) -> NDArray[np.float32]:
    sub = A[np.ix_(idx, idx)]
    return np.asarray(sub, dtype=np.float32)


def one_hop_expand(A: NDArray[np.float32], S: np.ndarray, cap: int | None = None) -> np.ndarray:
    mask = np.zeros(A.shape[0], dtype=bool)
    mask[S] = True
    for i in S:
        nbrs = np.where(A[i] > 0)[0]
        mask[nbrs] = True
    idx = np.flatnonzero(mask)
    if cap is not None and len(idx) > cap:
        idx = np.concatenate([S, idx[~np.isin(idx, S)][: max(0, cap - len(S))]])
    return idx


def knn_adjacency(X: NDArray[np.float32], k: int, mutual: bool = True) -> NDArray[np.float32]:
    """Build a cosine kNN adjacency matrix.

    Returns a dense (N,N) float32 adjacency with non-negative weights.
    For now we keep it dense for simplicity; future optimization can
    switch to sparse if N grows. When mutual=True we retain only edges
    where i appears in j's top-k and j appears in i's top-k (symmetrized
    by intersection). Diagonal is zero.
    """
    N, d = X.shape
    if N == 0:
        return np.zeros((0, 0), dtype=np.float32)
    # Normalize rows for cosine
    norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
    Xn = X / norms
    # Similarity matrix (can be large; acceptable for current M<=5000 baseline)
    sims = (Xn @ Xn.T).astype(np.float32)
    np.fill_diagonal(sims, -1.0)  # exclude self in top-k selection
    k_eff = min(k, max(1, N - 1))
    # Argpartition for efficiency
    idx_part = np.argpartition(-sims, kth=k_eff - 1, axis=1)[:, :k_eff]
    rows = np.repeat(np.arange(N), k_eff)
    cols = idx_part.ravel()
    weights = sims[rows, cols]
    A = np.zeros((N, N), dtype=np.float32)
    A[rows, cols] = np.maximum(0.0, weights)  # no negative weights
    # Remove self loops explicitly
    np.fill_diagonal(A, 0.0)
    if mutual:
        mutual_mask = (A > 0) & (A.T > 0)
        A = A * mutual_mask
    # Symmetrize (take max to preserve strongest direction)
    A = np.maximum(A, A.T)
    # Zero diagonal again (safety)
    np.fill_diagonal(A, 0.0)
    return A
