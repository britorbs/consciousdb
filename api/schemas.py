from __future__ import annotations

from pydantic import BaseModel, Field


class Overrides(BaseModel):
    alpha_deltaH: float = 0.1
    similarity_gap_margin: float = 0.15
    coh_drop_min: float = 1e-2
    expand_when_gap_below: float = 0.08
    iters_cap: int = 20
    residual_tol: float = 1e-3
    force_fallback: bool = False
    use_mmr: bool = False


class QueryRequest(BaseModel):
    query: str
    k: int = Field(8, ge=1, le=50)
    m: int = Field(400, ge=100, le=5000)
    overrides: Overrides = Overrides()
    # receipt_detail = 1 returns full neighbors + energy terms; 0 is lightweight (omit neighbors, zeroed energy terms)
    receipt_detail: int = Field(1, ge=0, le=1)


class Neighbor(BaseModel):
    id: str
    w: float


class EnergyTerms(BaseModel):
    coherence_drop: float
    anchor_drop: float
    ground_penalty: float


class Item(BaseModel):
    id: str
    score: float
    align: float
    # Alignment before coherence optimization (baseline) for uplift analysis
    baseline_align: float | None = None
    # uplift = align - baseline_align
    uplift: float | None = None
    activation: float
    neighbors: list[Neighbor] = []
    energy_terms: EnergyTerms
    excerpt: str | None = None


class Diagnostics(BaseModel):
    similarity_gap: float
    coh_drop_total: float
    # New pivot alias: deltaH_total (canonical name for coherence energy improvement)
    deltaH_total: float | None = None  # will mirror coh_drop_total; provided for forward compatibility
    # Graph component metrics
    component_count: int | None = None
    largest_component_ratio: float | None = None
    # Solver efficiency (deltaH_total per ms of solve time)
    solver_efficiency: float | None = None
    # Average uplift across returned items
    uplift_avg: float | None = None
    # Adaptive suggestion: optional next alpha_deltaH to try (feature-gated)
    suggested_alpha: float | None = None
    # Applied alpha (post automatic application or bandit); source annotation
    applied_alpha: float | None = None
    alpha_source: str | None = None  # one of: "manual", "suggested", "bandit", None
    used_deltaH: bool
    used_expand_1hop: bool
    cg_iters: int
    residual: float
    fallback: bool
    timings_ms: dict[str, float]
    receipt_version: int | None = None
    edge_count: int | None = None
    avg_degree: float | None = None
    iter_min: int | None = None
    iter_max: int | None = None
    iter_avg: float | None = None
    iter_med: float | None = None
    redundancy: float | None = None
    used_mmr: bool | None = None
    weights_mode: str | None = None
    fallback_reason: str | None = None
    # Normalization migration diagnostics (feature-flagged)
    deltaH_trace: float | None = None  # trace identity computed delta
    # Phase 1 dual-scope traces
    deltaH_trace_topk: float | None = None  # top-k component-sum scope (returned items)
    deltaH_trace_full: float | None = None  # full candidate set quadratic identity scope
    deltaH_scope_diff: float | None = None  # Relative scope difference full vs top-k trace
    kappa_bound: float | None = None  # spectral condition estimate (upper bound)
    # coherence_mode removed (always normalized); field dropped to reduce payload size
    coherence_fraction: float | None = None  # share of total ΔH attributable to coherence term


class QueryResponse(BaseModel):
    items: list[Item]
    diagnostics: Diagnostics
    query_id: str | None = None
    version: str = "v2.0.0"


class FeedbackRequest(BaseModel):
    query_id: str
    clicked_ids: list[str] = []
    accepted_id: str | None = None
    latency_ms: int | None = None
