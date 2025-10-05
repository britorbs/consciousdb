from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_receipt_version_present():
    r = client.post(
        "/query",
        json={
            "query": "check receipt version",
            "k": 3,
            "m": 120,
            "overrides": {"similarity_gap_margin": 10.0}
        },
    )
    assert r.status_code == 200
    diag = r.json()["diagnostics"]
    assert "receipt_version" in diag
    assert diag["receipt_version"] == 1
