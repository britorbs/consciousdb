import pytest

from api.main import SET, app
from tests._fastapi_optional import FASTAPI_AVAILABLE, TestClient

pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed (server extra missing)")


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
