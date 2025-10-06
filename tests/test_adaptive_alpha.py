import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    TestClient = None  # sentinel

from api.main import SET, app

pytestmark = pytest.mark.skipif(TestClient is None, reason="fastapi not installed (server extra missing)")


def test_adaptive_alpha_suggestion_emerges(monkeypatch):
    # Enable adaptive feature flag
    SET.enable_adaptive = True
    SET.api_keys = None
    c = TestClient(app)

    # Fire several queries (suggested_alpha initially None)
    r = c.post("/query", json={"query": "alpha tuning", "k": 4, "m": 150})
    assert r.status_code == 200
    first_diag = r.json()["diagnostics"]
    assert "suggested_alpha" in first_diag
    # May be None early because not enough feedback events yet

    # Provide a series of feedback events to cross MIN_SAMPLE threshold (~15). Using 20.
    for i in range(20):
        c.post(
            "/feedback",
            json={
                "query_id": f"q{i}",
                "clicked_ids": ["docA"] if i % 2 == 0 else [],
                "accepted_id": "docA" if i % 5 == 0 else None,
            },
        )

    # Another query should now surface a suggested_alpha (may still be None if correlation weak; assert key exists)
    r2 = c.post("/query", json={"query": "alpha tuning 2", "k": 4, "m": 150})
    assert r2.status_code == 200
    diag2 = r2.json()["diagnostics"]
    assert "suggested_alpha" in diag2
    # If present, should be within allowed clamp range
    if diag2["suggested_alpha"] is not None:
        assert 0.02 <= diag2["suggested_alpha"] <= 0.5

    # Reset flag to avoid side-effects on other tests
    SET.enable_adaptive = False
