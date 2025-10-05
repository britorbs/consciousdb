# Architecture

This document describes the runtime data flow, adaptive ranking components, observability, and extensibility points of the ConsciousDB Sidecar.

## Request Flow (BYOVDB)

1. Embed query `y` (embedder: SentenceTransformer / OpenAI / Vertex).
2. ANN recall from configured vector DB connector (pgvector / Pinecone / Chroma / Vertex) returning top-M IDs + similarities (+ optional vectors).
3. Easy-query gate: if `(cos_top1 - cos_top10) > margin` (similarity gap) and not forced full path, short-circuit to vector-only response.
4. Induce subgraph over recall set (mutual kNN, k=5 default). Optionally expand 1-hop when gap small & M large.
5. Solve anchored SPD system with Conjugate Gradient (Jacobi preconditioner):
   `M = λ_G I + λ_C L_sym + λ_Q B`, with anchor diagonal `B = diag(b)` from normalized recall similarities.
6. Compute per-node energy components on baseline (`λ_Q=0`) and anchored solution; derive coherence_drop.
7. Blend ranking score: `score_i = α * z(coherence_drop_i) + (1-α) * align_i` where `align_i = cos(Q*_i, y)` after smoothing.
8. Low-impact gate: if `sum(coherence_drop) < τ` treat as vector-only (`used_deltaH=false`).
9. Redundancy analysis + optional MMR if redundancy > threshold and k > 8.
10. Build explainability payload (neighbors, energy terms, diagnostics) and return.

## Connectors

Interface shape:
- `top_m(y: np.ndarray, m: int) -> List[(id, similarity, maybe_vector)]`
- `fetch_vectors(ids: List[str]) -> np.ndarray` when vectors absent from recall.

No persistent storage of customer embeddings occurs in the sidecar by default—stateless except transient query scope.

## Learning (Baseline Concept)

Feedback (`/feedback`) currently powers adaptive α suggestion / bandit but not structural graph updates. Future background job could:
* Calculate activations and apply Hebbian-style updates to a shared graph store (Redis / memory) with caps.
* Enforce degree & row norms to prevent hub explosion.

## Adaptive Manager (Alpha Suggestion)

Goal: auto-tune α to balance coherence vs. alignment given corpus heterogeneity.
Flow:
1. Cache `(deltaH_total, redundancy)` for each query (by `query_id`).
2. On feedback, transform into event `{deltaH_total, redundancy, positive}` (positive = accepted_id OR any click).
3. Maintain fixed-size ring buffer; compute Pearson correlation corr(deltaH_total, positive) if variance > ε.
4. If correlation > +θ_hi raise α; if < -θ_lo lower α; clamp to [0,1].
5. Expose `suggested_alpha`; optionally apply if `ENABLE_ADAPTIVE_APPLY=true`.

Resilience: IO failures on load/save are logged + metrics incremented; system continues using in-memory state / defaults.

## Bandit Layer (UCB1 over α Arms)

Optional exploration across discrete α arms. Precedence order for applied α: adaptive (if auto-apply) > bandit > manual override.
Reward model: acceptance or click → 1 else 0. Updated in feedback path, persisted in adaptive state JSON.

## Gating & Fallback

| Gate | Condition | Effect |
|------|-----------|--------|
| Easy Query | similarity_gap > margin & not forced | Skip solve; vector-only path |
| Low Impact | sum(coherence_drop) < coh_drop_min | Mark `used_deltaH=false` (vector-only semantics) |
| Forced Fallback | overrides.force_fallback | Force full pipeline attempt OR mark fallback reason forced |
| Iteration Cap | max_iters == iters_cap | Fallback; reason includes iters_cap |
| Residual | residual > residual_tol | Fallback; reason includes residual |

`fallback_reason` may be a comma list (e.g., `iters_cap,residual`).

## Ranking Determinism

Deterministic given (query embedding, recall set vectors + similarities, α). Non-determinism stems solely from adaptive / bandit evolution. Reproduce historical result via audit log: capture applied_alpha + coherence_drop, re-run solver offline.

## Audit Logging

Feature flag `ENABLE_AUDIT_LOG` writes one JSON line per query: timing slices, gating flags, fallback_reason, deltaH_total, redundancy, item IDs + per-item coherence_drop, optional HMAC signature (`AUDIT_HMAC_KEY`). Size-based rotation at 5MB.

## Metrics Surface (Prometheus)

- Total latency + segment (build / solve / rank)
- CG iteration histograms (avg/min/max/median derived in diagnostics)
- Redundancy histogram
- Fallback reason counters
- Adaptive state load/save failure counters
- Bandit arm selection / reward metrics

## Configuration Precedence

1. Request overrides (direct).
2. Adaptive suggestion (if auto-apply).
3. Bandit selection.
4. Environment defaults (`infra.settings.Settings`).

## Settings Highlights

| Env | Purpose |
|-----|---------|
| ALPHA_DELTAH | Default manual α if no adaptive/bandit override |
| SIMILARITY_GAP_MARGIN | Easy-query gate margin |
| COH_DROP_MIN | Low-impact gate threshold |
| ITERS_CAP / RESIDUAL_TOL | Solver convergence guards |
| ENABLE_ADAPTIVE / ENABLE_ADAPTIVE_APPLY | Turn on suggestion + auto-apply |
| ENABLE_BANDIT | Explore α arms via UCB1 |
| ENABLE_AUDIT_LOG | Emit detailed audit lines |
| AUDIT_HMAC_KEY | Sign audit lines for integrity |

## Persistence & State

Adaptive state JSON contains: suggested_alpha, events buffer, bandit arms (means, counts), metadata. Loaded on startup (best-effort) and saved on shutdown and feedback mutation. Failures degrade gracefully.

## Extensibility Points

| Area | Mechanism |
|------|-----------|
| Connectors | Implement `top_m` / `fetch_vectors`; register in connector registry |
| Embedders | Implement `embed_query`; register |
| Graph Construction | Replace `knn_adjacency` with persisted global graph or approximate neighbor service |
| Solver | Alternate preconditioners or acceleration (Chebyshev, multigrid) |
| Ranking | Replace linear blend with learned scorer (keeping explainability) |
| Adaptive Policy | Swap correlation heuristic for regression / Bayesian methods |

## Future Roadmap (Architecture)

- Persistent adaptive graph (Hebbian edges) with decay / pruning
- Progressive streaming responses (early top-k before solve completes)
- Memory tiering / vector compression (PQ / OPQ) for large M
- Structured remote audit exporter (OTel, object storage)
- Differential privacy noise injection (optional) for coherence metrics

## Summary

The sidecar layers deterministic linear-algebra smoothing atop ANN recall, then adaptively tunes the coherence vs. alignment trade-off using lightweight statistics and an optional bandit. Observability (metrics + audit) and gating ensure bounded latency and debuggability while preserving data minimization.
