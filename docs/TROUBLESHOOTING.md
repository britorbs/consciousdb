# Troubleshooting Guide

Quick reference for common operational and integration issues.

## Decision Table
| Symptom | Likely Cause | First Check | Fix |
|---------|--------------|-------------|-----|
| 401 Unauthorized | Missing / wrong API key | Request headers | Add `x-api-key` with valid key from `API_KEYS` env |
| 400 No ANN results | Connector misconfig or empty index | Connector logs, index count | Validate DSN/index; ensure embeddings ingested |
| Frequent `fallback_reason=iters_cap` | Poor conditioning / low k / high M | `cg_iters` vs `ITERS_CAP` | Increase `ITERS_CAP` moderately or tune λ parameters / reduce M |
| Frequent `fallback_reason=residual` | Residual tolerance too strict | Residual vs `RESIDUAL_TOL` | Loosen `RESIDUAL_TOL` slightly or inspect adjacency quality |
| Very low `deltaH_total` always | Easy gate always or coherence degenerate | `similarity_gap`, gate counters | Lower `SIMILARITY_GAP_MARGIN` or verify recall diversity |
| High redundancy & low diversity | MMR disabled / threshold high | `redundancy`, `used_mmr` | Enable MMR via override or lower `REDUNDANCY_THRESHOLD` |
| Adaptive α never changes | Insufficient events | Adaptive metrics | Generate feedback; ensure buffer size > warmup |
| Bandit arms all zero reward | No positive feedback events | Feedback log | Validate feedback payloads; test with manual clicks |
| Dimension mismatch at startup | Wrong embedder vs stored vectors | `/healthz` output | Set `EXPECTED_DIM` or update embeddings source |
| High latency spike in solve | Large expansion or high M | Timings breakdown | Adjust `EXPAND_WHEN_GAP_BELOW` or reduce M |
| Missing neighbors in items | k too small or mutual filter strict | `KNN_K`, adjacency stats | Increase `KNN_K` (with perf tradeoff) |

## Detailed Scenarios
### 1. Solver Hitting Iteration Cap
- Confirm `cg_iters` equals `ITERS_CAP` in diagnostics.
- Examine redundancy: overly dense subgraph may slow convergence.
- Actions: raise cap (short term), consider reducing λ_Q (anchor) if dominating, inspect A's degree distribution.

### 2. Residual Too High
- Residual > 2× tolerance triggers warning.
- Check if expansion triggered producing larger context.
- Try lowering expansion trigger or tightening similarity threshold for edges.

### 3. Persistent Fallbacks After Upgrade
- Compare new vs previous commit: adjacency logic, λ constants.
- Inspect audit lines for shift in `iter_max` or `residual`.
- Rollback if regression confirmed; open issue with logs + metrics snapshot.

### 4. Adaptive Not Applying
- `ENABLE_ADAPTIVE=true` but `applied_alpha` remains manual.
- Ensure `ENABLE_ADAPTIVE_APPLY=true` and warmup events reached.
- Validate events count via `adaptive_events_buffer_size` gauge.

### 5. Empty or Small ANN Result Set
- Connector may be returning fewer candidates (M > available docs).
- Adjust ingestion or reduce requested M.
- Confirm no silent errors in connector (add debug log temporarily).

### 6. Unexpected High Redundancy & MMR Ineffective
- If `used_mmr=false`: threshold not crossed or K ≤ 8.
- Increase K or force MMR via override for experimentation.

### 7. Audit Log Missing Signature
- Check `AUDIT_HMAC_KEY` presence in environment.
- If rotating key, ensure application restart to load new key.

### 8. Bandit Starvation (Single Arm Dominates Early)
- Ensure all arms pulled at least once (cold start). UCB logic should explore.
- If not, verify arm enumeration in state file.

## Collecting Diagnostic Bundle
For support requests gather:
- 3–5 sample `audit.log` lines (redact queries if sensitive)
- `/metrics` scrape snippet (relevant counters/histograms summary)
- Example `/query` request & response (k, m, diagnostics)
- `adaptive_state.json` (if adaptive enabled)
- Environment variable listing excluding secrets

## Feedback Payload Validation
A valid feedback request requires:
```json
{ "query_id": "...", "accepted_id": "doc123", "clicked_ids": ["doc123"] }
```
Missing `query_id` → feedback ignored (no crash). Ensure you map the `query_id` from prior `/query` response.

## Related
- `OPERATIONS.md`
- `CONFIGURATION.md`
- `ARCHITECTURE.md`
- `ADAPTIVE.md`
