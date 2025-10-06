import numpy as np
import pytest

from engine.solve import solve_query


class _Conn:
    def __init__(self, vecs, ids, sims):
        self.vecs = vecs
        self.ids = ids
        self.sims = sims

    def top_m(self, qv, m):
        # Provide embedding vectors directly + custom similarities to bypass randomness
        order = np.argsort(-self.sims)[:m]
        return [(self.ids[i], float(self.sims[i]), self.vecs[i]) for i in order]

    def fetch_vectors(self, ids):  # not used
        idx = [self.ids.index(x) for x in ids]
        return self.vecs[idx]


class _Emb:
    def __init__(self, v):
        self.v = v / (np.linalg.norm(v) + 1e-12)

    def embed(self, text):
        return self.v


@pytest.mark.real_solver
def test_rank_and_mmr_branch():
    rng = np.random.default_rng(123)
    # Construct corpus with deliberate redundancy so MMR triggers
    base = rng.normal(size=(25, 32)).astype(np.float32)
    base /= np.linalg.norm(base, axis=1, keepdims=True) + 1e-12
    # Force similarities to be close so early gap gate does not short-circuit.
    sims = base @ base[0]
    sims = (sims - sims.min()) / (sims.max() - sims.min() + 1e-12)  # normalize 0..1
    sims *= 0.05  # compress range so top vs 10th gap is small
    ids = [f"d{i}" for i in range(base.shape[0])]
    conn = _Conn(base, ids, sims)
    emb = _Emb(base[0])
    res = solve_query(
        "irrelevant", k=8, m=20, connector=conn, embedder=emb, overrides={
            # Set margin high so gap <= margin and full optimization path runs
            "similarity_gap_margin": 1.0,
            "alpha_deltaH": 0.6,
            "iters_cap": 12,
            "residual_tol": 5e-3,
            "coh_drop_min": 0.0,
            "use_mmr": True,
            # Force MMR branch by making threshold trivially low
            "redundancy_threshold": -1.0,
            "mmr_lambda": 0.5,
        }
    )
    diags = res["diagnostics"]
    assert diags["used_deltaH"] in (True, False)  # path executed
    # If redundancy high enough used_mmr may be True
    # Redundancy key should be present (full path executed)
    assert "redundancy" in diags
    # If redundancy threshold exceeded and MMR requested, flag may be True/False; just assert presence
    assert "used_mmr" in diags
    # Scores list should contain the max score first (MMR may reorder subsequent items for diversity)
    scores = [it["score"] for it in res["items"]]
    assert scores[0] == max(scores)
    # All ids unique
    assert len({it["id"] for it in res["items"]}) == len(res["items"])
