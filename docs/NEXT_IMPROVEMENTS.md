# Next Optional Improvements

A living checklist of potential enhancements. Tick items as they are implemented.

## Embedders & Connectors
- [ ] Add OpenAI embedder (with rate limiting + error backoff)
- [ ] Add Vertex AI embedder (use regional endpoint + caching)
- [ ] Add configurable connector pooling (reuse HTTP / DB sessions)
- [ ] Implement real 1‑hop expansion using persisted adjacency (avoid mock expansion)

## Observability & Metrics
- [x] Expose Prometheus metrics endpoint (`/metrics`) with request latency histograms
- [x] Track CG iteration distribution (histogram) and residuals
- [x] Add structured event for fallback reasons (which predicate triggered) (field: `fallback_reason` + `query_done` log)
- [ ] Integrate optional OpenTelemetry tracing (env-guarded)

## Performance & Scaling
- [ ] Add simple in-memory LRU cache for recent query embeddings
- [ ] Parallelize per-dimension CG solves using `ThreadPoolExecutor` when `d` large
- [ ] SIMD / NumPy optimization pass for per_node_components (benchmark diff)
- [ ] Add batch `/multi_query` endpoint for amortized embedding + ANN

## Reliability & Resilience
- [ ] Circuit breaker / retry wrapper around external connectors
- [ ] Graceful shutdown ensuring feedback log flush
- [ ] Timeouts and cancellation propagation from request to solver layer
- [ ] Configurable max in-flight requests (backpressure)

## Security & Governance
- [ ] API key rotation endpoint (admin scope)
- [ ] Rate limiting (token bucket per key)
- [ ] Audit log stream (append-only) for queries + feedback
- [ ] Add optional HMAC request signing verification

## Deployment & Ops
- [ ] Add SBOM (CycloneDX) generation in build pipeline
- [ ] Multi-arch Docker build (linux/amd64, linux/arm64)
- [ ] Add container image vulnerability scan step (e.g., Trivy)
- [ ] Helm chart for Kubernetes deployment

## Testing & QA
- [ ] Benchmark harness comparing dense vs CG speed & accuracy
- [ ] Property tests for z-score and gating invariants
- [ ] Load test script (Locust / k6) with synthetic embedding distribution
- [ ] Golden log snapshot test (ensure structured keys stability)

## Data & Feedback Loop
- [ ] Persist feedback events to durable store (Postgres/BigQuery)
- [ ] Add active learning sampler (surface uncertain items)
- [ ] Drift detection on embedding norms & similarity gap distributions
- [ ] Optional feature flag for experimental scoring formula variants

## Documentation & DX
- [ ] Expand `ALGORITHM.md` with worked example and diagrams
- [ ] Add architecture diagram to `ARCHITECTURE.md` (Mermaid)
- [ ] Quickstart script (powershell + bash variants) for local dev
- [ ] Generated OpenAPI description export task in Makefile

## Quality & Tooling
- [ ] Enforce Ruff + mypy in CI (strict subset of rules)
- [ ] Add pre-commit config (format, lint, security scan)
- [ ] Introduce type annotations for connectors & embedders interface boundaries
- [ ] Static analysis for secrets in config (detect misconfig)

## Stretch Ideas
- [ ] Adaptive k selection based on similarity gap slope
- [ ] Hybrid ranking fusion (graph + lexical BM25) optional overlay
- [ ] Partial update of kNN adjacency using streaming inserts
- [ ] GPU-accelerated embedding & similarity (Faiss / cuML path)

---
Add or prune items as priorities evolve. Keep the top 3–5 near-term picks surfaced in planning discussions.

---

## Phased Implementation Plan (Approved)

### Phase 1 – Defaults & Core Diagnostics
1. Change default kNN k from 10 to 5 (settings + docs) and expose `weights_mode="cos+"` in diagnostics.
2. Add redundancy metric (mean pairwise cosine across returned top-k) to diagnostics.
3. Add median CG iterations (`iter_med`) to diagnostics (already have min/avg/max).
4. Implement conditional MMR gating (only apply when `k>8` AND redundancy > threshold).
5. Extend diagnostics with: `redundancy`, `iter_med`, `used_mmr`, `weights_mode`.

### Phase 2 – Metrics & SLO Guards
6. COMPLETE: Prometheus `/metrics` endpoint with counters & histograms (latency, solve/rank/graph timings, iterations, redundancy, mmr_applied, query_total w/ labels). Decision: defer separate explicit counters for easy_gate / expand / fallback reasons (labels sufficient for now).
7. COMPLETE: SLO guard log warnings when `iter_max > 12` or residual > 2× tolerance.
8. COMPLETE: `fallback_reason` structured diagnostics + log field enumerating predicates (`forced`, `iters_cap`, `residual`).

### Phase 3 – Approximate kNN Mode
9. Introduce `KNN_APPROX_MODE` (exact|proj16|noisy_005|noisy_010).
10. Implement projection & noise modes for adjacency build (flagged; off by default).
11. Parity helper script to compute edge overlap vs exact for CI.

### Phase 4 – Benchmark & Parity CI
12. Add `/benchmarks` directory & `BENCHMARKS.md` with harness instructions.
13. Synthetic benchmark harness generating JSON summary (latencies, iters, redundancy, pseudo-uplift proxy).
14. CI parity job failing if edge_overlap<0.25 or uplift delta below threshold.

### Phase 5 – Connectors & Per-Tenant Calibration
15. Flesh out pgvector connector (real SQL cosine retrieval) with integration test.
16. Add per-tenant gating calibration (header-based tenant id mapping to `coh_drop_min`).
17. Validate connector-specific dimension & log connector health stats at startup.

### Phase 6 – Feedback & Diversity Refinement
18. Persist feedback JSONL to `data/feedback/` (configurable path) and optional ingestion interface.
19. Track rolling redundancy distribution to refine MMR threshold adaptively.
20. Optional endpoint to preview diversity impact (`/simulate_mmr`).

### Phase 7 – Documentation & DX
21. `BENCHMARKS.md` populated with sample output & interpretation guide.
22. Update `ALGORITHM.md` with redundancy metric + MMR gating formula.
23. Add Makefile targets: `bench-run`, `parity-check`, `export-openapi`.
24. Add quickstart script & update README for new metrics & approximate modes.

### Acceptance Snapshot (Phase 1 Done When)
- Query response includes redundancy & iter_med & used_mmr keys.
- Default kNN k=5 active (edge_count reflects reduced degree) and tests still pass.
- MMR not applied for k<=8; applied only when redundancy > threshold.

---

Track completion in WORKLOG after each phase or sub-step.
