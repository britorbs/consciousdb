# Adaptive & Bandit Systems

Deep dive into alpha suggestion (adaptive) and UCB1 bandit exploration.

This document now also formalizes reward semantics and the relationship between baseline alignment, uplift, and coherence improvement (ΔH / deltaH_total).

## Goals
- Stabilize ranking quality across heterogeneous corpora without manual α tuning.
- Explore alternative α values to improve acceptance/click reward.
- Maintain deterministic fallback when disabled (feature flags off).

## State Schema (adaptive_state.json)
```json
{
  "suggested_alpha": 0.12,
  "events": [ {"deltaH_total": 2.31, "redundancy": 0.29, "positive": true }, ... ],
  "bandit_arms": {
    "0.05": {"n": 11, "reward_sum": 7},
    "0.10": {"n": 10, "reward_sum": 5},
    "0.15": {"n": 9, "reward_sum": 6}
  },
  "bandit_enabled": true
}
```

## Alpha Suggestion Algorithm
Parameters (implicit defaults):
- Buffer size: 200 events (ring)
- Warmup: 15 events before first suggestion
- Update cadence: every 5 new events
- Correlation thresholds: θ_hi=+0.12, θ_lo=-0.12 (example) – adjust in code if needed
- Step size: ±0.01–0.02 (bounded)
- Bounds: α ∈ [0.02, 0.5]

Pseudo-code:
```
if len(events) < warmup: return None
if (events_since_last_update % update_stride) != 0: return previous
corr = pearson(deltaH_total, positive)
if variance(deltaH_total) < eps: return previous
if corr > θ_hi: alpha = min(alpha + step_up, max_alpha)
elif corr < θ_lo: alpha = max(alpha - step_down, min_alpha)
else: alpha = alpha
```

## Bandit (UCB1) over α Arms
Arms: fixed discrete set (e.g., [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]).
Selection after each query (when adaptive enabled):
\[ score_i = \bar{r}_i + c \sqrt{ \frac{2 \ln N}{n_i}} \]
Where \( \bar{r}_i = reward\_sum_i / n_i \), N = total pulls, n_i = pulls for arm i, c=1 (implicit).

Reward assignment (feedback):
```
reward = 1.0 if (accepted_id present OR any clicks) else 0.0
update arm stats; persist state
```

## Precedence for applied_alpha
1. Adaptive suggestion (if `ENABLE_ADAPTIVE_APPLY=true` and suggestion non-null)
2. Bandit selection (if enabled)
3. Manual override (`overrides.alpha_deltaH` in request)
4. Environment default `ALPHA_DELTAH`

`diagnostics.alpha_source` enumerates: `suggested`, `bandit`, `manual`.

## Reward Semantics & Scoring Signals

We expose three distinct but related quantitative signals:

| Signal | Symbol | Definition | Scope | Usage |
|--------|--------|------------|-------|-------|
| Baseline Alignment | a_i^base | Raw cosine similarity of original embedding x_i with query y | Per-item | Comparator for uplift; fallback score when coherence gate off |
| Smoothed Alignment | a_i^smooth | Cosine similarity of solved embedding q_i with y | Per-item | Blended with standardized coherence_drop via α |
| Coherence Improvement | ΔH = Σ_i coherence_drop_i | Global | Measures structural uplift (energy reduction) induced by solver |
| Per-item Uplift | u_i = a_i^smooth - a_i^base | Per-item | Diagnostic for how much structure benefited individual result |
| Average Uplift | ū = mean_i u_i (returned items) | Global (returned subset) | Surfaced as `uplift_avg` for coarse efficiency snapshot |
| Solver Efficiency | η = ΔH / solve_ms | Global | Normalizes structural gain by cost (ms) enabling runtime vs benefit trade-offs |
| Component Count | C | Number of connected components in local kNN subgraph | Graph | Fragmentation diagnostic (higher C => low connectivity) |
| Largest Component Ratio | ρ = |V_max| / N | Graph | Cohesion measure (near 1 ⇒ well-connected) |

