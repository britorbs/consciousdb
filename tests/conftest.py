"""Test fixtures and stubs for ConsciousDB SDK integration tests.

Provides a deterministic stub for ``solve_query`` to avoid depending on the
real solver implementation (keeps tests fast & deterministic).
"""

from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np
import pytest

from consciousdb import Config, ConsciousClient
from consciousdb import client as client_mod

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_LAST_OVERRIDES: dict[str, Any] | None = None


def _stub_solve_query(query: str, k: int, m: int, connector, embedder, overrides: dict[str, Any]):  # noqa: D401
    global _LAST_OVERRIDES
    _LAST_OVERRIDES = dict(overrides)
    # Build deterministic scores based on hash bucket to emulate ranking.
    base = abs(hash(query)) % 10_000
    items: list[dict[str, Any]] = []
    for i in range(k):
        score = (base % 100) / 100.0 - i * 0.01
        items.append(
            {
                "id": f"doc_{i}",
                "score": score,
                "align": score,
                "baseline_align": score,
                "energy_terms": {"coherence_drop": 0.0},
                "neighbors": [],
            }
        )
    return {
        "items": items,
        "diagnostics": {"deltaH_total": 0.0, "passed_overrides": overrides},
        "timings_ms": {"solve": 0.5},
    }


@pytest.fixture(autouse=True)
def patch_solve_query(monkeypatch, request):  # noqa: D401
    """Autouse patch for solve_query; disabled when test opts into real solver.

    Tests can opt-out of the stub by adding the marker ``@pytest.mark.real_solver``.
    An environment variable ``REAL_SOLVER=1`` also disables the stub globally.
    """
    use_real = bool(os.getenv("REAL_SOLVER")) or request.node.get_closest_marker("real_solver") is not None
    if not use_real:
        monkeypatch.setattr(client_mod, "solve_query", _stub_solve_query, raising=False)
    yield


class _StubConnector:  # minimal contract
    def top_m(self, query_vec: np.ndarray, m: int):  # noqa: D401
        return [(f"doc_{i}", 1.0 - i * 0.01, None) for i in range(m)]

    def fetch_vectors(self, ids):  # noqa: D401
        return np.zeros((len(ids), 4), dtype=np.float32)


class _StubEmbedder:
    def embed(self, text: str):  # noqa: D401
        v = np.zeros(4, dtype=np.float32)
        v[abs(hash(text)) % 4] = 1.0
        return v


@pytest.fixture()
def stub_client() -> ConsciousClient:
    connector = _StubConnector()
    embedder = _StubEmbedder()
    cfg = Config(alpha_deltaH=0.1)  # baseline for precedence tests
    return ConsciousClient(connector=connector, embedder=embedder, config=cfg, solver_overrides={"alpha_deltaH": 0.2})


# Local path bootstrap moved above to satisfy import ordering (E402).
