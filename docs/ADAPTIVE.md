# Adaptive & Bandit Systems

Deep dive into alpha suggestion (adaptive) and UCB1 bandit exploration.

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
