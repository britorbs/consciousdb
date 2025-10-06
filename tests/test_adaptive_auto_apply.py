from fastapi.testclient import TestClient

from api.main import SET, app


def test_adaptive_auto_apply(monkeypatch):
    # Simulate suggested alpha present
    SET.enable_adaptive = True
    SET.enable_adaptive_apply = True
    from adaptive.manager import STATE

    STATE.suggested_alpha = 0.22
    client = TestClient(app)
    r = client.post("/query", json={"query": "alpha apply", "k": 5, "m": 150, "overrides": {"alpha_deltaH": 0.1}})
    assert r.status_code == 200
    data = r.json()
    diag = data["diagnostics"]
    # Because we applied suggestion, applied_alpha should equal suggested_alpha
    if diag.get("suggested_alpha") is not None:
        assert diag.get("applied_alpha") == diag.get("suggested_alpha")
        assert diag.get("alpha_source") in ("suggested", "bandit")
