import numpy as np
import pytest

from engine.solve import solve_query


class _MiniConnector:
    def __init__(self, vecs: np.ndarray, ids):
        self.vecs = vecs.astype(np.float32)
        self.ids = list(ids)

    def top_m(self, query_vec: np.ndarray, m: int):  # returns (id, similarity, vector)
        sims = self.vecs @ (query_vec / (np.linalg.norm(query_vec) + 1e-12))
        order = np.argsort(-sims)[:m]
        out = []
        for i in order:
            out.append((self.ids[i], float(sims[i]), self.vecs[i]))
        return out

    def fetch_vectors(self, ids):  # not used because we return vectors in top_m
        idx = [self.ids.index(x) for x in ids]
        return self.vecs[idx]


class _MiniEmbedder:
    def embed(self, text: str):  # deterministic small embedding
        h = abs(hash(text)) % 10_000
        rng = np.random.default_rng(h)
        v = rng.normal(size=16).astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-12)
        return v


@pytest.mark.real_solver
def test_real_solver_ranks_and_energy():
    # Build small deterministic corpus
    rng = np.random.default_rng(42)
    base = rng.normal(size=(32, 16)).astype(np.float32)
    base /= np.linalg.norm(base, axis=1, keepdims=True) + 1e-12
    ids = [f"doc_{i}" for i in range(base.shape[0])]
    connector = _MiniConnector(base, ids)
    embedder = _MiniEmbedder()
    # Lower similarity gap by constraining m and explicit margin forcing full solve path
    result = solve_query(
        "test query", k=5, m=20, connector=connector, embedder=embedder, overrides={
            "alpha_deltaH": 0.4,
            "iters_cap": 10,
            "residual_tol": 1e-2,
            "similarity_gap_margin": 1.0,  # guarantee not early exit
            "coh_drop_min": 0.0,
        }
    )
    items = result["items"]
    diags = result["diagnostics"]
    assert len(items) == 5
    # Ensure deltaH path executed
    assert "coh_drop_total" in diags
    # Expect deltaH path considered (used_deltaH may be False if gating triggers fallback)
    # Accept either some coherence_drop or uplift present.
    assert any(
        (it["energy_terms"]["coherence_drop"] != 0.0) or (abs(it["uplift"]) > 0.0)
        for it in items
    )
    # Scores should be sorted descending
    scores = [it["score"] for it in items]
    assert scores == sorted(scores, reverse=True)
    # Alignment baseline present
    assert all("baseline_align" in it for it in items)

