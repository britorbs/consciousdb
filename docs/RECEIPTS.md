# Explainability Receipts (v1)

The retrieval response includes a structured receipt describing how the coherence optimization affected ranking. This document defines version 1 of the receipt fields and evolution guidelines.

## Versioning
`receipt_version` in diagnostics indicates schema version. Breaking changes increment this integer. Additive fields do **not** bump the version. Deprecated fields are kept for ≥1 minor release before removal.

## Core Scalars
| Field | Source | Meaning |
|-------|--------|---------|
| `deltaH_total` | diagnostics | Total coherence (energy) improvement vs baseline (sum of per-item coherence_drop). |
| `coh_drop_total` | diagnostics | Legacy alias for `deltaH_total` (deprecated; removal scheduled). |
| `redundancy` | diagnostics | Mean pairwise cosine similarity among provisional top-k before diversification (excludes diagonal). |
| `similarity_gap` | diagnostics | Gap between top similarity and 10th (or last available) used for easy gate heuristic. |
| `fallback` | diagnostics | True if any fallback predicate triggered. |
| `fallback_reason` | diagnostics | Comma-separated predicates: `forced`, `iters_cap`, `residual`. |
| `suggested_alpha` | diagnostics | Suggested alpha from adaptive correlation (present when ENABLE_ADAPTIVE and warmup complete). |
| `applied_alpha` | diagnostics | Alpha actually used in ranking (manual, suggested, or bandit arm). |
| `alpha_source` | diagnostics | One of `manual`, `suggested`, `bandit`. |
| `query_id` | diagnostics | Identifier for correlating feedback. |
| `coherence_mode` | diagnostics | Coherence attribution mode (`legacy` or `normalized`, Phase 0 feature-flagged). |
| `deltaH_trace` | diagnostics | Trace-form ΔH (currently mirrors `deltaH_total` in Phase 0; will become exact identity). |
| `kappa_bound` | diagnostics | Estimated upper bound on condition number of solve operator (stability diagnostic). |
| `coherence_fraction` | diagnostics | Fraction of total ΔH attributable to coherence (Laplacian) term (0–1). |

## Per-Item Fields
Each item has:
- `score`: Final blended score ( may include z(coherence_drop) + smoothed alignment ).
- `align`: Smoothed alignment (cosine) after optimization (or vanilla cosine if gated).
- `activation`: L2 norm of (Q*_i - original embedding) indicating how much the solve adjusted the vector.
- `energy_terms`:
  - `coherence_drop`: Node's contribution to ΔH (positive is good; larger means more local smoothing benefit).
  - `anchor_drop`: Anchor (query) energy component change (negative values represent attraction to query embedding).
  - `ground_penalty`: Regularization component preventing drift from original embedding.
- `neighbors`: Up to 5 neighbor objects `{id, w}` where `w` is adjacency weight (cosine similarity in v1).

## Gates & SLOs
| Aspect | Condition | Effect |
|--------|-----------|--------|
| Easy gate | similarity_gap > similarity_gap_margin | Skips solve; returns vector-only ranking. |
| Low-impact gate | deltaH_total < coh_drop_min | Uses vector-only scoring (coherence contribution disabled). |
| Iteration SLO | cg_iters > 12 | Warning log `slo_iter_guard`. |
| Residual SLO | residual > 2× residual_tol | Warning log `slo_residual_guard`. |

## Metrics Mapping (Prometheus)
| Metric | Relation |
|--------|----------|
| `conscious_deltaH_total` | Histogram over `deltaH_total`. |
| `conscious_gate_easy_total` | Count of easy gate activations. |
| `conscious_gate_low_impact_total` | Count of low-impact gate activations. |
| `conscious_gate_fallback_total` | Count of fallback occurrences. |
| `conscious_receipt_completeness_ratio` | Fraction of receipt fields present (deltaH_total, redundancy, neighbors). |
| `conscious_coherence_mode_total{mode}` | Count of queries by coherence attribution mode (migration telemetry). |

## Completeness Heuristic
A "complete" receipt has: non-null `deltaH_total`, non-null `redundancy`, and at least one item with neighbors. Ratio = present / 3.

## Deprecation Plan
- `coh_drop_total` (alias of `deltaH_total`) – mark deprecated in v1. Removal planned after two minor version increments or when no external consumers depend on it (whichever first). Clients should migrate to `deltaH_total` immediately.
  - Phase 1 (current): both fields present.
  - Phase 2: add structured log warning when `coh_drop_total` accessed (planned).
  - Phase 3: remove `coh_drop_total` and bump `receipt_version` if removal constitutes a breaking change for any retained clients.

