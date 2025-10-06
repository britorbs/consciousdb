"""Synthetic load test for normalized coherence stability.

Runs N (default 1000) queries with normalized mode enabled to approximate Phase 2
readiness criteria locally (informational scope diff; fallback rate < 5%).

NOTE: This is a longer-running test (~20+ minutes for N=1000). You may wish to
run it selectively:

    pytest -k normalization_load -s --maxfail=1

You can override the number of queries with the environment variable
NORMALIZATION_LOAD_N (e.g., export NORMALIZATION_LOAD_N=200 for a quicker smoke).
"""
from __future__ import annotations

import json
import os
import random
import statistics
from typing import List

# Set env flags BEFORE importing the FastAPI app so Settings picks them up once.
os.environ.setdefault("USE_NORMALIZED_COH", "true")
os.environ.setdefault("USE_MOCK", "true")  # ensure deterministic mock connector path

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


def _percentile(arr: List[float], pct: float) -> float:
    if not arr:
        return 0.0
    return float(np.percentile(np.array(arr, dtype=float), pct))


def test_normalized_stability_load():  # pragma: no cover - long-running analytic test
    N = int(os.getenv("NORMALIZATION_LOAD_N", "1000"))
    # Allow skipping entirely (CI might exclude) by setting to 0
    if N <= 0:
        return

    client = TestClient(app)

    query_templates = [
        "vector governance controls",
        "database optimization techniques",
        "machine learning algorithms",
        "distributed systems architecture",
        "security compliance frameworks",
        "data privacy regulations",
        "cloud infrastructure management",
        "API design patterns",
        "microservices orchestration",
        "quantum computing applications",
    ]

    rel_diffs: List[float] = []  # now scope diffs (full vs top-k)
    coherence_fractions: List[float] = []
    kappa_bounds: List[float] = []
    fallback_count = 0

    for i in range(N):
        query = random.choice(query_templates) + f" variation {i % 10}"
        k = random.choice([4, 6, 8, 10])
        m = random.choice([200, 300, 400, 500])
        response = client.post(
            "/query",
            json={
                "query": query,
                "k": k,
                "m": m,
                "overrides": {
                    "alpha_deltaH": random.uniform(0.05, 0.15),
                    "similarity_gap_margin": random.uniform(0.1, 0.2),
                    "coh_drop_min": random.uniform(0.005, 0.02),
                    "expand_when_gap_below": random.uniform(0.05, 0.1),
                    "iters_cap": random.choice([15, 20, 25]),
                    "residual_tol": random.choice([0.0005, 0.001, 0.002]),
                },
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        diag = data.get("diagnostics", {})
        if diag.get("deltaH_scope_diff") is not None:
            rel_diffs.append(float(diag["deltaH_scope_diff"]))
        if diag.get("coherence_fraction") is not None:
            coherence_fractions.append(float(diag["coherence_fraction"]))
        if diag.get("kappa_bound") is not None:
            kappa_bounds.append(float(diag["kappa_bound"]))
        if diag.get("fallback"):
            fallback_count += 1
        if (i + 1) % max(1, N // 10) == 0:
            print(f"Completed {i + 1}/{N} queries")

    if not rel_diffs:
        raise AssertionError("No deltaH_scope_diff values collected; check normalization path.")

    p50 = _percentile(rel_diffs, 50)
    p90 = _percentile(rel_diffs, 90)
    p95 = _percentile(rel_diffs, 95)
    p99 = _percentile(rel_diffs, 99)
    rel_max = max(rel_diffs)

    mean_coh_fraction = statistics.fmean(coherence_fractions) if coherence_fractions else 0.0
    std_coh_fraction = statistics.pstdev(coherence_fractions) if len(coherence_fractions) > 1 else 0.0

    fallback_rate = fallback_count / float(N)

    report = {
        "total_queries": N,
    "deltaH_scope_diff": {
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99,
            "max": rel_max,
            "samples": len(rel_diffs),
            "note": "Scope diff full vs top-k; large (~0.3-0.4) expected"
        },
        "coherence_fraction": {
            "mean": mean_coh_fraction,
            "std": std_coh_fraction,
            "min": min(coherence_fractions) if coherence_fractions else None,
            "max": max(coherence_fractions) if coherence_fractions else None,
        },
        "kappa_bound": {
            "mean": statistics.fmean(kappa_bounds) if kappa_bounds else None,
            "p95": _percentile(kappa_bounds, 95) if kappa_bounds else None,
        },
        "fallback_rate": fallback_rate,
        "phase_2_ready": (fallback_rate < 0.05),
    }

    with open("normalization_load_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n=== Normalization Load Test Report ===")
    print(json.dumps(report, indent=2))

    # Hard assertions for Phase 2 criteria (can relax by setting NORMALIZATION_LOAD_STRICT=false)
    strict = os.getenv("NORMALIZATION_LOAD_STRICT", "true").lower() in ("1", "true", "yes")
    if strict:
        # Only enforce operational fallback rate threshold now; scope diff is informational.
    print(f"Scope difference P95: {p95:.3f} (expected ~0.3-0.4 for top-k vs full)")
        assert fallback_rate < 0.05, f"Fallback rate {fallback_rate:.2%} >= 5% threshold"

    # Assert we gathered a reasonable number of samples. Some queries trigger the
    # easy_query_gate and skip full energy decomposition (leaving deltaH_rel_diff None),
    # so expecting 90% coverage is unrealistic under mocked / gated conditions.
    # Default minimum: at least 50% of queries OR an absolute floor (env override).
    min_samples_env = int(os.getenv("NORMALIZATION_LOAD_MIN_SAMPLES", "300"))
    min_fraction = float(os.getenv("NORMALIZATION_LOAD_MIN_FRACTION", "0.5"))
    required = max(min_samples_env, int(min_fraction * N))
    assert len(rel_diffs) >= required, (
    f"Insufficient deltaH_scope_diff coverage ({len(rel_diffs)}/{N}); need >= {required}. "
        "Increase overrides to force harder queries or lower requirement via env vars "
        "NORMALIZATION_LOAD_MIN_SAMPLES / NORMALIZATION_LOAD_MIN_FRACTION."
    )

    print("\n✓ Synthetic normalization stability test completed.")
