from fastapi.testclient import TestClient

from api.main import SET, app


def test_force_fallback_flag():
    prior = SET.api_keys
    SET.api_keys = None
    try:
        c = TestClient(app)
        payload = {
            "query": "x",
            "k": 3,
            "m": 200,
            "overrides": {"force_fallback": True},
        }
        r = c.post("/query", json=payload)
        assert r.status_code == 200
        j = r.json()
        assert j["diagnostics"]["fallback"] is True or j["diagnostics"]["used_deltaH"] is False
    finally:
        SET.api_keys = prior
