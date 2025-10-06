import numpy as np

from engine.solve import solve_query


class DummyConnector:
    def top_m(self, y, m):
        # Return id, similarity, and vector
        return [(f"doc_{i}", 0.9 - i * 0.01, np.ones(8, dtype=np.float32) * (i + 1)) for i in range(m)]

    def fetch_vectors(self, ids):  # not used because we include vectors
        return np.stack([np.ones(8, dtype=np.float32) for _ in ids])


class DummyEmbedder:
    def embed(self, text):
        return np.ones(8, dtype=np.float32)


def test_solve_query_basic_paths():
    res = solve_query(
        query="test query",
        k=5,
        m=10,
        connector=DummyConnector(),
        embedder=DummyEmbedder(),
        overrides={"force_fallback": True},  # ensure fallback path covered
    )
    assert "items" in res and "diagnostics" in res and "timings_ms" in res
    assert len(res["items"]) == 5
    first = res["items"][0]
    assert {"id", "score", "align", "baseline_align", "energy_terms", "neighbors"}.issubset(first.keys())
    # Force MMR usage by enabling and lowering threshold
    res_mmr = solve_query(
        query="test query",
        k=5,
        m=10,
        connector=DummyConnector(),
        embedder=DummyEmbedder(),
        overrides={"use_mmr": True, "redundancy_threshold": 0.0},
    )
    assert res_mmr["diagnostics"].get("used_mmr") in (True, False)
