from fastapi.testclient import TestClient
from api.main import app, SET

def test_query_feedback_linkage_and_metrics():
    SET.enable_adaptive = True
    SET.api_keys = None
    c = TestClient(app)
    # Issue a query, capture query_id and deltaH
    r = c.post("/query", json={"query": "linkage test", "k": 4, "m": 150})
    assert r.status_code == 200
    j = r.json()
    qid = j.get("query_id")
    assert qid is not None
    dH = j["diagnostics"]["deltaH_total"]
    # Provide feedback referencing query_id
    fb = c.post("/feedback", json={"query_id": qid, "clicked_ids": ["docX"], "accepted_id": None})
    assert fb.status_code == 200
    # Scrape metrics and ensure adaptive metrics present
    m = c.get("/metrics")
    text = m.text
    assert "conscious_adaptive_feedback_total" in text
    assert "conscious_adaptive_events_buffer_size" in text
    # Reset flag
    SET.enable_adaptive = False
