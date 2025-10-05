from __future__ import annotations
from typing import List, Optional, Dict, Any
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
    activation: float
    neighbors: List[Neighbor] = []
    energy_terms: EnergyTerms
    excerpt: Optional[str] = None

class Diagnostics(BaseModel):
    similarity_gap: float
    coh_drop_total: float
    # New pivot alias: deltaH_total (canonical name for coherence energy improvement)
    deltaH_total: float | None = None  # will mirror coh_drop_total; provided for forward compatibility
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
    timings_ms: Dict[str, float]
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

class QueryResponse(BaseModel):
    items: List[Item]
    diagnostics: Diagnostics
    query_id: str | None = None
    version: str = "v2.0.0"

class FeedbackRequest(BaseModel):
    query_id: str
    clicked_ids: List[str] = []
    accepted_id: Optional[str] = None
    latency_ms: Optional[int] = None
