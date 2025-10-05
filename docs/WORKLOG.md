# Work Log

Chronological record of roadmap implementation. Append an entry after each completed step.

## 2025-10-04
- Added kNN adjacency construction (`graph.build.knn_adjacency`) and integrated into `/query` pipeline replacing placeholder line graph.
- Extended settings with `KNN_K`, `KNN_MUTUAL`.
- Diagnostics now include `edge_count` and `avg_degree`.
- Updated schemas to reflect new diagnostics fields.

- Vectorized coherence computation in `engine.energy.per_node_components` (N1). Replaced Python loops with batch operations; preserved semantics via directed-edge accumulation. Pending benchmark harness to quantify speedup formally.

- Added z-score stabilization (G6) in `engine.rank.zscore`: returns zero vector when std < 1e-6 to prevent division noise.

Pending next: vectorized coherence computation (N1), z-score stabilization (G6), iteration stats (G8).

## 2025-10-04 (later)
- Implemented iteration stats exposure (G8): `solve_block_cg` now returns per-dimension iteration counts; API aggregates `iter_min`, `iter_max`, `iter_avg` into diagnostics. Updated `Diagnostics` schema and adjusted fallback condition to use max iteration.
- Added z-score variance tests (T3) in `tests/test_zscore_variance.py` verifying constant vector returns zeros and non-constant behavior remains standard.
- Applied top-priority Ruff fixes batch: removed multi-statement lines, separated imports, removed unused imports, restructured callback in solver for iteration counting.

## 2025-10-04 (later 2)
- Added dimension & health validation (C5): startup probes embedder dimension, compares with `EXPECTED_DIM`; fails fast when mismatch and `FAIL_ON_DIM_MISMATCH=true`, logs structured summary otherwise.
- Added request ID middleware (O2): assigns/propagates `x-request-id`; health and query responses now include header (response only for now) for correlation.
- Added startup validation summary (F2) via structured log fields: connector, embedder, dim, expected_dim, knn params.
- Extended health endpoint with `embed_dim` and `expected_dim` for quick diagnostics.

## 2025-10-04 (later 3)
- Implemented structured JSON logging (O1): custom JsonFormatter capturing timestamp, level, logger, message plus request-scoped fields (request_id, timings, gap, iteration stats). Added per-request summary log `query_done` and `easy_query_gate` event. Updated logging initialization to be idempotent across tests.

## 2025-10-04 (later 4)
- Added API key auth middleware (S1) with constant-time comparison and configurable header (`API_KEY_HEADER`). Disabled when `API_KEYS` unset.
- Added gating boundary + auth tests (T1 partial coverage): tests for auth enabled/disabled, easy-query gate, coherence-drop gate, forced fallback path. Adjusted tests to isolate API key state to avoid cross-test leakage.

## 2025-10-04 (later 5)
- Implemented lazy sentence-transformers loader (E1) with graceful fallback to hash-based 32-dim embedding when library missing or load fails. Logs `embedder_loaded` or fallback warnings, probes dimension on first use. Maintains API surface.

## 2025-10-04 (later 6)
- Replaced single-stage Dockerfile with multi-stage build (D1): builder compiles wheels, runtime installs wheels only; removed build toolchain from final image, added non-root user and healthcheck. Added OPTIONAL_EXTRAS build arg to include optional embedders/connectors without bloating default image. Updated DEPLOYMENT docs.

## 2025-10-04 (later 7)
- Added `atol=0.0` to CG solver call in `engine.solve.solve_block_cg` to eliminate SciPy future deprecation warning while maintaining convergence semantics.
- Migrated deprecated `@app.on_event('startup')` logic to FastAPI lifespan context (removes deprecation warnings; preserves validation + state injection for embed_dim/expected_dim).
- Added `.dockerignore` to shrink build context (excluded tests, docs, venv, logs, git metadata).
- Extended `Makefile` with `docker-build` and `docker-build-extras` targets (support `EXTRAS` arg for optional packages).
- Added `tests/test_health.py` to assert `/healthz` endpoint returns expected keys.
- Full test suite now 13 passing (includes new health test), no deprecation warnings from startup or SciPy CG.

