import json
import os

from fastapi.testclient import TestClient

from api.main import SET, app


def test_audit_log_written(tmp_path):
    # Ensure audit log starts clean
    log_path = tmp_path / "audit.log"
    # Monkeypatch working directory so audit.log writes here
    cwd_prior = os.getcwd()
    SET.api_keys = None  # disable auth
    try:
        os.chdir(tmp_path)
        c = TestClient(app)
        r = c.post("/query", json={"query": "audit trail", "k": 3, "m": 120})
        assert r.status_code == 200
        assert log_path.exists(), "audit.log not created"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        evt = json.loads(lines[-1])
        # Core required keys
        for k in [
            "ts",
            "query",
            "k",
            "m",
            "deltaH_total",
            "fallback",
            "receipt_version",
            "items",
        ]:
            assert k in evt, f"missing key {k} in audit event"
        assert isinstance(evt["items"], list) and len(evt["items"]) > 0
        first = evt["items"][0]
        for k in ["id", "score", "coherence_drop", "neighbors"]:
            assert k in first
        # neighbors should be list of ids
        assert isinstance(first["neighbors"], list)
    finally:
        os.chdir(cwd_prior)
