# Explainability Receipts (v2)

Receipt schema **version 2** is the sole supported format. Normalized coherence is permanent; legacy v1 and migration flags have been removed.

## Versioning
`receipt_version` in diagnostics indicates schema version. Breaking changes increment this integer. Additive fields do **not** bump the version. Deprecated fields are kept for ≥1 minor release (or explicit deprecation window) before removal. Phase 2 normalization flip activated v2 as the default.

## Core Scalars (v2)
| Field | Source | Meaning |
|-------|--------|---------|
| `deltaH_total` | diagnostics | Total coherence (energy) improvement vs baseline (sum of per-item coherence_drop). |
| `redundancy` | diagnostics | Mean pairwise cosine similarity among provisional top-k before diversification (excludes diagonal). |
| `similarity_gap` | diagnostics | Gap between top similarity and 10th (or last available) used for easy gate heuristic. |
| `fallback` | diagnostics | True if any fallback predicate triggered. |
| `fallback_reason` | diagnostics | Comma-separated predicates: `forced`, `iters_cap`, `residual`. |
| `suggested_alpha` | diagnostics | Suggested alpha from adaptive correlation (present when ENABLE_ADAPTIVE and warmup complete). |
| `applied_alpha` | diagnostics | Alpha actually used in ranking (manual, suggested, or bandit arm). |
| `alpha_source` | diagnostics | One of `manual`, `suggested`, `bandit`. |
| `query_id` | diagnostics | Identifier for correlating feedback. |
| `deltaH_trace` | diagnostics | Trace-form ΔH (quadratic identity; ≈ `deltaH_total`). |
| `deltaH_scope_diff` | diagnostics | Scope divergence: relative difference between full candidate-set trace and returned top‑k component sum (expected p95 ≈ 0.30–0.40). Informational only. |
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
No active deprecations; legacy migration artifacts removed.

## Future Additions (v2 candidates)
- Learned edge weights (separate from raw cosine).
- Per-item `deltaH_rank_contrib` explicit scalar.
- Signed integrity hash of receipt payload.
- Tenant-scoped adaptive parameter set ID.
 - Normalized coherence as default (will bump `receipt_version` to 2 when legacy removed).

## Normalized Coherence & Energy Identity
1. Per-node coherence attribution uses the normalized Laplacian quadratic form: node i contribution = \(q_i^T (L q)_i\).
2. Conservation: \(\sum_i \text{coherence\_drop}_i = \text{deltaH\_total}\) (± FP tolerance); `deltaH_trace` matches within tolerance.
3. `kappa_bound` approximates the condition number upper bound.

Invariants:
| Invariant | Rationale |
|----------|-----------|
| `deltaH_trace >= 0` | Non-negative energy gap (SPD guarantees). |
| `abs(deltaH_trace - deltaH_total)` ≈ 0 | Identity validation. |
| `0 ≤ coherence_fraction ≤ 1` | Sanity bound. |

### Example
```json
{
  "diagnostics": {
    "deltaH_total": 0.1874,
    "deltaH_trace": 0.1874,
  "kappa_bound": 5.9,
  "deltaH_scope_diff": 0.352
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

### Scope Divergence
`deltaH_scope_diff` indicates proportion of improvement outside the returned top-k (structural tail). High values are typical when k << M.

## v2 Format
```json
{
  "receipt_version": 2,
  "deltaH_total": 2.187,
  "deltaH_trace": 2.187,        // NEW: Exact (trace-form) energy gap identity
  "deltaH_scope_diff": 0.342,    // Scope divergence full vs top-k
  "coherence_fraction": 0.71,    // NEW: Share of ΔH attributable to Laplacian term
  "kappa_bound": 5.2,            // NEW: Conditioning upper bound
  "items": [
    {
      "coherence_drop": 0.143,   // Uses ||qi/√di - qj/√dj||^2 with strict 0.5/0.5 edge splitting
      "anchor_drop": -0.021,
      "ground_penalty": 0.004
    }
  ]
}
```

Advantages:
- Degree-normalized attribution aligns exactly with the normalized Laplacian objective.
- `deltaH_trace` supplies an auditable, non-negative quadratic form identity.
- `deltaH_rel_diff` enables safe shadow comparison during migration (to be dropped after stabilization).
- `coherence_fraction` contextualizes how much of the total improvement comes from structural smoothing.
- `kappa_bound` surfaces conditioning to aid operational tuning (e.g., preconditioner tweaks, iteration caps).

Stakeholder Value:
- Audit-grade identity; reduced schema churn.
- Deterministic attribution supports explainability claims.
- Conditioning metric (`kappa_bound`) aids reliability tuning.


## Historical Note
Legacy migration details removed; receipts considered stable.

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