## 2025-10-05 (Phase 1 diagnostics & ranking enhancements)
- Phase 1 Plan Execution (defaults & diagnostics):
	- Reduced default `KNN_K` from 10 to 5 in `infra.settings` to lower graph density and speed early experimentation.
	- Introduced configurables: `REDUNDANCY_THRESHOLD`, `MMR_LAMBDA`, `ENABLE_MMR`.
	- Extended `Diagnostics` schema with: `iter_med`, `redundancy`, `used_mmr`, `weights_mode`.
	- Added redundancy metric: average pairwise cosine similarity among top-k pre-diversified candidates (excluding diagonal).
	- Conditional MMR gating: applied only when (k>8) AND redundancy exceeds threshold AND MMR globally enabled or per-request override present. Records boolean `used_mmr`.
	- Ranking refactor: unified base order (pure similarity or blended z(deltaH)+alignment) before optional diversification.
	- Added median iteration statistic (`iter_med`) to complement min/avg/max for solver stability monitoring.
	- Added lightweight `weights_mode` marker (currently `"cos+"`) to expose future planned projection/noise modes.
	- Solver compatibility fix: replaced deprecated/removed `tol` usage in SciPy CG with guarded `rtol` first, legacy fallback; keeps strict `atol=0.0` semantics.
	- Updated structured query log to include `redundancy` and `used_mmr` fields.
- All tests pass (13/13) post-refactor; no new warnings.
- Next (Phase 1 remaining / upcoming Phase 2): consider adding metrics endpoint & Prometheus counters (latency histogram, redundancy distribution, solver iterations) before approximate kNN variants.

## 2025-10-05 (Phase 2 metrics – partial)
- Added `prometheus-client` dependency and new module `infra.metrics` defining histograms (query latency, graph build, solve, rank), solver iterations, redundancy; counters for MMR application and query totals (labeled by fallback/easy_gate/coh_gate), plus gauge for max residual.
- Instrumented `/query` handler to emit metrics (best-effort guarded try/except to avoid user-facing failures on metrics errors).
- Added `/metrics` endpoint exposing default registry using `generate_latest`.
- Created `tests/test_metrics.py` validating presence of key metric families after a sample query (adapted to schema constraints m>=100).
- Adjusted NEXT_IMPROVEMENTS observability checklist marking exposed metrics + iteration/residual tracking complete; left SLO warnings & fallback_reason event pending.
- All tests now 14 passing (added metrics test). No performance regressions observed (latency buckets populated in test run context).
- Pending to finish Phase 2: SLO guard log warnings (iter_max, residual) and structured fallback_reason emission.

## 2025-10-05 (Phase 2 completion)
- Implemented SLO guard warnings: logs `slo_iter_guard` (when `iter_max>12`) and `slo_residual_guard` (when residual > 2× tolerance) with structured fields for threshold introspection.
- Added fallback reason enumeration (`fallback_reason`) combining predicates: `forced`, `iters_cap`, `residual` (comma-separated when multiple triggers).
- Extended diagnostics schema & `/query` response to include `fallback_reason` while preserving `fallback` boolean for quick path checks.
- Added tests (`tests/test_fallback_reason.py`) covering forced fallback, iteration cap triggered fallback, and residual-based fallback; all pass.
- Modified easy-query gate to respect `force_fallback` override (ensures tests and callers can force full pipeline execution even when similarity gap is large).
- Updated NEXT_IMPROVEMENTS Phase 2 items 6–8 to COMPLETE and noted decision to defer additional explicit counters (existing labeled counter suffices for observability scope right now).
- Full test suite now 17 passing (includes new fallback reason tests) with one benign torch CUDA warning about deprecated pynvml (non-blocking).

## 2025-10-05 (Pivot Phase A – Receipt Fundamentals)
- Added `deltaH_total` (alias of existing `coh_drop_total`) to `Diagnostics` for coherent branding of coherence energy improvement (ΔH). Backwards-compatible; both fields currently present.
- Implemented neighbor receipts: each returned item now includes top (≤5) adjacency neighbors with cosine weights (mutual kNN k=5). Easy gate path still returns empty neighbors by design (no graph build) while full pipeline populates them.
- Updated `/query` handler to emit `deltaH_total` in both early and full paths; neighbor extraction built from existing in-memory adjacency to avoid extra passes.
- Added test `tests/test_receipt_phase_a.py` verifying presence/equality of `deltaH_total` and non-empty neighbor lists when full pipeline executes.
- All tests now 18 passing (includes new receipt test). Next: introduce `receipt_version`, audit log & deltaH histogram metrics (Phase B observability) and plan deprecation timeline for `coh_drop_total` once downstreams migrate.

