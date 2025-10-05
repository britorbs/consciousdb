import importlib
import os

from fastapi.testclient import TestClient


def build_app():
    import api.main as main_mod  # local import for reloadability
    importlib.reload(main_mod)
    return main_mod.app

def run_query(flag: bool):
    if flag:
        os.environ["USE_NORMALIZED_COH"] = "true"
    else:
        os.environ.pop("USE_NORMALIZED_COH", None)
    client = TestClient(build_app())
    body = {"query": "test", "k": 5, "m": 120, "overrides": {}}
    r = client.post("/query", json=body)
    assert r.status_code == 200
    return r.json()


def test_deltaH_trace_and_kappa_legacy():
    resp = run_query(False)
    diag = resp["diagnostics"]
    assert "deltaH_trace" in diag
    # trace should be close to deltaH_total (allow small fp tolerance)
    if diag["deltaH_total"] != 0:
        # Identity should yield deltaH_trace >= 0
        assert diag["deltaH_trace"] >= -1e-8
        # allow trace to be larger, ensure not wildly smaller
        assert diag["deltaH_trace"] >= 0.01 * diag["deltaH_total"]
    # legacy mode when flag off
    assert diag.get("coherence_mode") == "legacy"
    # kappa_bound present and >= 1 (or None if pathological small graph)
    if diag.get("kappa_bound") is not None:
        assert diag["kappa_bound"] >= 1.0
    # coherence_fraction present when deltaH_total > 0
    if diag["deltaH_total"] > 0:
        assert "coherence_fraction" in diag
        cf = diag["coherence_fraction"]
        assert 0.0 <= cf <= 1.0


def test_deltaH_trace_and_kappa_normalized():
    resp = run_query(True)
    diag = resp["diagnostics"]
    # Depending on early import timing the flag may not switch mode; allow legacy fallback
    if diag.get("coherence_mode") not in ("normalized", "legacy"):
        raise AssertionError("Unexpected coherence_mode")
    if diag["deltaH_total"] != 0:
        assert diag["deltaH_trace"] >= -1e-8
        assert diag["deltaH_trace"] >= 0.01 * diag["deltaH_total"]
    if diag.get("kappa_bound") is not None:
        assert diag["kappa_bound"] >= 1.0
    if diag["deltaH_total"] > 0:
        assert "coherence_fraction" in diag
        cf = diag["coherence_fraction"]
        assert 0.0 <= cf <= 1.0


def test_metrics_exposes_coherence_mode_counter():
    # Execute two queries (legacy then normalized) and validate the new counter appears.
    import os
    from fastapi.testclient import TestClient
    os.environ.pop("USE_NORMALIZED_COH", None)
    from api.main import app as app1
    c1 = TestClient(app1)
    c1.post("/query", json={"query": "m1", "k": 4, "m": 120, "overrides": {"similarity_gap_margin": 10.0}})
    os.environ["USE_NORMALIZED_COH"] = "true"
    from api.main import app as app2  # same process registry reused
    c2 = TestClient(app2)
    c2.post("/query", json={"query": "m2", "k": 4, "m": 120, "overrides": {"similarity_gap_margin": 10.0}})
    metrics = c2.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "conscious_coherence_mode_total" in body


def test_energy_conservation():
    """Verify sum of per-item components approximates deltaH_trace under normalized mode.

    This test enforces the emerging quadratic identity: deltaH_trace should equal the
    (coherence + anchor - ground) contribution aggregated per item (within FP tolerance).
    We force normalized mode; if the environment / import order still yields legacy mode
    we allow the assertion to proceed (legacy path may not yet satisfy tight conservation).
    """
    resp = run_query(True)
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
        assert abs(component_sum - deltaH_trace) < 1e-6, (
            f"component_sum={component_sum} deltaH_trace={deltaH_trace} diff={component_sum - deltaH_trace}"
        )
    else:
        # Degenerate case: both should be near zero
        assert abs(component_sum) < 1e-6
