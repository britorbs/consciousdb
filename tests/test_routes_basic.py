from fastapi.testclient import TestClient

from api.main import app


def test_healthz():
    from api.main import SET as _SET  # noqa: F401

    keys_prior = _SET.api_keys
    _SET.api_keys = None
    try:
        c = TestClient(app)
        r = c.get("/healthz")
        assert r.status_code == 200
        j = r.json()
        assert j.get("ok") is True
    finally:
        _SET.api_keys = keys_prior


def test_query_mock_fast():
    from api.main import SET as _SET

    keys_prior = _SET.api_keys
    _SET.api_keys = None
    try:
        c = TestClient(app)
        r = c.post("/query", json={"query": "hello world", "k": 3, "m": 200})
        assert r.status_code == 200
        j = r.json()
        assert "items" in j and len(j["items"]) > 0
        assert "diagnostics" in j
    finally:
        _SET.api_keys = keys_prior
