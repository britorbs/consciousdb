from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_uplift_fields_present_full():
    r = client.post(
        "/query",
        json={
            "query": "uplift test full",
            "k": 5,
            "m": 120,
            "overrides": {"similarity_gap_margin": 0.0},
            "receipt_detail": 1,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) > 0
    for it in data["items"]:
        # baseline_align and uplift should be present (may be zero or negative but numeric)
        assert "baseline_align" in it
        assert "uplift" in it
        assert isinstance(it["baseline_align"], (float | int))
        assert isinstance(it["uplift"], (float | int))
        # When full receipt, neighbors may be present (not asserted non-empty because of randomness)
        assert "energy_terms" in it
        assert it["energy_terms"]["coherence_drop"] is not None


def test_lightweight_mode_strips_neighbors_and_energy():
    r = client.post(
        "/query",
        json={
            "query": "uplift test light",
            "k": 4,
            "m": 120,
            "overrides": {"similarity_gap_margin": 0.0},
            "receipt_detail": 0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) > 0
    for it in data["items"]:
        assert it["neighbors"] == []
        # Energy terms coerced to zero in lightweight mode
        assert it["energy_terms"]["coherence_drop"] == 0.0
        assert it["energy_terms"]["anchor_drop"] == 0.0
        assert it["energy_terms"]["ground_penalty"] == 0.0
        # uplift still provided
        assert "uplift" in it
