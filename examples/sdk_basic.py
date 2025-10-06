"""Basic SDK usage example for ConsciousDB.

Run with:
    python examples/sdk_basic.py

This uses a minimal in-memory connector and a trivial embedder to demonstrate
construction of the client and performing a single query.
"""
from __future__ import annotations

import numpy as np

from consciousdb import Config, ConsciousClient


class InMemoryConnector:
    """Simple in-memory connector storing dense vectors for demonstration.

    Exposes the minimal contract consumed by the client:
      - top_m(query_vec, m) -> list[(id, similarity, vector)]
      - fetch_vectors(ids) -> np.ndarray
    """

    def __init__(self):
        self.ids = [f"doc{i}" for i in range(8)]
        rng = np.random.default_rng(42)
        self.vecs = rng.normal(size=(len(self.ids), 16)).astype("float32")
        # L2 normalize to approximate cosine with dot product
        self.vecs /= np.linalg.norm(self.vecs, axis=1, keepdims=True) + 1e-12

    def top_m(self, query_vec, m: int):  # noqa: D401
        sims = self.vecs @ (query_vec / (np.linalg.norm(query_vec) + 1e-12))
        order = np.argsort(-sims)[:m]
        out = []
        for idx in order:
            out.append((self.ids[idx], float(sims[idx]), self.vecs[idx]))
        return out

    def fetch_vectors(self, ids):  # noqa: D401
        id_to_idx = {d: i for i, d in enumerate(self.ids)}
        return self.vecs[[id_to_idx[i] for i in ids]]


class TrivialEmbedder:
    """Maps text deterministically to a vector for demo consistency."""

    def embed(self, text: str):  # noqa: D401
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        v = rng.normal(size=16).astype("float32")
        v /= np.linalg.norm(v) + 1e-12
        return v


def main():  # noqa: D401
    cfg = Config.from_env()  # Optionally override: Config(iters_cap=15, residual_tol=1e-3)
    connector = InMemoryConnector()
    embedder = TrivialEmbedder()
    client = ConsciousClient(connector=connector, embedder=embedder, config=cfg)

    query = "vector governance controls"
    result = client.query(query, k=5, m=50, overrides={"alpha_deltaH": 0.15})

    print("Top Results:")
    for item in result.items:
        print(f"  {item.id}\tscore={item.score:.4f}")
    print("\nDiagnostics (subset):")
    for key in ["deltaH_total", "redundancy", "iters_used"]:
        if key in result.diagnostics:
            print(f"  {key}: {result.diagnostics[key]}")
    print("Timings (ms):", result.timings_ms)


if __name__ == "__main__":  # pragma: no cover
    main()
