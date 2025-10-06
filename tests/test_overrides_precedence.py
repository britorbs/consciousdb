from __future__ import annotations

"""Tests override precedence: per-call > client solver_overrides > Config > defaults."""

def test_override_precedence(stub_client):
    res = stub_client.query("alpha precedence", k=3, m=10, overrides={"alpha_deltaH": 0.3})
    passed = res.diagnostics.get("passed_overrides", {})
    assert passed.get("alpha_deltaH") == 0.3, "Per-call override should win"


def test_solver_overrides_when_no_call_override(stub_client):
    res = stub_client.query("alpha precedence 2", k=2, m=5)
    passed = res.diagnostics.get("passed_overrides", {})
    # Expect solver_overrides (0.2) to override Config (0.1)
    assert passed.get("alpha_deltaH") == 0.2
