from fastapi.testclient import TestClient

from api.main import app


def test_fallback_reason_metric(monkeypatch):
    client = TestClient(app)
    # Force fallback via overrides (force_fallback)
    r = client.post(
        "/query",
        json={"query": "metric fallback", "k": 3, "m": 120, "overrides": {"alpha_deltaH": 0.1, "force_fallback": True}},
    )
    assert r.status_code == 200
    # Scrape metrics endpoint
    m = client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    # Expect our counter with label forced or contains reason
    assert "conscious_fallback_reason_total" in body
