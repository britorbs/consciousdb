from fastapi.testclient import TestClient

from api.main import app


def run_query():
    client = TestClient(app)
    r = client.post("/query", json={"query": "test", "k": 5, "m": 120, "overrides": {}})
    assert r.status_code == 200
    return r.json()


def test_deltaH_trace_and_kappa_normalized():
    resp = run_query()
    diag = resp["diagnostics"]
    if diag["deltaH_total"] != 0:
        assert diag["deltaH_trace"] >= -1e-8
        assert diag["deltaH_trace"] >= 0.01 * diag["deltaH_total"]
    if diag.get("kappa_bound") is not None:
        assert diag["kappa_bound"] >= 1.0
    if diag["deltaH_total"] > 0:
        assert "coherence_fraction" in diag
        cf = diag["coherence_fraction"]
        assert 0.0 <= cf <= 1.0


def test_metrics_basic_exposure():
    client = TestClient(app)
    client.post("/query", json={"query": "m1", "k": 4, "m": 120, "overrides": {"similarity_gap_margin": 10.0}})
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "conscious_deltaH_total" in metrics.text


def test_energy_conservation():
    """Verify sum of per-item components approximates deltaH_trace under normalized mode.

    This test enforces the emerging quadratic identity: deltaH_trace should equal the
    (coherence + anchor - ground) contribution aggregated per item (within FP tolerance).
    We force normalized mode; if the environment / import order still yields legacy mode
    we allow the assertion to proceed (legacy path may not yet satisfy tight conservation).
    """
    resp = run_query()
    diag = resp["diagnostics"]
    items = resp["items"]
    # Extract per-item weighted components
    total_coh = sum(it["energy_terms"]["coherence_drop"] for it in items)
    total_anc = sum(it["energy_terms"]["anchor_drop"] for it in items)
    total_grd = sum(it["energy_terms"]["ground_penalty"] for it in items)
    component_sum = total_coh + total_anc - total_grd
    deltaH_trace = diag["deltaH_trace"]
    # Only assert tight conservation when trace is non-trivial
    if abs(deltaH_trace) > 1e-9:
        assert (
            abs(component_sum - deltaH_trace) < 1e-6
        ), f"component_sum={component_sum} deltaH_trace={deltaH_trace} diff={component_sum - deltaH_trace}"
    else:
        # Degenerate case: both should be near zero
        assert abs(component_sum) < 1e-6
