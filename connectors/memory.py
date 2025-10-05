from __future__ import annotations

import numpy as np

from .base import BaseConnector


class MemoryConnector(BaseConnector):
    def __init__(self, data: np.ndarray | None = None, ids: list[str] | None = None):
        # Small random dataset for dev; replace via setters if needed
        if data is None:
            rng = np.random.default_rng(0)
            self.X = np.linalg.norm(rng.normal(size=(1024, 32)), axis=1, keepdims=True)
            self.X = (rng.normal(size=(1024, 32))).astype(np.float32)
            norms = np.linalg.norm(self.X, axis=1, keepdims=True) + 1e-12
            self.X = (self.X / norms).astype(np.float32)
        else:
            self.X = data.astype(np.float32)
        if ids is None:
            self.ids = [f"doc:{i}" for i in range(self.X.shape[0])]
        else:
            self.ids = ids

    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray | None]]:
        q = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        sims = (self.X @ q).astype(np.float32)
        order = np.argsort(-sims)[:m]
        out = []
        for i in order:
            out.append((self.ids[i], float(sims[i]), self.X[i]))
        return out

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:
        # Naive mapping by index in name (only for dev)
        idxs = [int(x.split(":")[-1]) for x in ids]
        return self.X[idxs]
