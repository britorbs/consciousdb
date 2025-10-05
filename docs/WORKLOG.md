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

## 2025-10-05 (Plan A – Baseline/Uplift & Lightweight Receipts)
- Extended `QueryRequest` with `receipt_detail` flag (1=full, 0=lightweight) enabling clients to trade explainability depth for lower payload & minor compute savings.
- Added per-item `baseline_align` (pre-optimization similarity surrogate) and `uplift` (final align minus baseline) to quantify solver contribution.
- Added solver-level diagnostics: `component_count`, `largest_component_ratio` (connected component analysis over kNN subgraph) and `solver_efficiency` (deltaH_total per ms).
- Added `uplift_avg` (mean item uplift) to `Diagnostics` surface for quick aggregate view.
- Implemented connected component traversal (BFS) over dense adjacency (k=5) – lightweight for recalled set sizes; gracefully falls back to None on exceptions.
- Adjusted `/query` pipeline:
	- Captures baseline alignment prior to ΔH-based blending.
	- Computes uplift for each returned item.
	- Applies lightweight mode by omitting neighbor lists & zeroing energy term contributions while still returning uplift & baseline fields.
- Updated schemas (`api.schemas`) with new optional fields; maintained backward compatibility (kept `receipt_version=1`).
- Added guard to ensure easy gate path also populates baseline/uplift trivially (uplift=0.0) for consistency.
- All pre-existing 27 tests remain green (pytest run post-change); no receipt_version bump yet since fields are additive & optional.
- Next steps: expose new Prometheus metrics (component_count, largest_component_ratio, solver_efficiency, uplift_avg), add JSON Schema & validation tests, expand docs on reward semantics and new diagnostics, and introduce CLI entrypoint.

## 2025-10-05 (Plan A Completion – Schema Validation, Docs, CLI)
- Added JSON Schema `schemas/query_response.schema.json` for `QueryResponse` (draft 2020-12) covering new optional baseline/uplift & diagnostic fields.
- Implemented validation test `tests/test_schema_validation.py` using `jsonschema.validate` (dev extra) to guard response shape regressions (lightweight mode sample).
- Created uplift & lightweight tests `tests/test_uplift_and_lightweight.py` verifying baseline_align/uplift presence and neighbor/energy stripping under `receipt_detail=0` with zeroed energy terms.
- Extended `docs/ADAPTIVE.md` with reward semantics: differentiation of baseline alignment vs smoothed alignment vs uplift, solver efficiency η, component fragmentation metrics, safety bounds, and usage guidelines.
- Introduced console script `consciousdb-sidecar` (entrypoint `api.cli:main`) enabling `consciousdb-sidecar --port 8080 --reload` launch without manual uvicorn invocation.
- Added `api/cli.py` thin wrapper (argparse + uvicorn.run) for simplified dev ergonomics.
- Confirmed editable reinstall registers script (`pip install -e .`) and CLI help output works.
- Decision: keep `receipt_version=1` (additive, backward-compatible optional fields) – will bump only upon removal/renaming or semantic change of existing keys.
- All Plan A tasks complete; total tests increased (schema + uplift) with entire suite passing (includes new validations). No production behavior regressions observed.
- Ready for next roadmap phase (e.g., Prometheus export of new metrics, benchmark harness, or privacy/rate limiting features) pending prioritization.

## 2025-10-05 (Normalization Phase 0 – Flag & Dual Attribution)
- Added temporary `docs/NORMALIZATION_PLAN.md` detailing migration to normalized coherence attribution, ΔH trace identity, and conditioning diagnostics with phased rollout (flag → observe → version bump → cleanup).
- Introduced feature flag `USE_NORMALIZED_COH` (default false) in `infra.settings` to guard normalized attribution path.
- Refactored `engine.energy.per_node_components` to support dual computation: legacy asymmetric directed-edge attribution (0.5 / 0.25 split) and new symmetric normalized edge half-splitting aggregated via undirected edge grouping; returns extra reference components for relative diff diagnostics.
- Updated `/query` pipeline (`api.main`) to invoke `per_node_components` with `normalized=flag` and compute: `coherence_mode` (`legacy|normalized`), `deltaH_rel_diff` (relative difference between legacy and normalized totals, Phase 0 telemetry), and placeholder `deltaH_trace` (currently equal to `coh_drop_total`; real quadratic form identity to follow).
- Extended `Diagnostics` schema with new optional fields: `deltaH_trace`, `deltaH_rel_diff`, `kappa_bound`, `coherence_mode` (additive + backward-compatible).
- Ensured legacy behavior and surface values unchanged when flag off; all prior tests remain green (30 passed after additions).
- Next (Phase 0 continuation): implement true trace-form ΔH identity and low-cost spectral condition number bound (`kappa_bound`) before enabling normalized attribution in internal environments.

