import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_receipt_contains_deltaH_and_neighbors(monkeypatch):
    # Force full pipeline (disable easy gate)
    # Set a very high similarity_gap_margin so easy gate won't trigger
    req = {
        "query": "coherence layer pivot",
        "k": 5,
        "m": 120,
        "overrides": {
            "alpha_deltaH": 0.1,
            "similarity_gap_margin": 10.0,  # ensure not gated
            "coh_drop_min": 0.0,
            "expand_when_gap_below": 0.0,
            "iters_cap": 10,
            "residual_tol": 1e-3
        }
    }
    r = client.post("/query", json=req)
    assert r.status_code == 200, r.text
    data = r.json()
    diag = data["diagnostics"]
    # deltaH_total should mirror coh_drop_total
    assert "deltaH_total" in diag
    assert pytest.approx(diag["deltaH_total"], rel=1e-6) == diag["coh_drop_total"]
    # At least one item with neighbors list (may be empty if small kNN, but expect non-empty if k>=2)
    items = data["items"]
    assert len(items) > 0
    # Since kNN k=5 default and m>=120, adjacency should have neighbors
    neighbor_counts = [len(it["neighbors"]) for it in items]
    assert max(neighbor_counts) >= 1
    # Each neighbor has id and weight key 'w'
    for it in items:
        for n in it["neighbors"]:
            assert set(n.keys()) == {"id", "w"}
            assert isinstance(n["w"], float)
