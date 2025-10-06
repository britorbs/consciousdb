"""Smoke test for the ConsciousClient synchronous SDK facade.

Ensures a minimal end-to-end flow runs without the FastAPI server.
"""

from __future__ import annotations

import numpy as np

from consciousdb import ConsciousClient
from consciousdb import client as client_mod


class StubConnector:
    def __init__(self):
        # Pretend we have 5 documents with trivial embeddings (unit vectors on axes)
        self.ids = [f"doc{i}" for i in range(5)]
        self.vecs = np.eye(5, dtype=np.float32)

    def top_m(self, query_vec: np.ndarray, m: int):  # simplified signature
        # Cosine similarity with unit vectors ~ query component
        sims = self.vecs @ query_vec.ravel()
        order = np.argsort(-sims)[:m]
        out = []
        for idx in order:
            out.append((self.ids[idx], float(sims[idx]), self.vecs[idx]))
        return out

    def fetch_vectors(self, ids):  # noqa: D401
        id_to_idx = {d: i for i, d in enumerate(self.ids)}
        arrs = [self.vecs[id_to_idx[i]] for i in ids]
        return np.vstack(arrs)


class StubEmbedder:
    def embed(self, text: str):  # noqa: D401
        # Map text length mod 5 to a one-hot position
        n = len(text) % 5
        v = np.zeros(5, dtype=np.float32)
        v[n] = 1.0
        return v


# Provide a shim solve_query matching expected import; if real one exists it overrides this.


def _fake_solve_query(query: str, k: int, m: int, connector, embedder, overrides):  # noqa: D401
    q_vec = embedder.embed(query)
    top = connector.top_m(q_vec, m)
    items = []
    for vid, score, _v in top[:k]:
        items.append(
            {
                "id": vid,
                "score": score,
                "align": score,
                "baseline_align": score,
                "energy_terms": {"coherence_drop": 0.0},
                "neighbors": [],
            }
        )
    return {"items": items, "diagnostics": {"deltaH_total": 0.0}, "timings_ms": {"solve": 1.0}}


# Monkeypatch if needed
if getattr(client_mod, "solve_query", None) is None:  # runtime monkeypatch for smoke path
    client_mod.solve_query = _fake_solve_query


def test_conscious_client_smoke():
    connector = StubConnector()
    embedder = StubEmbedder()
    c = ConsciousClient(connector=connector, embedder=embedder)
    res = c.query("hello", k=3, m=5)
    assert len(res.items) == 3
    assert all(it.id.startswith("doc") for it in res.items)
    assert res.diagnostics.get("deltaH_total") == 0.0
    assert "client_total" in res.timings_ms
