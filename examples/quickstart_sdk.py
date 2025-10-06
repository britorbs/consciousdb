"""Minimal SDK quickstart example.

Run:
    python examples/quickstart_sdk.py

This uses a trivial in-memory connector + a mock embedder to demonstrate
`ConsciousClient.query` end-to-end. Replace with real connectors / embedders
by installing extras, configuring environment variables, or passing your own
instances to the client constructor.
"""
from __future__ import annotations

import numpy as np

from consciousdb.client import ConsciousClient
from engine.solve import solve_query


class InMemoryConnector:
    """Very small in-memory connector for demonstration.

    Generates synthetic vectors lying on a unit circle arc so that
    structural relationships are non-trivial but fast.
    """

    def __init__(self, n: int = 32, dim: int = 8, seed: int = 42):
        rng = np.random.default_rng(seed)
        # Random directions with slight clustering to make some redundancy
        raw = rng.normal(size=(n, dim)).astype(np.float32)
        norms = np.linalg.norm(raw, axis=1, keepdims=True) + 1e-12
        self.vectors = raw / norms
        self.ids = [f"doc_{i}" for i in range(n)]

    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray]]:
        sims = (self.vectors @ query_vec) / (
            np.linalg.norm(self.vectors, axis=1) * (np.linalg.norm(query_vec) + 1e-12)
        )
        order = np.argsort(-sims)[:m]
        return [
            (self.ids[i], float(sims[i]), self.vectors[i].astype(np.float32))
            for i in order
        ]

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:  # not used (vectors provided above)
        mapping: dict[str, int] = {i: idx for idx, i in enumerate(self.ids)}
        arr_list = [self.vectors[mapping[_id]] for _id in ids]
        stacked: np.ndarray = np.stack(arr_list).astype(np.float32)
        return stacked


class MockEmbedder:
    def embed(self, text: str) -> np.ndarray:
        # Simple deterministic hash → vector for reproducibility
        h = abs(hash(text)) % (10**8)
        rng = np.random.default_rng(h)
        v = rng.normal(size=(self.dim,)).astype(np.float32)
        v /= np.linalg.norm(v) + 1e-12
        return v

    def __init__(self, dim: int = 8):
        self.dim = dim


def main():
    connector = InMemoryConnector(n=48, dim=8)
    embedder = MockEmbedder(dim=8)
    client = ConsciousClient(connector=connector, embedder=embedder)
    res = client.query("vector governance controls", k=6, m=24)
    print("deltaH_total:", res.diagnostics.get("deltaH_total"))
    for i, item in enumerate(res.items[:3]):
        print(f"{i+1}. id={item.id} score={item.score:.4f} align={item.align:.4f}")
    # Direct low-level access (optional):
    raw = solve_query("explainability in retrieval", k=5, m=16, connector=connector, embedder=embedder, overrides={})
    print("Low-level keys:", list(raw.keys()))


if __name__ == "__main__":
    main()
