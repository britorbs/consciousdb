# ConsciousDB Sidecar Roadmap

_Last updated: 2025-10-05_

## 1. Vision & Principles
Build a portable, explainable retrieval sidecar that: (a) never regresses on easy queries, (b) provides transparent diagnostics, (c) lets customers keep their own vector storage (BYOVDB), and (d) scales performance & security incrementally without locking choices early.

Guiding principles:
- Gating before complexity: skip work when the query is separable.
- Math first, optimization second: prove SPD & correctness, then tune.
- Observability early: add metrics/logs before performance tightening.
- Feature flags & graceful fallbacks: no hard outages when advanced logic fails.
- BYO everything: connectors & embedders pluggable with minimal core changes.

## 2. Phase Overview
| Phase | Name | Focus | Target Duration | Exit Snapshot |
|-------|------|-------|-----------------|---------------|
| 0 | Stabilize Foundation | Real graph, perf baseline, auth/logging | ~1–1.5 wks | kNN graph + ST + auth + P95<150ms |
| 1 | Production Core | Connectors, metrics, config, MMR, perf guard | ~1.5–2 wks | Pgvector/Pinecone + /metrics + rate limits |
| 2 | Reliability & Security | Retries, multi-tenant, secrets, audit, coverage | ~2 wks | Retry & isolation + ≥85% coverage |
| 3 | Optimization & Learning | Performance refactors, caching, feedback infra | ~2 wks | Caching + feedback pipeline |
| 4 | Advanced Features | Approx kNN, learning edges, packaging | as needed | Approx graph + offline eval |

## 3. Backlog (Tickets by Epic)
Priority: P0 critical, P1 high, P2 medium, P3 stretch. Effort: S/M/L/XL.

### 3.1 Graph & Ranking Foundations
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| G1 | Real cosine kNN adjacency | P0 | M | – | kNN over recalled vectors (k configurable); no self-loops; symmetric (A≈Aᵀ, tol 1e-6); avg_degree≈k (±1); metrics: edge_count, build_ms |
| N1 | Vectorized coherence computation | P0 | M | G1 | ≥20% runtime improvement vs baseline (M=400,d=32); identical values to prior method |
| G6 | Z-score stabilization | P0 | S | – | If std<1e-6 → zero vector; unit test passes |
| G8 | Iteration stats exposure | P0 | S | – | Diagnostics show min/max/median/max_iters_used; early convergence reflected |
| G3 | 1-hop context expansion | P1 | S | G1 | Expands only when gap<threshold & |S_ctx|>|S| & |S_ctx|≤cap; results restricted to S |
| G4 | Neighbor list population | P1 | S | G1 | Each item has neighbors list (≤k_adj) with ids + weights |
| G5 | MMR rerank flag | P1 | S | G1 | When enabled: MMR applied to (Q*, alignment); lower mean pairwise cosine than baseline |
| G7 | Dual-solve optimization | P2 | M | Stable solve | Runtime reduction ≥15% vs two CG runs; scores within tolerance |
| G2 | Approximate kNN (FAISS/Annoy) | P3 | L | G1 | >95% edge overlap sample; latency drop documented |

### 3.2 Connectors
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| C5 | Dimension & health validation | P0 | S | E1 | Startup dry-run ANN + optional fetch; mismatch raises clear error |
| C1 | PgVector fetch_vectors | P1 | S | – | Returns array shape (len(ids), d); integration test (mock) |
| C2 | Pinecone query implementation | P1 | M | API key | ids+scores returned; optional vectors; fallback on missing values |
| C6 | Retry/backoff & timeouts | P2 | M | C1/C2 | Exponential jitter, max_attempts, retries_used in diagnostics |
| C3 | Chroma connector | P2 | M | lib | Query success path + test |
| C4 | Vertex AI vector search | P2 | L | project | Query path behind env flag |

### 3.3 Embeddings
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| E1 | Real SentenceTransformer (lazy) | P0 | M | – | Cold start <1.5s; placeholder preserved; dimension visible in /healthz |
| E2 | OpenAI embedder | P1 | S | key | Handles 429 w/ backoff; test via mock; env-gated |
| E5 | Embedding LRU cache | P2 | M | E1 | Cache hit ratio metric; repeated query faster (>50% improvement) |
| E3 | Vertex AI embeddings | P2 | M | creds | Similar to E2; integration flag |
| E6 | Batch embeddings support | P3 | L | E1 | Accept list; shape validated |

