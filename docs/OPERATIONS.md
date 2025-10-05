# Operations & Observability

Runbook for metrics, logging fields, SLO guardrails, and audit integrity.

## Metrics Dictionary (Prometheus)
| Metric | Type | Labels | Meaning / Action |
|--------|------|--------|------------------|
| `conscious_query_latency_ms` | Histogram | path? (implicit) | End-to-end latency distribution; watch P95 budget |
| `conscious_graph_build_ms` | Histogram | – | Time to build local kNN graph |
| `conscious_solve_ms` | Histogram | – | CG solve time (anchored baseline) |
| `conscious_rank_ms` | Histogram | – | Time for ranking & redundancy/MMR |
| `conscious_cg_iterations` | Histogram | – | Distribution of iterations per dimension block |
| `conscious_deltaH_total` | Histogram | – | Distribution of coherence improvements; sudden collapse ⇒ recall quality issues |
| `conscious_redundancy` | Histogram | – | Average pairwise similarity of provisional top-k; high + low uplift may warrant MMR |
| `conscious_fallback_reason_total` | Counter | reason | Counts fallbacks by reason (`forced`, `iters_cap`, `residual`, `none`) |
| `conscious_gate_easy_total` | Counter | – | Easy-query skips (vector-only) |
| `conscious_gate_low_impact_total` | Counter | – | Low-impact gate activations |
| `conscious_mmr_applied_total` | Counter | – | Times MMR diversification applied |
| `conscious_adaptive_feedback_total` | Counter | positive | Feedback events processed |
| `conscious_adaptive_suggested_alpha` | Gauge | – | Current suggested alpha (adaptive) |
| `conscious_adaptive_events_buffer_size` | Gauge | – | Size of adaptive event ring buffer |
| `conscious_bandit_arm_select_total` | Counter | alpha | Times each alpha arm selected |
| `conscious_bandit_arm_avg_reward` | Gauge | alpha | Mean reward per arm (bandit) |
| `conscious_adaptive_state_load_failure_total` | Counter | – | Failed loads at startup |
| `conscious_adaptive_state_save_failure_total` | Counter | – | Failed persistence attempts |

## Key Log Fields (JSON Structured)
| Field | Source | Meaning |
|-------|--------|---------|
| `request_id` | middleware | Correlate logs across phases |
| `gap` | query log | Similarity gap used for easy gate decision |
| `coh_drop_total` | query log | (Deprecated alias) old coherence aggregate |
| `coh_drop_total` | query log | Use `deltaH_total` going forward |
| `fallback` | query log | True when any solver/gating fallback occurred |
| `fallback_reason` | query log | Comma reasons; diagnose stability |
| `iter_max` | diagnostics | Maximum CG iterations used |
| `residual` | diagnostics | Final residual; >2× tol triggers warning |
| `redundancy` | diagnostics | Redundancy value before optional MMR |
| `used_deltaH` | diagnostics | Whether coherence component contributed |
| `used_mmr` | diagnostics | MMR applied |
| `used_expand_1hop` | diagnostics | 1-hop context expansion used |

## SLO Guardrails
| Aspect | Target | Action When Breached |
|--------|--------|----------------------|
| P95 latency | ≤400ms (K≤8) | Inspect segment histograms; consider lowering M or early gating tuning |
| Fallback rate | <5% (excluding forced) | Check reasons; iter caps/residual tolerance adjustments or investigate solver convergence |
| Iteration max | < iters_cap | If hitting cap: assess Laplacian conditioning / adjust λ parameters |
| Residual | ≤ 2× residual_tol | Log warnings; potential need to reduce gap threshold or adjust preconditioner |
| Redundancy | Monitor | If high with low uplift, enable conditional MMR or tune threshold |

## Incident Triage Checklist
1. Confirm latency spike vs baseline metrics (graph_build vs solve vs rank).
2. Check fallback reasons distribution – spikes in `residual` or `iters_cap`?
3. Inspect adaptive state size & suggested_alpha drift (gauge stability).
4. Tail recent audit log lines (`audit.log`) for unusual deltaH_total collapse.
5. Validate connector health (ANN returning empty / fewer than expected?).

## Audit Log Integrity Verification
If `AUDIT_HMAC_KEY` enabled:
1. Read each JSON line; extract and temporarily remove `signature`.
2. Canonicalize remaining JSON with sorted keys.
3. Compute `hex = HMAC_SHA256(key, canonical_bytes)`.
4. Compare constant-time; flag mismatches.

Pseudo-Python:
```python
import hmac, hashlib, json
key=b"<AUDIT_HMAC_KEY>"
with open("audit.log") as f:
    for ln in f:
        obj=json.loads(ln)
        sig=obj.pop("signature", None)
        body=json.dumps(obj, sort_keys=True, separators=(",",":"))
        calc=hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
        assert sig==calc, "tamper detected"
```

## Deployment Hardening Checklist
| Item | Status | Notes |
|------|--------|-------|
| API key auth enabled |  | Set `API_KEYS` |
| Audit log HMAC on |  | Set `AUDIT_HMAC_KEY` |
| Adaptive off (if deterministic mode) |  | Disable `ENABLE_ADAPTIVE` for reproducible bench |
| Resource limits (CPU/mem) set |  | Prevent noisy neighbor effects |
| Log shipping configured |  | Forward audit/logs to central store |
| Secrets manager integration |  | No raw secrets in env files committed |
| Network egress restricted |  | Limit only to vector DB endpoints |

## Playbooks
### High Residual Fallbacks Spike
1. Confirm residual reasons in metrics.
2. Increase `ITERS_CAP` short-term (observability first).
3. Inspect graph degree distribution (is k lowered inadvertently?).
4. Consider lowering `EXPAND_WHEN_GAP_BELOW` to reduce context size.

### Sudden Uplift Drop (deltaH_total near zero)
1. Validate connector returning fewer results (ANN issue).
2. Check if easy gate triggering excessively (gap metric).
3. Ensure adaptive suggested_alpha not pinned at 0 or 1 (bandit starvation).

### Redundancy High Despite MMR Disabled
1. Evaluate enabling conditional MMR (`ENABLE_MMR=true` or override).
2. Increase k diversity via adjusting recall M or decreasing `ALPHA_DELTAH` if overscoring coherence.

## Related
- `CONFIGURATION.md`
- `SECURITY.md`
- `ADAPTIVE.md`
- `RECEIPTS.md`
