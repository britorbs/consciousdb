from fastapi.testclient import TestClient

from api.main import SET, app


def test_metrics_after_query():
    prior = SET.api_keys
    SET.api_keys = None  # disable auth for test
    try:
        c = TestClient(app)
        # Issue a query (respect schema min m>=100)
        r = c.post("/query", json={"query": "metrics test", "k": 3, "m": 120})
        assert r.status_code == 200, r.text
        m = c.get("/metrics")
        assert m.status_code == 200
        body = m.text
        # Check a few metric families & labels
        assert "conscious_query_latency_ms" in body
        assert "conscious_query_total" in body
        # Ensure redundancy histogram present
        assert "conscious_redundancy" in body
    finally:
        SET.api_keys = prior
