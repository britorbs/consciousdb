# API

This document summarizes the primary HTTP endpoints. For the explainability receipt schema see `RECEIPTS.md`.

## POST /query

Initiate a retrieval + (optionally) coherence optimization solve.

### Request
```jsonc
{
  "query": "text query",              // Required unless an embedding override is supported
  "k": 8,                               // Number of items to return
  "m": 400,                             // Candidate pool size
  "overrides": {
    "alpha_deltaH": 0.1,
    "similarity_gap_margin": 0.15,
    "coh_drop_min": 0.01,               // Low-impact gate threshold
    "expand_when_gap_below": 0.08,      // 1-hop expansion gate
    "iters_cap": 20,                    // CG iterations cap
    "residual_tol": 0.001,
    "force_fallback": false,            // Force vector-only path for testing
    "enable_mmr": false                 // Optional per-request diversification override
  }
}
```

### Response (illustrative subset)
```jsonc
{
  "items": [
    {
      "id": "doc:123#p0",
      "score": 0.873,
      "align": 0.912,
      "activation": 0.093,
      "neighbors": [ { "id": "doc:122#p3", "w": 0.82 } ],
      "energy_terms": {
        "coherence_drop": 0.156,
        "anchor_drop": -0.021,
        "ground_penalty": 0.004
      }
    }
  ],
  "diagnostics": {
    "receipt_version": 1,
    "deltaH_total": 2.314,
    "coh_drop_total": 2.314,            // Deprecated alias (see Deprecations)
    "redundancy": 0.31,
    "similarity_gap": 0.42,
    "used_deltaH": true,
    "used_expand_1hop": false,
    "used_mmr": false,
    "cg_iters": 9,
    "iter_min": 7,
    "iter_med": 8,
    "iter_max": 9,
    "residual": 0.0007,
    "fallback": false,
    "fallback_reason": null,
    "weights_mode": "cos+",
    "suggested_alpha": 0.12,            // Present when ENABLE_ADAPTIVE=true after warmup
    "applied_alpha": 0.12,              // Final alpha used (may equal manual, suggested, or bandit)
    "alpha_source": "suggested",       // manual | suggested | bandit
    "query_id": "0f5d4c1a-...",        // Correlates with /feedback
    "timings_ms": {
      "embed": 3.1,
      "ann": 18.6,
      "build": 4.2,
      "solve": 22.5,
      "rank": 1.7,
      "total": 50.1
    }
  },
  "version": "v0.1.0"
}
```

### Notes
- If the easy-query gate triggers (high similarity gap) or low-impact gate fires, `used_deltaH` will be false and coherence terms may be absent or zeroed; neighbors list may be empty.
- `coh_drop_total` will be removed after migration; rely on `deltaH_total`.
- `suggested_alpha`, `applied_alpha`, `alpha_source`, and `query_id` appear only when adaptive features are enabled.
- Fallback path populates `fallback=true` and a `fallback_reason` (comma-separated if multiple conditions).

## POST /feedback

Submit relevance feedback for adaptive correlation and bandit reward updates.

### Request
```jsonc
{
  "query_id": "0f5d4c1a-...",          // Required (from /query response) when adaptive enabled
  "accepted_id": "doc:123#p0",         // Optional explicit accepted item id
  "clicked_ids": ["doc:123#p0"],       // Optional array of clicked / engaged item ids
  "metadata": { "user": "analyst42" } // Optional arbitrary key-value data (not persisted unless extended)
}
```

### Response
```jsonc
{ "status": "ok" }
```

Reward semantics (bandit): reward = 1 if `accepted_id` present OR any `clicked_ids` non-empty, else 0.

## GET /healthz
Lightweight readiness probe; includes embedder dimension, expected dimension, and optionally connector status.

### Sample
```jsonc
{
  "status": "ok",
  "embed_dim": 32,
  "expected_dim": 32,
  "version": "v0.1.0"
}
```

## Metrics
Prometheus exposition at `/metrics` (histograms: latency, solve_ms, rank_ms, redundancy, deltaH_total; counters: gates, fallback reasons, adaptive events, bandit selections). See OPERATIONS.md (planned) for full catalog.

## Deprecations
- `coh_drop_total` (alias of `deltaH_total`) – slated for removal after two minor versions; clients should migrate now.

## Feature Flags (env)
- `ENABLE_ADAPTIVE`, `ENABLE_ADAPTIVE_APPLY`, `ENABLE_BANDIT`, `ENABLE_AUDIT_LOG` – control presence of adaptive & audit fields.

Refer to upcoming `CONFIGURATION.md` for a complete environment variable matrix.
