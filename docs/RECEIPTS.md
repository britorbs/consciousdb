# Explainability Receipts (v2 Active)

The retrieval response includes a structured receipt describing how the coherence optimization affected ranking. Receipt schema **version 2** is now active (normalized coherence default). Legacy version 1 details are retained for historical and migration reference.

## Versioning
`receipt_version` in diagnostics indicates schema version. Breaking changes increment this integer. Additive fields do **not** bump the version. Deprecated fields are kept for ≥1 minor release (or explicit deprecation window) before removal. Phase 2 normalization flip activated v2 as the default.

## Core Scalars (v2)
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
| `coherence_mode` | diagnostics | Attribution mode (`normalized` default; `legacy` only via `FORCE_LEGACY_COH`). |
| `deltaH_trace` | diagnostics | Trace-form ΔH (quadratic identity; ≈ `deltaH_total`). |
| `deltaH_rel_diff` | diagnostics | Scope divergence: relative difference between full candidate-set trace and returned top‑k component sum (expected p95 ≈ 0.30–0.40). Not an accuracy error. (Temporary; will rename or remove in Phase 3.) |
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
- `coh_drop_total` (alias of `deltaH_total`) – deprecated since v1; removal targeted for Phase 3 cleanup.
- `deltaH_rel_diff` – retained as scope divergence telemetry during grace window; to be renamed (`deltaH_scope_diff`) or removed in Phase 3.

## Future Additions (v2 candidates)
- Learned edge weights (separate from raw cosine).
- Per-item `deltaH_rank_contrib` explicit scalar.
- Signed integrity hash of receipt payload.
- Tenant-scoped adaptive parameter set ID.
 - Normalized coherence as default (will bump `receipt_version` to 2 when legacy removed).

## Normalized Coherence & Energy Identity (v2 Default)
Status: Phase 2 complete — normalized path is the default. Use `FORCE_LEGACY_COH=true` only for emergency rollback during the grace window.
1. Computes per-node coherence contributions using the symmetric normalized Laplacian \(L_{sym} = I - D^{-1/2} A D^{-1/2}\) by forming degree-normalized embeddings \(Q_i / \sqrt{d_i}\) prior to difference.
2. Aggregates undirected edge energy with strict 0.5 / 0.5 splitting after grouping duplicate (i,j)/(j,i) edges.
3. Emits additional diagnostics fields:
   - `coherence_mode`: `normalized` vs `legacy`.
   - `deltaH_trace`: Trace-form energy gap (currently mirrors `deltaH_total`; will become quadratic identity validation).
   - `deltaH_rel_diff`: Relative difference between legacy and normalized totals when running in legacy mode with reference available (telemetry only; to be removed post cutover).
   - `kappa_bound`: Lightweight conditioning bound of solve operator (helps identify poorly conditioned batches).

Implemented in v2:
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

### Migration Guidance (Phases 0–2 Complete)
| Phase | Status | Action | Client Recommendation |
|-------|--------|--------|-----------------------|
| 0 | Done | Flag introduced (`USE_NORMALIZED_COH=false`) | Begin parsing `coherence_mode`, ignore magnitude shift. |
| 1 | Done | Internal enablement + monitoring | Observe `deltaH_rel_diff` distribution; verify fallback stability. |
| 2 | Done | Default flip + `receipt_version=2` | Update heuristics; treat legacy as deprecated. |
| 3 | Pending | Remove legacy & scope metric | Stop relying on `deltaH_rel_diff`; use trace identity. |

### Invariants (v2)
- `sum_i coherence_drop_i == deltaH_total` (within FP tolerance – enforced by test).
- `deltaH_trace >= 0` and `abs(deltaH_trace - deltaH_total)` ≈ 0.
- Scope divergence (`deltaH_rel_diff`) p95 stable (~0.30–0.40) unless top‑k truncation policy changes.
- Normalization flip does not raise fallback rate (>2% triggers alert).

See `NORMALIZATION_PLAN.md` for the full technical roadmap.

## Receipt Version Comparison (v1 vs v2)

This section provides a concise, side-by-side illustration of the evolution from the legacy (v1) unnormalized coherence attribution to the normalized (future v2) mathematically rigorous formulation.

### v1 (Legacy – Unnormalized)
```json
{
  "receipt_version": 1,
  "coherence_mode": "legacy",
  "deltaH_total": 2.314,
  "items": [
    {
      "coherence_drop": 0.156,  // Uses ||qi - qj||^2 (asymmetric 0.5/0.25 splitting)
      "anchor_drop": -0.021,
      "ground_penalty": 0.004
    }
  ]
}
```

Characteristics:
- Coherence attribution based on raw embedding differences without explicit degree normalization.
- No explicit verification identity; `deltaH_total` inferred from optimization path.
- No conditioning metric; limited auditability.

### v2 (Normalized – Mathematically Rigorous)
```json
{
  "receipt_version": 2,
  "coherence_mode": "normalized",
  "deltaH_total": 2.187,
  "deltaH_trace": 2.187,        // NEW: Exact (trace-form) energy gap identity
  "deltaH_rel_diff": 0.0002,     // NEW: Legacy vs normalized diff (migration telemetry; removed post cutover)
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

Migration Notes:
1. During Phase 1, both modes may appear; clients should treat `coherence_mode` as authoritative.
2. Before the default flip, begin logging distributions of `deltaH_rel_diff` (< 1e-3 target) and `coherence_fraction`.
3. After Phase 2 (default normalized + version bump), remove any dependency on legacy magnitude baselines.

Stakeholder Value:
- Improves mathematical fidelity (trace identity) and audit readiness.
- Reduces ambiguity in per-node contributions; fosters trust with explainability consumers.
- Exposes a clear conditioning signal for proactive reliability management.


## Normalization Migration Summary
Phases 0–2 complete. Phase 1 synthetic 1000-query load: 0% fallback, p95 scope divergence ~0.375, kappa_bound p95 ~1.75. Phase 2 flipped default; escape hatch `FORCE_LEGACY_COH` remains for a limited grace window. Phase 3 will remove legacy path & finalize metric renames.

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
