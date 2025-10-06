import json
import pytest
from tests._fastapi_optional import TestClient, FASTAPI_AVAILABLE
from api.main import app

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed (server extra missing)")


def test_query_response_conforms_to_schema():
    # Skip if jsonschema not installed (optional dev dep)
    if jsonschema is None:
        return
    c = TestClient(app)
    r = c.post(
        "/query",
        json={
            "query": "schema validation",
            "k": 3,
            "m": 120,
            "overrides": {"similarity_gap_margin": 10.0},
            "receipt_detail": 0,
        },
    )
    assert r.status_code == 200
    payload = r.json()
    with open("schemas/query_response.schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=payload, schema=schema)