## 2025-10-05 (Pivot Phase B – Metrics & Receipt Versioning)
- Added `receipt_version=1` to `Diagnostics` enabling forward-compatible evolution of receipt fields.
- Extended Prometheus metrics:
	- Histogram: `conscious_deltaH_total` (distribution of deltaH_total)
	- Counters: `conscious_gate_easy_total`, `conscious_gate_low_impact_total`, `conscious_gate_fallback_total`
	- Gauge: `conscious_receipt_completeness_ratio` (heuristic completeness over deltaH_total, redundancy, neighbors)
- Instrumented easy gate path to emit metrics (was previously skipped) ensuring comprehensive gate visibility.
- Updated metrics observation helper (`infra.metrics.observe_query`) with new arguments (deltaH_total, low_impact_gate, neighbors_present) and integrated into both early & full code paths.
- Added tests: `tests/test_metrics_deltaH.py` (deltaH histogram + completeness gauge) and `tests/test_receipt_version.py` (receipt_version presence) raising total test count to 20.
- All tests now 20 passing; no performance regressions observed. Next steps: implement audit log stream & RECEIPTS.md documentation, then adaptive scaffold.

## 2025-10-05 (Post Phase B – Feature Flags & Audit Log Foundation)
- Introduced feature flags in `infra.settings`: `ENABLE_AUDIT_LOG` (on by default), `ENABLE_ADAPTIVE`, `ENABLE_BANDIT` to gate upcoming adaptive experimentation layers.
- Implemented structured audit log append in `/query` (JSONL `audit.log`) capturing query, k, m, deltaH_total, fallback/fallback_reason, gating booleans, solver stats, redundancy, and compact per-item subset (id, final score, coherence_drop, neighbor ids) to enable offline analysis & drift detection.
- Added `tests/test_audit_log.py` validating audit log line creation and required keys presence (receipt_version, deltaH_total, items[].coherence_drop).
- Auth disabled within the test to isolate behavior; working directory temporarily redirected to write log into ephemeral temp path ensuring test isolation.
- Auth & metrics unaffected; audit write wrapped in try/except (best-effort) to avoid impacting latency path.
- Authored `docs/RECEIPTS.md` detailing receipt schema (v1), metrics mapping, completeness heuristic, deprecation path for `coh_drop_total`, and future evolution candidates.
- Test suite now 21 passing (includes audit log test) with unchanged runtime (~5.5s local). Pending: integrate README link to RECEIPTS doc and begin adaptive parameter scaffold in subsequent phase.

## 2025-10-05 (Adaptive Scaffold – Suggested Alpha v0)
- Added `adaptive/manager.py` implementing an in-memory ring buffer of feedback events (≤200) and correlation-based suggestion for `alpha_deltaH` (point-biserial style). Recomputes every 5 events after a 15-event warmup.
- Extended `Diagnostics` schema with optional `suggested_alpha` (feature-gated via `ENABLE_ADAPTIVE`).
- Integrated suggestion exposure in `/query` response when adaptive enabled.
- Hooked `/feedback` endpoint to record heuristic feedback events (placeholder deltaH/redundancy until query linkage added).
- Added test `tests/test_adaptive_alpha.py` verifying that after 20 feedback events a `suggested_alpha` key is present and bounded if non-null.
- Test suite now 22 passing; no performance degradation observed (≈ +0.3s overhead for added test). Next: introduce real query_id linkage & metrics for adaptive loop.

## 2025-10-05 (Adaptive Linkage & Metrics)
- Added `query_id` to `QueryResponse` (UUID when adaptive enabled) and cached `(deltaH_total, redundancy)` per query (FIFO capped at 500) enabling precise feedback attribution.
- Updated `/feedback` to resolve true deltaH_total/redundancy from cache instead of heuristic placeholder, feeding adaptive correlation.
- Introduced adaptive Prometheus metrics: `conscious_adaptive_feedback_total{positive}`, `conscious_adaptive_suggested_alpha`, `conscious_adaptive_events_buffer_size` and integrated emission on feedback events.
- Extended audit log (both easy & full paths) with `query_id` and `suggested_alpha`; added easy gate audit emission (fixes regression where early return skipped audit log causing failing test).
- README updated with Adaptive Loop section and current metrics list now including adaptive gauges/counters.
- Added tests: `test_adaptive_query_linkage.py` (query→feedback linkage & metrics presence). Adjusted existing audit log test after ensuring easy gate path also logs.
- Full test suite now 23 passing; runtime ~4.9s (slightly improved due to earlier termination ordering). Next: consider persistence layer, automatic suggestion application safety guard, and labeled fallback_reason counter.

