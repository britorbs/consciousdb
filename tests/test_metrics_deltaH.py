from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_metrics_exposes_deltaH_histogram():
    # Force full path (avoid easy gate) by setting huge similarity_gap_margin
    r = client.post(
        "/query",
        json={
            "query": "deltaH metrics",
            "k": 5,
            "m": 120,
            "overrides": {"similarity_gap_margin": 10.0}
        },
    )
    assert r.status_code == 200
    m = client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    assert "conscious_deltaH_total" in body
    assert "conscious_gate_easy_total" in body
    assert "conscious_receipt_completeness_ratio" in body