## Future Additions (v2 candidates)
- Learned edge weights (separate from raw cosine).
- Per-item `deltaH_rank_contrib` explicit scalar.
- Signed integrity hash of receipt payload.
- Tenant-scoped adaptive parameter set ID.
 - Normalized coherence as default (will bump `receipt_version` to 2 when legacy removed).

## v2 Preview – Normalized Coherence & Energy Identity
Status: Phase 0 (feature-flagged). When `USE_NORMALIZED_COH=true` the system:
1. Computes per-node coherence contributions using the symmetric normalized Laplacian \(L_{sym} = I - D^{-1/2} A D^{-1/2}\) by forming degree-normalized embeddings \(Q_i / \sqrt{d_i}\) prior to difference.
2. Aggregates undirected edge energy with strict 0.5 / 0.5 splitting after grouping duplicate (i,j)/(j,i) edges.
3. Emits additional diagnostics fields:
   - `coherence_mode`: `normalized` vs `legacy`.
   - `deltaH_trace`: Trace-form energy gap (currently mirrors `deltaH_total`; will become quadratic identity validation).
   - `deltaH_rel_diff`: Relative difference between legacy and normalized totals when running in legacy mode with reference available (telemetry only; to be removed post cutover).
   - `kappa_bound`: Lightweight conditioning bound of solve operator (helps identify poorly conditioned batches).

Planned for v2 formalization:
| Change | Effect |
|--------|--------|
| Remove legacy asymmetric attribution | Decreases ambiguity; per-node coherence strictly tied to normalized Laplacian objective. |
| Introduce exact ΔH quadratic identity | Enables audit-grade verification (non-negative, recomputable). |
| Deprecate `coh_drop_total` alias | Canonical name becomes `deltaH_total`. |

### Example (Normalized Mode Excerpt)
```json
{
  "diagnostics": {
    "deltaH_total": 0.1874,
    "deltaH_trace": 0.1874,
    "coherence_mode": "normalized",
    "kappa_bound": 5.9
  },
  "items": [
    {
      "id": "doc_17",
      "score": 0.812,
      "energy_terms": {
        "coherence_drop": 0.0241,
        "anchor_drop": -0.0113,
        "ground_penalty": 0.0027
      },
      "neighbors": [ {"id": "doc_03", "w": 0.74}, {"id": "doc_22", "w": 0.69} ]
    }
  ]
}
```

### Migration Guidance
| Phase | Action | Client Recommendation |
|-------|--------|-----------------------|
| 0 (current) | Flag off by default; new fields additive | Begin reading `coherence_mode`, `deltaH_trace`. |
| 1 | Internal enablement, monitor `deltaH_rel_diff` | Alert if diff > 1e-3 (investigate data skew). |
| 2 | Flip default (`normalized`), bump `receipt_version` to 2 | Treat legacy attribution as deprecated; update any magnitude-based heuristics. |
| 3 | Remove legacy path & `deltaH_rel_diff` | Rely solely on trace identity for audits. |

### Invariants (Target)
- `sum_i coherence_drop_i == deltaH_total` (within FP tolerance – enforced by test).
- `deltaH_trace >= 0` and `abs(deltaH_trace - deltaH_total)` small (future identity).
- Monotonic improvement: enabling normalization should not reduce ranking quality vs legacy in internal benchmarks (tracked separately).

See `NORMALIZATION_PLAN.md` for the full technical roadmap.

## Normalization Migration
The normalization rollout (see `NORMALIZATION_PLAN.md`) introduces mathematically consistent per-node coherence using the symmetric normalized Laplacian and adds diagnostics:
- `coherence_mode` confirms which attribution path was active.
- `deltaH_trace` will validate ΔH via a non-negative quadratic identity (placeholder equals `deltaH_total` during Phase 0).
- `kappa_bound` offers a lightweight spectral conditioning estimate aiding convergence monitoring.
During Phase 0 these fields are additive and backward compatible; clients should begin reading `coherence_mode` to prepare for `normalized` becoming the default in receipt_version=2.

## Audit Log Entry (when ENABLE_AUDIT_LOG)
Each query appends JSON line with minimal PII:
```json
{
  "ts": 1730700000.123,
  "query": "...",
  "k": 8,
  "m": 400,
  "deltaH_total": 2.314,
  "applied_alpha": 0.12,
  "alpha_source": "suggested",
  "fallback": false,
  "fallback_reason": null,
  "receipt_version": 1,
  "easy_gate": false,
  "low_impact_gate": false,
  "iter_max": 9,
  "residual": 0.0007,
  "redundancy": 0.31,
  "items": [ {"id": "doc_42", "score": 0.87, "coherence_drop": 0.15, "neighbors": ["doc_17","doc_88"]} ]
}
```

## Integrity & Privacy
Do not include raw embeddings or user PII. Future integrity features may sign the JSON with a service key to enable tamper detection.

---
This doc evolves with receipt_version. Changes should remain additive where possible.
