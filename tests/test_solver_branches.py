import numpy as np
import pytest

from engine.solve import solve_query


class _ConnGate:
    def __init__(self, vecs, sims, ids):
        self.vecs = vecs
        self.sims = sims
        self.ids = ids

    def top_m(self, qv, m):
        order = np.argsort(-self.sims)[:m]
        return [(self.ids[i], float(self.sims[i]), self.vecs[i]) for i in order]

    def fetch_vectors(self, ids):
        idx = [self.ids.index(x) for x in ids]
        return self.vecs[idx]


class _EmbConst:
    def __init__(self, v):
        self.v = v / (np.linalg.norm(v) + 1e-12)

    def embed(self, text):
        return self.v


@pytest.mark.real_solver
def test_baseline_gate_triggers():
    # Construct sims with a modest gap (first - 10th ≈ 0.248). Use margin smaller than gap to trigger baseline path.
    rng = np.random.default_rng(7)
    vecs = rng.normal(size=(30, 24)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    sims = np.linspace(1.0, 0.2, num=30)
    ids = [f"g{i}" for i in range(30)]
    connector = _ConnGate(vecs, sims, ids)
    emb = _EmbConst(vecs[0])
    res = solve_query(
        "q", k=5, m=20, connector=connector, embedder=emb, overrides={
            "similarity_gap_margin": 0.05,  # gap (~0.248) > margin triggers baseline path
            "coh_drop_min": 0.0,
        }
    )
    diags = res["diagnostics"]
    assert diags["fallback"] is False
    assert diags["used_deltaH"] is False
    assert diags["similarity_gap"] > 0.05
    # Energy terms should be zero
    assert all(it["energy_terms"]["coherence_drop"] == 0.0 for it in res["items"])


@pytest.mark.real_solver
def test_force_fallback_disables_deltaH():
    rng = np.random.default_rng(9)
    vecs = rng.normal(size=(25, 24)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    sims = rng.random(25)
    ids = [f"f{i}" for i in range(25)]
    connector = _ConnGate(vecs, sims, ids)
    emb = _EmbConst(vecs[0])
    res = solve_query(
        "q", k=6, m=20, connector=connector, embedder=emb, overrides={
            "similarity_gap_margin": 0.0,  # allow full path
            "force_fallback": True,
            "coh_drop_min": 0.0,
            "iters_cap": 8,
            "residual_tol": 1e-2,
        }
    )
    diags = res["diagnostics"]
    assert diags["fallback"] is True
    assert diags["used_deltaH"] is False
    # Returned items length matches k
    assert len(res["items"]) == 6
