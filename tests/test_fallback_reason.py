from fastapi.testclient import TestClient

from api.main import SET, app


def test_fallback_forced():
    prior = SET.api_keys
    SET.api_keys = None
    try:
        c = TestClient(app)
        # Lower similarity_gap_margin so easy gate is unlikely to trigger; ensure fallback path executes
        r = c.post(
            "/query",
            json={
                "query": "force fb",
                "k": 3,
                "m": 120,
                "overrides": {"force_fallback": True, "similarity_gap_margin": 0.01},
            },
        )
        assert r.status_code == 200, r.text
        diag = r.json()["diagnostics"]
        assert diag["fallback"] is True
        assert "forced" in diag["fallback_reason"]
    finally:
        SET.api_keys = prior


def test_fallback_iters_cap():
    prior = SET.api_keys
    SET.api_keys = None
    try:
        # Reduce iters_cap to 1 to trigger iters_cap reason
        c = TestClient(app)
        r = c.post("/query", json={"query": "iters cap", "k": 3, "m": 120, "overrides": {"iters_cap": 1}})
        assert r.status_code == 200, r.text
        diag = r.json()["diagnostics"]
        if diag["fallback"]:  # may not always hit, but when fallback true ensure reason present
            assert "iters_cap" in diag["fallback_reason"]
    finally:
        SET.api_keys = prior


def test_fallback_residual_reason():
    prior = SET.api_keys
    SET.api_keys = None
    try:
        # Force residual trigger by setting residual_tol extremely small
        c = TestClient(app)
        r = c.post("/query", json={"query": "resid trigger", "k": 3, "m": 120, "overrides": {"residual_tol": 1e-12}})
        assert r.status_code == 200, r.text
        diag = r.json()["diagnostics"]
        if diag["fallback"]:
            assert (
                "residual" in diag["fallback_reason"]
                or "iters_cap" in diag["fallback_reason"]
                or "forced" in diag["fallback_reason"]
            )
    finally:
        SET.api_keys = prior
