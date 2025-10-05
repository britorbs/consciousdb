from fastapi.testclient import TestClient

from api.main import app


def test_health_endpoint():
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert "version" in body
    # embed_dim and expected_dim may be None prior to first query if lifespan not yet invoked in this test context
    assert "embed_dim" in body
    assert "expected_dim" in body