## 2025-10-05 (Adaptive Persistence, Auto-Apply, Bandit, Audit Signing)
- Added adaptive state persistence: load at startup, save on feedback & graceful shutdown (`adaptive_state.json` path configurable via `ADAPTIVE_STATE_PATH`).
- Introduced `ENABLE_ADAPTIVE_APPLY` to automatically apply `suggested_alpha` when present; diagnostics now emit `applied_alpha` and `alpha_source` (manual|suggested|bandit).
- Added fallback reason Prometheus counter `conscious_fallback_reason_total{reason}` for granular fallback attribution.
- Implemented audit log HMAC signing (optional) via `AUDIT_HMAC_KEY`; each audit line gains `signature` (SHA-256 HMAC over sorted JSON sans signature) enabling tamper detection.
- Implemented UCB1 bandit over discrete alpha arms `[0.05,0.1,0.15,0.2,0.25,0.3]` gated by `ENABLE_BANDIT`; records per-query arm selection, attributes reward on feedback (accept or any click => 1 else 0). Persists bandit arm statistics with adaptive state.
- Added bandit metrics: `conscious_bandit_arm_select_total{alpha}` and `conscious_bandit_arm_avg_reward{alpha}` plus snapshot updates after selection & reward.
- Extended audit events (both easy & full paths) to include applied/suggested alpha and (if configured) signed integrity field.
- Added tests: audit signature presence & verification, adaptive auto-apply path, bandit selection & reward accrual, fallback reason counter scrape.
- Diagnostics surface: `applied_alpha`, `alpha_source` (manual/suggested/bandit) now available for downstream tuning introspection.
- Updated persistence logic to be best-effort (non-fatal) and atomic (temp file replace) for durability without latency impact.
- All new features guarded by explicit env flags; default behavior remains backward compatible when flags unset.

## 2025-10-05 (Post-Adaptive Hardening & Ops Polish)
- Removed placeholder fallback reason increment from `observe_query` to prevent double counting; explicit labeled increments now only in query handler.
- Added defensive guard in `bandit_select` for empty arm list (returns None gracefully).
- Introduced Prometheus counters `conscious_adaptive_state_load_failure_total` and `conscious_adaptive_state_save_failure_total` to track persistence issues; wired into lifespan load/save + feedback persistence path.
- Implemented simple size-based (5MB) log rotation for `audit.log` and `feedback.log` (single-generation rollover to `.1`) to bound disk usage during sustained traffic.
- Added size rotation before each audit/feedback append in both easy and full pipeline paths without impacting hot path latency (try/except guarded best-effort).
- Verified via smoke test with env flags (`ENABLE_ADAPTIVE`, `ENABLE_BANDIT`, `ENABLE_ADAPTIVE_APPLY`, `ENABLE_AUDIT_LOG`) that bandit alpha application, fallback forced path, and feedback reward attribution operate correctly after changes.
- Test suite remains fully green (27 tests) post-hardening; no new warnings beyond existing torch CUDA deprecation notice.

## 2025-10-05 (Lint Convergence & Config Migration)
- Comprehensive Ruff cleanup pass completed: eliminated remaining multi-statement lines, wrapped long lines, removed unused variables/imports, and renamed ambiguous single-letter matrix `I` to `identity_mat` for clarity.
- Balanced style strategy adopted: per-file ignores for mathematical symbol naming (`N8xx`) limited to `engine/`, `graph/`, adaptive manager, and tests; avoids mass renaming that would reduce readability.
- Increased Ruff line length to 120 to accommodate mathematical expressions without awkward wraps.
- Migrated deprecated Ruff configuration keys to new `[tool.ruff.lint]` and `[tool.ruff.lint.per-file-ignores]` schema (removes deprecation warnings in CI).
- Added `tests/conftest.py` plus `sitecustomize.py` to ensure local package imports (`api`, `engine`, etc.) succeed during test runs without editable install; resolves prior `ModuleNotFoundError` issues after lint refactors.
- Standardized import style in `tests/conftest.py` (split multi-import, sorted, blank line after header comment) and auto-formatted with Ruff.
- Verified clean lint state: `ruff check .` returns "All checks passed"; integrated into pre-commit workflow (already present) with autofix enabled.
- Test suite re-run post changes: all 27 tests passing; no functional regressions introduced by stylistic updates.
- Committed & pushed two commits:
	- `chore(lint): apply balanced ruff cleanup...` (main lint remediation & test path setup)
	- `chore(lint): migrate ruff config to lint.* schema and fix conftest imports` (schema migration + final import polish)
- Established foundation for future additions (optional: add mypy pre-commit, coverage badge) without blocking current release stability.