### 3.4 Numerical & Performance
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| N4 | Benchmark harness | P1 | S | Phase0 baseline | JSON includes P50_ms,P95_ms,iters_p95,gap_rate,fallback_rate |
| N2 | Multi-d solve optimization | P2 | L | G7 | Single block or parallel strategy; same outputs |
| N3 | Preconditioner options | P3 | M | baseline | Toggle none/Jacobi; iteration deltas recorded |

### 3.5 Observability & Diagnostics
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| O1 | JSON structured logging | P0 | S | – | JSON lines w/ level, ts, request_id |
| O2 | Request ID middleware | P0 | S | O1 | Adds header `X-Request-ID`; logs correlate |
| O3 | Prometheus metrics endpoint | P1 | M | O1 | /metrics exposes counters, histograms |
| O4 | Gating/fallback counters | P1 | S | O3 | Metrics show increments per gate path |
| O5 | On-demand profiling | P2 | L | O3 | Admin endpoint triggers CPU/heap profile dump |

### 3.6 Security & Multi-Tenancy
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| S1 | API key auth middleware | P0 | S | – | 401 on missing/invalid; test passes |
| S2 | Rate limiting (token bucket) | P1 | M | S1 | 429 on excess; configurable per key |
| S3 | Tenant connector scoping | P2 | M | S1 | Separate states per tenant id |
| S4 | Secrets backend abstraction | P2 | M | – | Env + stub provider; fallback logic test |
| S5 | Audit log sanitization | P2 | S | O1 | No secrets; test scans logs |

### 3.7 Testing & QA
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| T1 | Gating boundary tests | P0 | S | – | Force easy & hard queries deterministically |
| T3 | Z-score variance edge test | P0 | S | G6 | Constant vector yields zeros |
| T2 | Ranking stability test | P1 | S | G1 | Without deltaH, ordering matches sims |
| T4 | Connector error paths | P1 | M | C1/C2 | Missing env produces descriptive error |
| T5 | Perf regression guard CI | P1 | M | N4 | Fail if P95 > baseline*1.25 |
| T7 | Coverage ≥85% | P2 | M | broader tests | CI coverage gate active |
| T6 | Solver fuzz tests | P3 | L | stable solve | No NaNs across random sparse graphs |

### 3.8 Configuration & Operability
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| F2 | Startup validation summary | P0 | S | C5 | Log active modules, dims, thresholds |
| F1 | Layered config (YAML + env) | P1 | M | – | Precedence: env > YAML > defaults |
| F4 | Build /version endpoint | P2 | S | – | Returns commit hash, build time |
| F3 | Hot-reload tuning (λ params) | P3 | L | F1 | Auth endpoint updates in-memory params |

### 3.9 Deployment & Packaging
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| D1 | Multi-stage slim image | P0 | S | – | Size reduced vs baseline; doc delta |
| D2 | Extras install (build args) | P1 | S | D1 | Build arg chooses extras set |
| D3 | CI pipeline (lint/test/bench) | P1 | M | N4 | Workflow publishes artifacts |
| D4 | Pre-commit hooks | P2 | S | – | Ruff/black/mypy run pre-commit |
| D5 | Optional package publish | P3 | M | stable API | pip install works, entrypoint OK |

### 3.10 Feedback & Learning Loop
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| L1 | Rotating JSONL feedback log | P2 | S | current feedback | Size-based rollover; test ensures rotation |
| L2 | Feedback ingestion queue | P2 | M | L1 | Consumer stub processes events |
| L3 | Hebbian edge prototype | P3 | L | G1,L2 | Updated adjacency influences next query (flag) |
| L4 | Offline eval harness (NDCG) | P3 | M | dataset | Outputs metrics JSON |

### 3.11 Docs & Developer Experience
| ID | Title | P | Effort | Dependencies | Acceptance Criteria |
|----|-------|---|--------|--------------|--------------------|
| X1 | Roadmap doc (this) | P0 | S | – | File committed |
| X2 | CONTRIBUTING guide | P1 | S | D3 | Style, testing, PR steps |
| X3 | Updated architecture diagram | P2 | S | G1 | Diagram reflects real graph flow |
| X4 | Troubleshooting guide | P2 | S | connectors | Common errors + resolutions |
| X5 | API examples (curl & Python) | P3 | S | stable API | Added to API.md appendix |

