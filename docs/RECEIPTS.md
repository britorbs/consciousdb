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
