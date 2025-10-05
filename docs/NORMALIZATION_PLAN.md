# Normalized Coherence & Energy Gap Implementation Plan (Temporary Doc)

Status: DRAFT (to be merged incrementally). This file captures the migration path to a mathematically rigorous, normalized coherence attribution and an audit-grade energy gap verification identity.

## Goals
1. Align per-node coherence attribution with the normalized Laplacian \(L_{sym} = I - D^{-1/2} A D^{-1/2}\).
2. Provide an exact, non-negative energy gap identity: \n  \[ \Delta H = H_y(X;A) - H_y(Q^*;A) = \operatorname{Tr}((X-Q^*)^\top M (X-Q^*)) \ge 0. \]
3. Surface spectral conditioning guidance via \n  \[ \kappa(M) \le \frac{\lambda_G + 2\lambda_C + \lambda_Q\|b\|_\infty}{\lambda_G}. \]
4. Stage rollout with a feature flag (`USE_NORMALIZED_COH`) before bumping `receipt_version`.
5. Preserve backward compatibility until downstream consumers update.

## Current vs Target
| Aspect | Current (v1 receipts) | Target (flag ON) |
|--------|-----------------------|------------------|
| Laplacian in attribution | Uses unnormalized differences \(\|q_i - q_j\|^2\) while code constructs normalized Laplacian | Consistent normalized differences \(\|q_i/\sqrt{d_i} - q_j/\sqrt{d_j}\|^2\) |
| Per-node coherence sum fidelity | Approximate (sums to ΔH numerically but not exact identity) | Exact match (up to FP tolerance) with ΔH trace identity |
| Energy gap verification | Implicit (difference of totals) | Explicit: `deltaH_trace` + relative diff |
| Conditioning surfaced | None | `kappa_bound` diagnostic |
| Anchor distribution | ReLU normalize | (Future) optional softmax temperature τ |
| Attribution share telemetry | Not available | `coherence_fraction` = coherence component / total ΔH |
| Adoption metric | None | `conscious_coherence_mode_total{mode}` counter to monitor rollout |

## Phased Implementation
### Phase 0 (This PR scope)
- Add this plan.
- Introduce environment flag `USE_NORMALIZED_COH` (default: `false`).
- Implement normalized path (post-solve) computing per-node normalized coherence deltas in parallel to legacy; only returned if flag true.
- Add energy gap identity computation (trace form) and diagnostics fields: `deltaH_trace`, `deltaH_rel_diff`, `kappa_bound` (all optional, only when full solver path executed).
- Tests: ensure flag OFF leaves current outputs unchanged; flag ON produces non-negative ΔH and small relative diff.

### Phase 1 (Enable & Observe)
- Default flag remains false; internal environments run with true to accumulate empirical differences.
- Log both legacy and normalized sums (warn if relative diff > 1e-3).

### Phase 2 (Receipt Version Bump)
- Set default `USE_NORMALIZED_COH=true`.
- Bump `receipt_version` to 2.
- Deprecate legacy per-node path; keep compatibility shim for one minor release (mapping `coherence_drop_legacy` if needed).

### Phase 3 (Cleanup)
- Remove legacy code path & flag.
- Update docs / whitepaper sections with normalized formulas only.

## Data Structures & Computation Sketch
Given recalled set size N and embedding dimension d (moderate), normalized difference computation is memory feasible.

```
d = A.sum(axis=1) + 1e-12
inv_sqrt_d = 1.0 / np.sqrt(d)
Xn = X * inv_sqrt_d[:, None]
Qn = Q_star * inv_sqrt_d[:, None]
rows, cols = np.nonzero(A)
w = A[rows, cols]
base_diff = Xn[rows] - Xn[cols]
star_diff = Qn[rows] - Qn[cols]
edge_delta = w * ( (base_diff**2).sum(1) - (star_diff**2).sum(1) )
coh_norm = np.zeros(N, dtype=np.float32)
# Each undirected relation appears twice if A symmetric; use 0.5 split
np.add.at(coh_norm, rows, 0.5 * edge_delta)
np.add.at(coh_norm, cols, 0.5 * edge_delta)
coh_norm *= lambda_C
```

