import os, json, tempfile, pathlib
from fastapi.testclient import TestClient
from api.main import app, SET


def test_audit_signature_present(monkeypatch):
    # Enable audit log and set HMAC key
    monkeypatch.setenv("ENABLE_AUDIT_LOG", "true")
    monkeypatch.setenv("AUDIT_HMAC_KEY", "secret")
    # Re-import settings not easily; rely on global SET having been created before
    SET.enable_audit_log = True
    SET.audit_hmac_key = "secret"
    # temp directory for logs
    with tempfile.TemporaryDirectory() as td:
        cwd = os.getcwd()
        os.chdir(td)
        try:
            client = TestClient(app)
            r = client.post("/query", json={"query":"hello world", "k":3, "m":120, "overrides": {"alpha_deltaH": 0.1}})
            assert r.status_code == 200
            # Read latest audit line
            path = pathlib.Path("audit.log")
            assert path.exists()
            line = path.read_text().strip().splitlines()[-1]
            obj = json.loads(line)
            # signature field should exist
            assert "signature" in obj
            # Recompute signature for verification
            import hmac, hashlib
            body_no_sig = {k:v for k,v in obj.items() if k != "signature"}
            recomputed = hmac.new(SET.audit_hmac_key.encode("utf-8"), json.dumps(body_no_sig, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
            assert recomputed == obj["signature"]
        finally:
            os.chdir(cwd)
