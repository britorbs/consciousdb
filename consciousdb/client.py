"""Synchronous client facade for ConsciousDB.

This wraps existing solver / ranking logic so users can embed optimization locally
without running the FastAPI service. The interface mirrors the former REST /query
endpoint shape (minus transport wrapper).

Design Notes:
- Keep dependencies minimal; avoid importing FastAPI or server modules.
- Connectors and embedders are injected or can be looked up via registries (future enhancement).
- Configuration precedence: per-call overrides > constructor overrides > config.to_overrides().
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class _SolveQueryFn(Protocol):  # noqa: D401
    def __call__(
        self,
        query: str,
        k: int,
        m: int,
        connector: Any,
        embedder: Any,
        overrides: dict | None,
    ) -> dict[str, Any]: ...

try:  # soft import pattern
    from engine.solve import solve_query as _real_solve_query  # noqa: F401
    solve_query: _SolveQueryFn | None = _real_solve_query
except Exception:  # pragma: no cover
    solve_query = None


@dataclass
class RankedItem:
    id: str
    score: float
    align: float | None = None
    baseline_align: float | None = None
    energy_terms: dict[str, float] | None = None
    neighbors: list[dict[str, Any]] | None = None


@dataclass
class QueryResult:
    items: list[RankedItem]
    diagnostics: dict[str, Any]
    timings_ms: dict[str, float]

    def to_dict(self) -> dict[str, Any]:  # convenience for serialization
        return {
            "items": [item.__dict__ for item in self.items],
            "diagnostics": self.diagnostics,
            "timings_ms": self.timings_ms,
        }


class ConsciousClient:
    """Primary synchronous SDK entrypoint.

    Parameters
    ----------
    connector : Any
        Object providing vector access; must expose at least a `top_m(query_vec, m)` and `fetch_vectors(ids)` signature.
    embedder : Any
        Object providing `embed(text: str) -> np.ndarray` or `embed_batch(list[str]) -> np.ndarray`.
    solver_overrides : dict | None
        Default solver parameter overrides (alpha, gaps, iteration caps, etc.).
    """

    def __init__(
        self,
        connector: Any,
        embedder: Any,
        solver_overrides: dict[str, Any] | None = None,
        config: Any | None = None,
    ):
        self.connector = connector
        self.embedder = embedder
        self._config = config
        base_overrides = config.to_overrides() if config is not None else {}
        self.solver_overrides = {**base_overrides, **(solver_overrides or {})}
        if solve_query is None:
            raise ImportError(
                "engine.solve.solve_query not importable; expected signature: "
                "solve_query(query, k, m, connector, embedder, overrides)."
            )

    # Minimal contract for the solver (documenting expectation for future refactor):
    # solve_query(query_text: str, k: int, m: int, connector, embedder, overrides: dict) -> dict

    def query(
        self,
        query: str,
        k: int,
        m: int,
        overrides: dict[str, Any] | None = None,
        include_receipt: bool = True,
    ) -> QueryResult:
        """Execute a ranked retrieval with coherence optimization.

        Parameters
        ----------
        query : str
            Natural language query.
        k : int
            Number of reranked results to return.
        m : int
            Candidate pool size (retrieved before coherence optimization).
        overrides : dict | None
            Per-call parameter overrides (merged over client-level overrides).
        include_receipt : bool
            If False, may prune diagnostics (future optimization). Current implementation always returns diagnostics.
        """
        if k <= 0:
            return QueryResult(items=[], diagnostics={}, timings_ms={})
        if m < k:
            raise ValueError("m must be >= k")
        t0 = time.time()
        eff_overrides = {**self.solver_overrides, **(overrides or {})}
        assert solve_query is not None  # mypy narrow
        raw = solve_query(query, k, m, self.connector, self.embedder, eff_overrides)
        t1 = time.time()
        # Expected raw format (align with existing API output):
        # {
        #   "items": [ { id, score, align, baseline_align, energy_terms, neighbors }, ... ],
        #   "diagnostics": {...},
        #   "timings_ms": {...}
        # }
        items_out: list[RankedItem] = []
        for it in raw.get("items", []):
            items_out.append(
                RankedItem(
                    id=str(it.get("id")),
                    score=float(it.get("score", 0.0)),
                    align=it.get("align"),
                    baseline_align=it.get("baseline_align"),
                    energy_terms=it.get("energy_terms"),
                    neighbors=it.get("neighbors"),
                )
            )
        diagnostics = raw.get("diagnostics", {})
        timings = raw.get("timings_ms", {})
        # Add client total timing if not present
        if "client_total" not in timings:
            timings = {**timings, "client_total": (t1 - t0) * 1000.0}
        return QueryResult(items=items_out, diagnostics=diagnostics, timings_ms=timings)

    def batch_query(
        self,
        queries: list[str],
        k: int,
        m: int,
        overrides: dict[str, Any] | None = None,
    ) -> list[QueryResult]:
        """Naive batch convenience wrapper (sequential for now)."""
        return [self.query(q, k=k, m=m, overrides=overrides) for q in queries]