Interpretation guidelines:
- High ΔH with modest ū can indicate coherent global smoothing where few individual items shift alignment dramatically (broad subtle uplift).
- High ū with low ΔH suggests a small subset benefited strongly—potentially increasing α may overweight structural signal; monitor correlation.
- Low η (efficiency) under latency pressure may justify lowering k or adjusting α if coherence gate rarely triggers.

### Reward Mapping
Feedback event reward (bandit + correlation) is currently:
```
reward = 1.0 if (accepted_id present OR any clicks) else 0.0
```
We DO NOT weight reward by uplift or ΔH to avoid reinforcing degenerate strategies that overfit to structural artifacts; coherence signals are treated as contextual features, not reward multipliers.

Future variants may consider scaled rewards (e.g., reward * sigmoid(ū)) but only after guardrails for pathological boosts (e.g., adversarial embeddings) are in place.

### Safety Bounds
- α bounds [0.02, 0.5] prevent over-dominance of either coherence (z-scored) or alignment terms.
- Uplift values are unconstrained but monitored; if |ū| > 0.6 (empirical outlier) consider flagging for investigation (future metric / alert TBD).
- Component fragmentation: if C > 0.2N (very fragmented), solver efficiency may drop; a future heuristic could trigger reduced k or early exit.

### When to Trust Uplift
Trust per-item uplift (u_i) when:
1. `used_deltaH` is true (coherence gate passed)
2. Residual ≤ 2× tolerance (solver converged)
3. Largest component ratio ρ ≥ 0.6 (graph sufficiently connected)

If any fail, treat uplift as advisory only (avoid using for automated downstream boosts).

## Baseline vs. Smoothed Alignment in Ranking
Ranking blend (when coherence active):
```
score_i = α * z(coherence_drop_i) + (1 - α) * a_i^smooth
```
Baseline alignment a_i^base is not in the blend directly; it forms the counterfactual to quantify uplift. This separation ensures structural gain measurement without double-counting in scoring.

## Extensibility Hooks
Planned optional reward shaping fields (NOT active yet):
- `implicit_depth_bonus` – dampens reward if accepted item was already ranked very high (reduces trivial wins)
- `novelty_score` – penalize repeated click IDs across queries to encourage diversity exploration.

## Metrics Alignment (New Diagnostics)
Expose or planned metrics (some may be added if operational need confirmed):
- solver_efficiency (gauge or distribution) – currently internal diagnostic, may promote to Prometheus.
- component_count & largest_component_ratio – fragmentation monitoring; candidate for alerting if sustained deviation.
- uplift_avg – high-level structural benefit health.

All remain additive and optional; absent values (None) are not treated as errors.

## Failure Modes & Safeguards
| Failure | Mitigation |
|---------|------------|
| State load IO error | Logged warning; metrics increment; start with defaults |
| Correlation unstable (low variance) | No update applied |
| Bandit arm starvation | UCB ensures exploration via ln(N)/n term |
| File corruption | JSON parse error -> ignore & reinitialize |
| Overfitting to noise | Small step size + buffer window smoothing |

## Reproducibility
To replay a historical decision:
1. Locate audit log line for `query_id`.
2. Extract `applied_alpha`, `suggested_alpha`, `alpha_source`.
3. Re-run solver offline with same ANN recall set and α = `applied_alpha` to reproduce ranking order.

## Disabling Adaptive Features
Set `ENABLE_ADAPTIVE=false` (and `ENABLE_BANDIT=false`) for fully deterministic scoring given α.

## Future Enhancements
- Thompson sampling bandit with Beta/Bernoulli posterior
- Contextual bandit (features: redundancy, deltaH_total)
- Confidence interval gating to freeze α within stable band
- Adaptive arm set resizing (add/remove arms based on reward deltas)

## Related
- `CONFIGURATION.md`
- `OPERATIONS.md`
- `ARCHITECTURE.md`