## Energy Gap Identity Decomposition
Let: \( M = \lambda_G I + \lambda_C L_{sym} + \lambda_Q B \).
We avoid forming dense M:
- Ground term: \( \lambda_G \|X-Q^*\|_F^2 \)
- Laplacian term: reuse normalized edge deltas but with \(Q^*\) vs X difference applied to both sides if needed.
- Anchor term: depends on anchor formulation. If objective includes \(\lambda_Q \sum_i b_i \|q_i - y\|^2\):
  - Expand difference using (X - Q*) and y.
Provide docstring citing final chosen anchor energy expression.

## Diagnostics Fields (Proposed Additions)
| Field | Meaning | Conditionally Present |
|-------|---------|-----------------------|
| `deltaH_trace` | Trace-form computed ΔH | Full solve & flag ON (or always if cheap) |
| `deltaH_rel_diff` | |ΔH - ΔH_trace| / (ΔH + 1e-12) | When both computed |
| `kappa_bound` | Upper bound on condition number | Full solve |
| `coherence_mode` | `normalized` or `legacy` | Always |
| `coherence_fraction` | Fraction of ΔH attributable to coherence (edge/Laplacian) term | When ΔH>0 |

## Receipt Versioning
- v1: legacy unnormalized per-node deltas.
- v2: normalized coherence primary; legacy removed.
- Communicate in `RECEIPTS.md` with side-by-side example.

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Downstream breaks due to changed magnitudes | Feature flag; version bump later |
| Performance regression for large N | Reuse A sparsity (k small) so O(kN d) acceptable |
| Numerical drift causing false diffs | Tolerance guard (1e-4) before logging warnings |

## Open Questions
1. Anchor term exact form in current energy (confirm implementation before final trace identity code).
2. Whether to supply per-item normalized coherence components separately (`coherence_drop_norm`). For now, reuse `coherence_drop` name only when flag ON.
3. Add Prometheus metrics for `kappa_bound`? (Defer until operational need.)
4. Whether to expose ground / anchor fractions alongside `coherence_fraction` for deeper audits.

## Immediate Next Steps
- Implement flag & dual computation path.
- Integrate diagnostics fields (flag OFF => legacy only, but still compute `kappa_bound`).
- Write tests for non-negativity & relative diff.
- Add coherence adoption & fraction telemetry (DONE).
- Tighten conservation test once quadratic identity validated across corpora.

## Flag Flip & Receipt Version Bump Plan
Monitoring Gates:
- Target: ≥95% of production queries run successfully with `coherence_mode=normalized` and `deltaH_rel_diff < 1e-3` over 7 rolling days.
- Alert threshold: Any day with >0.5% queries showing `deltaH_rel_diff > 5e-3` or mean `coherence_fraction` shift >5% vs prior week.

Execution:
1. Phase 1 (current): Collect counters (`conscious_coherence_mode_total`).
2. Phase 2 prep: Shadow-run normalized in parallel for 100% queries; log comparisons (already partially via `deltaH_rel_diff`).
3. Flip: Set `USE_NORMALIZED_COH=true` by default; increment `receipt_version` to 2 in responses.
4. Grace: Keep legacy path code guarded by env (`FORCE_LEGACY_COH=true`) for one minor release to allow emergency rollback.
5. Cleanup: Remove legacy code & `deltaH_rel_diff`, keep `coherence_fraction`.

Risk Mitigations:
- If anomaly detected, auto-disable via dynamic config flag; emit structured anomaly log (`norm_mismatch_anomaly`).
- Retain last 24h distribution snapshots for deltaH_total & coherence_fraction to support RCA.

---
This document will be removed after Phase 2 once normalization is the default.