## 4. Phase Exit Criteria (Condensed)
- Phase 0: P95<150ms; kNN graph; ST embedder; z-score stabilized; auth/logging operational.
- Phase 1: Connectors (pgvector, Pinecone); metrics & counters; perf guard; rate limiting; config layering.
- Phase 2: Retries, tenant isolation, secrets abstraction, audit sanitation, coverage gates.
- Phase 3: Performance optimizations (vectorization & multi-d), embedding cache, feedback infra.
- Phase 4: Approx graph, learning edges, advanced packaging & offline eval.

## 5. Metrics & Quality Gates
| Metric | Source | Threshold |
|--------|--------|-----------|
| P95 query latency (M=400,d=32) | Benchmark harness | <150ms (Phase 0) |
| Fallback rate | Metrics | <5% steady-state |
| Gate skip (easy-query) rate | Metrics | >40% (healthy gating) |
| CG iterations (max) | Diagnostics | < iters_cap; median reported |
| Coverage (lines / branches) | CI | ≥85% / ≥75% (Phase 2) |
| Perf regression delta | CI guard | P95 ≤ baseline*1.25 |

## 6. Risk Register
| Risk | Impact | Mitigation |
|------|--------|------------|
| Graph cost spikes with large M | Latency | Vectorization + cap expansion |
| External API throttling (OpenAI/Pinecone) | Errors, latency | Retry/backoff + rate limit |
| Secret leakage in logs | Security | Sanitization + tests |
| Performance drift post-optimizations | User latency | Perf guard (T5) |
| Over-tuning thresholds w/out metrics | Poor relevance | Early metrics (O3/O4) |

## 7. Change Control
- Each P0/P1 ticket requires: tests, documentation update (if user-facing), metrics impact note.
- Baseline updates: require sign-off + stored new benchmark artifact.
- Feature flags for experimental paths (MMR, approx kNN, Hebbian edges).

## 8. Deprecations & Documentation Restructure
The documentation restructure (see CHANGELOG Unreleased section) consolidated and replaced several planning / legacy documents to reduce duplication and drift.

Removed (historical copies remain in git history):
- BUILD_PLAN.md (content superseded by this roadmap's phased planning)
- NEXT_IMPROVEMENTS.md (items merged into Backlog tables above)
- ConsciousDB_Simulations_Phases_A-G.md (replaced by consolidated `SIMULATIONS.md` / methodology in `BENCHMARKS.md`)
- DOCS_RESTRUCTURE.md (executed plan)

New authoritative docs introduced:
- CONFIGURATION.md (env var & precedence matrix)
- OPERATIONS.md (metrics catalog, SLO guardrails, audit integrity)
- ADAPTIVE.md (alpha heuristic, bandit, state schema)
- TROUBLESHOOTING.md (decision table & scenarios)
- BENCHMARKS.md (uplift & performance methodology)

Update Expectations:
- Add new environment variables only via CONFIGURATION.md (and link out elsewhere instead of duplicating tables).
- Add/modify metrics first in OPERATIONS.md before referencing in README or TROUBLESHOOTING.
- Adaptive algorithm or precedence changes must synchronize ADAPTIVE.md, RECEIPTS.md (fields), and API.md (diagnostics).

External References:
Integrators or prior links pointing to deprecated planning documents should now reference this `ROADMAP.md` (for future work) and the CHANGELOG (for historical changes) to maintain continuity.

## 9. Sprint Plan (Next Two Sprints)
Sprint 1: G1, N1, G6, G8, C5, E1, O1, O2, S1, T1, T3, F2, D1, X1
Sprint 2: G3, G4, G5, C1, C2, E2, N4, O3, O4, S2, T2, T4, T5, F1, D2, D3, X2

## 10. Appendix
- Benchmark dataset seed definition (to be added with N4).
- Threshold tuning guide (future addition).

---
_This roadmap is a living document; update the timestamp and summarize changes in a Changelog section when materially altered._
