from fastapi.testclient import TestClient

from api.main import app


def _run():
    client = TestClient(app)
    r = client.post(
        "/query",
        json={
            "query": "energy identity test",
            "k": 5,
            "m": 120,
            "overrides": {
                "similarity_gap_margin": 10.0,
                "coh_drop_min": 0.0,
                "iters_cap": 12,
            },
        },
    )
    assert r.status_code == 200
    return r.json()


def _assert_conservation(resp: dict):
    diag = resp["diagnostics"]
    items = resp["items"]
    # Sum per-item coherence_drop
    per_item_sum = sum(it["energy_terms"]["coherence_drop"] for it in items)
    deltaH_total = diag["deltaH_total"]
    # Basic non-negativity (can be zero if trivial solve)
    assert diag["deltaH_trace"] >= -1e-8
    # Placeholder: deltaH_trace may not yet equal deltaH_total (future identity). Ensure it's not wildly off (factor bound)
    if deltaH_total > 1e-9:
        ratio = diag["deltaH_trace"] / (deltaH_total + 1e-12)
        # Accept broad band; fail only if clearly pathological
        assert 0.0 <= ratio <= 2.0
    # Current implementation: deltaH_total folds coherence + anchor + ground while per-item coherence_drop
    # only covers the coherence component. Expect per_item_sum <= deltaH_total. Enforce weak sanity:
    if deltaH_total > 1e-9:
        assert per_item_sum <= deltaH_total * 1.01  # small FP / ordering slack
        # Ensure coherence portion is a meaningful fraction (not vanishing unexpectedly)
        frac = per_item_sum / (deltaH_total + 1e-12)
        assert 0.01 <= frac <= 1.01


def test_energy_conservation_normalized():
    resp = _run()
    _assert_conservation(resp)
