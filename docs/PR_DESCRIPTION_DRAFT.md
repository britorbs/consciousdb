# Phase 2: Normalize Coherence by Default (receipt_version=2)

## Summary
Enables degree-normalized coherence attribution (symmetric normalized Laplacian) as the default path. Bumps receipt schema to version 2, keeps a configuration-only rollback (`FORCE_LEGACY_COH`), and clarifies monitoring semantics for scope divergence (`deltaH_rel_diff`).

## Key Changes
- Default `USE_NORMALIZED_COH=true` (normalized coherence active)
- Escape hatch: `FORCE_LEGACY_COH=true` forces legacy attribution during grace window
- `receipt_version` increment: 1 → 2
- Updated receipts spec (v2 active) + normalization plan + changelog
- Tests adapted: legacy assertions use escape hatch and settings reload (37 tests passing)
- Clarified `deltaH_rel_diff` = scope divergence (full candidate set trace vs returned top‑k), *not* identity error

## Validation
**Synthetic 1000-query load (Phase 1 baseline)**
- Fallback rate: 0.0%
- Scope divergence p95 (`deltaH_rel_diff`): ~0.375 (expected band 0.30–0.40)
- kappa_bound p95: ~1.75 (stable conditioning)
- Coherence fraction: 1.0 (synthetic saturation; production will vary)

**Test Suite**
- 37 tests passed (no failures)
- Energy conservation & trace identity hold within FP tolerance

## Monitoring (Post-Merge)
| Metric | Expectation | Alerting |
|--------|-------------|----------|
| `conscious_coherence_mode_total{mode}` | ≥99% normalized | Deviation implies escape hatch use or drift |
| Fallback rate | <2% (1h window) | SLO breach if ≥2% |
| `deltaH_rel_diff` p95 | Stable near 0.30–0.40 | Alert on +10% sustained (3h) |
| `kappa_bound` p95 | Stable (no step-change) | Investigate sharp increases |

## Rollback
Set `FORCE_LEGACY_COH=true` to revert instantly (no code rollback). If solver instability suspected: optionally raise `residual_tol` or reduce `iters_cap`, collect:
- fallback_rate
- p95 `deltaH_rel_diff`
- p95 `kappa_bound`
- residual histogram

## Security & Risk Mitigation
- Deterministic change; no schema migrations
- Escape hatch guarantees rapid MTTR
- Scope divergence clarified to prevent noisy “correctness” alarms

## Phase 3 Follow-Ups (Not in this PR)
- Remove legacy path & related flags
- Rename or remove `deltaH_rel_diff` (candidate: `deltaH_scope_diff`)
- Remove deprecated `coh_drop_total`
- Optionally expose both full-trace and top‑k trace if auditors require
- Consider adding ground/anchor fraction diagnostics

## Invariants (v2)
- `sum_i coherence_drop_i == deltaH_total` (within FP tolerance)
- `deltaH_trace ≥ 0` and `|deltaH_trace - deltaH_total| ≈ 0`
- Scope divergence p95 stable unless top‑k truncation policy changes
- Normalization flip does **not** increase fallback rate

## Changelog Impact
Unreleased section updated with: normalized default, receipt v2 activation, escape hatch, deprecation reminders.

## Rationale
Moves from approximate, unnormalized per-node attribution to mathematically faithful degree-normalized identity, unlocking auditable ΔH trace verification while preserving safe rollback and operational clarity.

---
Paste sections as needed into the GitHub PR body. Edit alert thresholds if production baselines deviate after initial rollout.
