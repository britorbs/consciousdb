# Changelog

All notable changes to this project are documented here. Format loosely follows Keep a Changelog; semantic versioning applies.

## [3.0.0] - 2025-10-06 (Unreleased)
### Added
- Stable high-level orchestration entrypoint `solve_query` (embedding → candidate recall → ephemeral graph → SPD CG solve → energy attribution → ranking / optional MMR → diagnostics).
- `ConsciousClient.query` SDK method (in‑process, no HTTP requirement) exposing structured receipt object with `deltaH_total`, per-item decomposition, neighbors, timings, redundancy, cg iterations, fallback.
- Benchmark harness with metrics (nDCG, MRR, Recall@K, MAP@K) and bootstrap confidence intervals (see `docs/BENCHMARKS.md`).
- Optional reranker baseline integration point (cross-encoder) for comparative evaluation.
- Expanded README: SDK-first banner, consolidated quickstart, migration guide.

### Changed
- Shift to SDK-first distribution; HTTP server now optional extra (`pip install "consciousdb[server]")`.
- Slim default install footprint (no FastAPI/Uvicorn unless requested).
- Cleaner typing pattern using Protocol-based optional import for solver (removing fragile type ignores).
- Import ordering, style, and lint issues resolved across connectors, benchmarks, engine (Ruff clean slate).

### Fixed
- Typing / mypy issues in connectors (Pinecone, Chroma) and client.
- Duplicate `_retry` definition in Pinecone connector.
- Assorted lint violations (unused imports/vars, long lines, ordering).

### Deprecated
- Legacy sidecar-first usage path; retained via `server` extra for transitional deployments. Future enhancements target SDK path.

### Security
- No new security fixes; baseline model + threat posture documented in `docs/SECURITY.md`.

### Internal
- Docstring stability contract for `solve_query` clarifying additive-only evolution of receipt fields.

## Historical (Pre‑3.0 Snapshot)
Earlier iterations focused on normalized coherence attribution, adaptive loops, metrics, and initial sidecar deployment model. See repository history for granular changes prior to the formal 3.0 consolidation.

---
Upgrade notes:
1. Replace HTTP POST calls with `ConsciousClient().query(query, k, m)`.
2. Remove sidecar deployment unless cross-language / network boundary required.
3. Add extras explicitly for connectors/embedders (e.g. `pip install "consciousdb[connectors-pgvector,embedders-sentence]"`).
4. Consume returned dataclass fields instead of raw JSON where possible (schema still serializable).
5. Expect only additive receipt field changes going forward.

[3.0.0]: https://github.com/Maverick0351a/consciousdb/releases/tag/v3.0.0
