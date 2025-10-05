from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import SET, app


def test_auth_disabled_without_keys():
    # Ensure no API_KEYS set
    assert not SET.api_keys
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200


def test_auth_rejects_without_header():
    prior = SET.api_keys
    try:
        SET.api_keys = "secret1,secret2"
        c = TestClient(app)
        r = c.get("/healthz")
        assert r.status_code == 401
    finally:
        SET.api_keys = prior


def test_auth_accepts_valid_key():
    prior = SET.api_keys
    try:
        SET.api_keys = "alpha,beta"
        c = TestClient(app)
        r = c.get("/healthz", headers={"x-api-key": "beta"})
        assert r.status_code == 200
    finally:
        SET.api_keys = prior


def test_easy_query_gate_triggers():
    prior = SET.api_keys
    SET.api_keys = None  # ensure auth disabled
    try:
        c = TestClient(app)
        r = c.post("/query", json={"query": "hello", "k": 3, "m": 120, "overrides": {"similarity_gap_margin": 0.0}})
        assert r.status_code == 200
        j = r.json()
        assert j["diagnostics"]["similarity_gap"] >= 0
    finally:
        SET.api_keys = prior


def test_coh_drop_gate():
    prior = SET.api_keys
    SET.api_keys = None
    try:
        c = TestClient(app)
        r = c.post("/query", json={"query": "hello", "k": 3, "m": 120, "overrides": {"coh_drop_min": 1e9}})
        assert r.status_code == 200
        j = r.json()
        assert j["diagnostics"]["used_deltaH"] is False
    finally:
        SET.api_keys = prior