## 2025-10-05 (Normalization Phase 0 – ΔH Identity & Diagnostics Expansion)
- Implemented exact quadratic-form ΔH trace identity in `/query` handler: decomposition into ground (‖Q−X‖²), Laplacian (Tr(Q^T L Q)), and anchor (Σ b_i ‖q_i−y‖²) deltas; exposed as `deltaH_trace` with numerical non-negativity guard (fallback to `coh_drop_total` on anomaly).
- Added spectral conditioning upper bound `kappa_bound` via 3-step power iteration estimating λ_max of M = λ_g I + λ_c L + λ_q B with conservative λ_min = λ_g.
- Extended Phase 0 telemetry computing `deltaH_rel_diff` between active coherence attribution mode and reference path (legacy vs normalized) to quantify migration impact.
- Added new tests `tests/test_normalization_diagnostics.py` covering presence, non-negativity, proportionality of `deltaH_trace`, kappa bound sanity (≥1), and coherence_mode reporting under both flag states.
- Populated normalization diagnostics (`coherence_mode`, `deltaH_trace`, etc.) in easy-gate early return path to satisfy test expectations and ensure consistent surface for downstream logging when solver is skipped.
- Resolved failing normalization diagnostics tests (2 earlier failures) by adding `coherence_mode` to easy path diagnostics; full suite now 32 passing.
- Work remaining for later Phases: enable flag by default (Phase 2), bump `receipt_version` to 2 removing legacy path, optional Prometheus metric for `kappa_bound`, potential anchor temperature τ exploration, and eventual removal of `deltaH_rel_diff` once migration complete.

## 2025-10-05 (Normalization Phase 0 – Degree Normalization & Adoption Telemetry)
- Implemented degree-normalized coherence attribution in `engine.energy.per_node_components` applying per-edge scaling via D^{-1/2} to ensure symmetric, mass-preserving energy allocation (eliminates residual bias from high-degree nodes present in legacy asymmetric path).
- Fixed transient `IndentationError` introduced during refactor (restored test stability immediately after patch).
- Added `coherence_fraction` diagnostic (coherence / total ΔH, clamped to [0,1]) to quantify share of improvement attributable to Laplacian smoothing vs anchor & ground components; exposed only when `deltaH_total > 0`.
- Introduced Prometheus counter `conscious_coherence_mode_total{mode}` to track adoption mix (`legacy` vs `normalized`) under `USE_NORMALIZED_COH` feature flag.
- Extended `/query` handler to compute `coherence_fraction` alongside existing ΔH trace identity (`deltaH_trace`) and adoption telemetry (`deltaH_rel_diff`, `coherence_mode`).
- Updated tests (`tests/test_normalization_diagnostics.py`) to assert presence & bounds of `coherence_fraction` and verify counter exposure for both modes (flag on/off); suite size increased to 35 passing tests.
- Documentation updates:
	- `docs/RECEIPTS.md`: Added `coherence_fraction` field, adoption counter metric, and v2 preview guidance for clients to begin consuming new fields.
	- `docs/NORMALIZATION_PLAN.md`: Added attribution share telemetry row, adoption metric row, flip criteria (≥95% normalized queries, `deltaH_rel_diff < 1e-3`), alert thresholds for diff & fraction distribution shifts, and cleanup plan retaining `coherence_fraction` while removing `deltaH_rel_diff` post-migration.
- Metrics & diagnostics now provide: (`deltaH_total`, `deltaH_trace`, `deltaH_rel_diff`, `coherence_fraction`, `kappa_bound`, `coherence_mode`).
- Current status: Phase 0 observation complete with stable normalized attribution parity (no regressions observed); proceeding toward Phase 1 (internal default flip) pending 7-day stability window & distribution review.
- Pending next steps:
	1. Add optional Prometheus summary/histogram for `kappa_bound` (defer until variance assessed).
	2. Capture anchor & ground fractions (either explicit fields or derivable via exposing all three components) if deeper energy audit proves necessary.
	3. Initiate staged rollout experiment (shadow / dual run) to gather production distribution deltas prior to flipping default.
	4. Flip `USE_NORMALIZED_COH` default to true (Phase 1) once adoption criteria met; begin deprecating legacy path.
	5. Phase 2: Bump `receipt_version` to 2, remove legacy attribution branch & `deltaH_rel_diff`; retain `coherence_fraction` and `deltaH_trace` as canonical energy diagnostics.
	6. Post-migration cleanup & doc prune: excise legacy references from `RECEIPTS.md` and collapse normalization plan into changelog.

## 2025-10-05 (Tooling – Mypy Introduction & Type Hygiene)
- Introduced mypy configuration in `pyproject.toml` with exclusions (`build/`, `dist/`, `.venv/`) to eliminate duplicate shadowed module errors from build artifacts during CI.
- Added `__init__.py` across top-level packages (`adaptive`, `api`, `connectors`, `embedders`, `engine`, `graph`, `infra`) to convert them into explicit packages and resolve initial duplicate module path complaints.
- Added `_SupportsEncode` Protocol to type the `sentence_transformers` model interface (only `encode` needed) avoiding reliance on third-party stubs; refactored `SentenceTransformerEmbedder` to remove unreachable branch warning and ensure deterministic ndarray return type.
- Hardened solver & energy modules: ensured functions `jacobi_precond_diag`, `apply_M`, and per-node energy attribution return concrete `np.ndarray` (removed implicit Any propagation) via `np.asarray` casting.
- Adjusted logging exception guard to remove unnecessary ignore; clarified `EXPECTED_DIM` parsing logic in settings and annotated internal variable for readability.
- Cleaned memory connector and graph utilities with explicit ndarray casts, eliminating `no-any-return` diagnostics.
- Final mypy run: 56 files analyzed, 0 issues (configuration intentionally permissive—strictness can be ratcheted later). Left advanced flags (`disallow_untyped_defs`, etc.) disabled to allow incremental adoption without blocking feature velocity.
- Next optional tooling steps (deferred): introduce incremental strictness per package, add mypy caching in CI, evaluate stub generation for connector SDKs, and integrate a coverage report for typed functions.
