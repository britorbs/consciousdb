from __future__ import annotations

"""Prometheus metrics registry and helpers.

Centralizes metric definitions to avoid duplicate time series in tests.
"""
from prometheus_client import Counter, Gauge, Histogram  # noqa: E402

# Buckets tuned for sub-ms to multi-second latencies (log-ish progression)
QUERY_LATENCY_MS = Histogram(
    "conscious_query_latency_ms",
    "Total /query request latency (milliseconds)",
    buckets=(0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500, 1000, 2000, 5000),
)
GRAPH_BUILD_MS = Histogram(
    "conscious_graph_build_ms",
    "Graph construction time (milliseconds)",
    buckets=(0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500),
)
SOLVE_MS = Histogram(
    "conscious_solve_ms", "Solver time (milliseconds)", buckets=(0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500)
)
RANK_MS = Histogram(
    "conscious_rank_ms", "Ranking (scoring + diversification) time (milliseconds)", buckets=(0.2, 0.5, 1, 2, 5, 10, 20)
)
ITERATIONS = Histogram(
    "conscious_solver_iterations", "Per-dimension solver iteration counts", buckets=(1, 2, 3, 5, 8, 13, 21, 34)
)
REDUNDANCY = Histogram(
    "conscious_redundancy",
    "Average pairwise cosine redundancy of preliminary top-k",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
)
MMR_APPLIED = Counter("conscious_mmr_applied_total", "Count of queries where MMR diversification executed")
QUERY_COUNT = Counter("conscious_query_total", "Total query requests processed", ["fallback", "easy_gate", "coh_gate"])

# New pivot metrics
DELTAH_TOTAL = Histogram(
    "conscious_deltaH_total",
    "Distribution of coherence improvement (deltaH_total)",
    buckets=(0.0, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
)
GATE_EASY = Counter("conscious_gate_easy_total", "Count of queries short-circuited by easy gate")
GATE_LOW_IMPACT = Counter(
    "conscious_gate_low_impact_total", "Count of queries where coherence drop below threshold (deltaH gate)"
)
GATE_FALLBACK = Counter("conscious_gate_fallback_total", "Count of queries that entered fallback path")
FALLBACK_REASON = Counter(
    "conscious_fallback_reason_total",
    "Count of fallback occurrences by reason (label 'reason' can be multi-token comma joined or 'none')",
    ["reason"],
)
RECEIPT_COMPLETENESS = Gauge(
    "conscious_receipt_completeness_ratio",
    "Fraction of optional receipt fields present (deltaH_total, neighbors, redundancy)",
)


# Scope difference distribution (full candidate set trace vs returned top-k component sum)
DELTAH_SCOPE_DIFF = Histogram(
    "conscious_deltaH_scope_diff",
    "Relative scope difference between full candidate-set ΔH trace and top-k component-sum trace",
    buckets=(1e-6, 1e-5, 1e-4, 5e-4, 1e-3, 5e-3, 1e-2),
)

MAX_RESIDUAL = Gauge("conscious_solver_max_residual", "Max relative residual observed for last query")

# Adaptive metrics
ADAPTIVE_FEEDBACK = Counter(
    "conscious_adaptive_feedback_total",
    "Feedback events counted by positivity",
    ["positive"],
)
ADAPTIVE_SUGGESTED_ALPHA = Gauge(
    "conscious_adaptive_suggested_alpha",
    "Most recent suggested alpha_deltaH (if any)",
)
ADAPTIVE_BUFFER_SIZE = Gauge(
    "conscious_adaptive_events_buffer_size",
    "Current number of adaptive feedback events in memory",
)

# Bandit metrics
BANDIT_ARM_SELECT = Counter(
    "conscious_bandit_arm_select_total",
    "Selections of bandit alpha arms",
    ["alpha"],
)
BANDIT_ARM_REWARD = Gauge(
    "conscious_bandit_arm_avg_reward",
    "Average reward for bandit alpha arm",
    ["alpha"],
)

# Adaptive persistence failure metrics
ADAPTIVE_STATE_LOAD_FAILURE = Counter(
    "conscious_adaptive_state_load_failure_total",
    "Count of failures when loading adaptive state from disk",
)
ADAPTIVE_STATE_SAVE_FAILURE = Counter(
    "conscious_adaptive_state_save_failure_total",
    "Count of failures when saving adaptive state to disk",
)


def observe_bandit_snapshot(arms):
    for arm in arms:
        if arm.pulls > 0:
            BANDIT_ARM_REWARD.labels(alpha=str(arm.alpha)).set(arm.reward_sum / arm.pulls)


def observe_query(
    *,
    latency_ms: float,
    graph_ms: float,
    solve_ms: float,
    rank_ms: float,
    iterations: list[int],
    redundancy: float,
    mmr_used: bool,
    fallback: bool,
    easy_gate: bool,
    coh_gate: bool,
    max_residual: float,
    delta_h_total: float | None = None,
    low_impact_gate: bool = False,
    neighbors_present: bool | None = None,
) -> None:
    """Record a single query's metrics.

    Added in pivot Phase B: deltaH_total histogram, gate counters, receipt completeness gauge.
    """
    QUERY_LATENCY_MS.observe(latency_ms)
    GRAPH_BUILD_MS.observe(graph_ms)
    SOLVE_MS.observe(solve_ms)
    RANK_MS.observe(rank_ms)
    for it in iterations:
        ITERATIONS.observe(it)
    REDUNDANCY.observe(redundancy)
    if mmr_used:
        MMR_APPLIED.inc()
    QUERY_COUNT.labels(
        fallback=str(fallback).lower(),
        easy_gate=str(easy_gate).lower(),
        coh_gate=str(coh_gate).lower(),
    ).inc()
    MAX_RESIDUAL.set(max_residual)
    # New metrics
    if delta_h_total is not None:
        DELTAH_TOTAL.observe(delta_h_total)
    if easy_gate:
        GATE_EASY.inc()
    if low_impact_gate:
        GATE_LOW_IMPACT.inc()
    if fallback:
        GATE_FALLBACK.inc()
        # Fallback reason counter is incremented explicitly in the query handler with precise labels.
    # Completeness heuristic: count how many receipt fields present out of 3
    present = 0
    denom = 3
    if delta_h_total is not None:
        present += 1
    if redundancy is not None:
        present += 1
    if neighbors_present:
        present += 1
    RECEIPT_COMPLETENESS.set(present / denom)


def observe_adaptive_feedback(*, positive: bool, buffer_size: int, suggested_alpha: float | None):
    ADAPTIVE_FEEDBACK.labels(positive=str(positive).lower()).inc()
    ADAPTIVE_BUFFER_SIZE.set(buffer_size)
    if suggested_alpha is not None:
        ADAPTIVE_SUGGESTED_ALPHA.set(suggested_alpha)
