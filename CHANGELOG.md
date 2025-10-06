# Changelog

All notable changes to this project will be documented in this file.

The format (for released versions) adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project follows [SemVer](https://semver.org/) once it reaches a stable 1.0.0.

## [Unreleased]
### Added
- Receipt schema v2 activation: normalized coherence attribution now default (`USE_NORMALIZED_COH=true`).
- Escape hatch `FORCE_LEGACY_COH` allowing temporary reversion to legacy attribution during grace window.
- Additional receipt diagnostics stabilization: clarified `deltaH_rel_diff` semantics as scope divergence (full trace vs returned top‑k) to aid monitoring.
### Changed
- Bumped `receipt_version` from 1 to 2 (normalized coherence default); updated documentation (`docs/RECEIPTS.md`, `NORMALIZATION_PLAN.md`).
- Updated receipts doc to mark normalization Phases 0–2 complete and outline Phase 3 cleanup targets.
### Fixed
- Clarified invariants and scope divergence interpretation to prevent misclassification of expected variance as correctness regression.
### Removed
### Deprecated
- `coh_drop_total` alias remains deprecated; removal scheduled for Phase 3 cleanup.
- `deltaH_rel_diff` slated for rename/removal (`deltaH_scope_diff`) post legacy code path deletion.
### Security
### Performance

## [0.1.0] - 2025-10-05
### Added
- Initial packaging metadata in `pyproject.toml` (PEP 621) with optional extras for connectors & embedders.
- Contribution, Code of Conduct, and Security policies (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`).
- Expanded README with "Database-as-Model" paradigm narrative and comparison table.
- Log rotation (size-based) & HMAC-signed audit log.
- Adaptive solver enhancements: correlation-based alpha suggestion + UCB1 bandit with guard rails.
- Extended Prometheus metrics (deltaH_total, fallback reasons, adaptive stats, persistence failure counters).
- New documentation set establishing single-source separation: `docs/CONFIGURATION.md`, `docs/OPERATIONS.md`, `docs/ADAPTIVE.md`, `docs/TROUBLESHOOTING.md`, `docs/BENCHMARKS.md`.
- Transparent pricing framework rewrite (`PRICING_MODEL.md`) with formulas & governance; enriched research doc with data dictionary.

### Changed
- Unified dependency specification via `pyproject.toml` (phase in progress).
- `README.md` trimmed; large configuration matrix replaced with pointer links; added "Further Documentation" hub section.
- `SECURITY.md` expanded with threat model, assets, controls matrix & roadmap.
- `ARCHITECTURE.md` rewritten to include adaptive manager, bandit precedence, gating/fallback matrix, extensibility notes.
- `PRICING_RESEARCH_AND_SIMULATIONS.md` updated with data dictionary and cross-link to pricing model.

### Removed
- Redundant fallback metric increment duplication.
- Obsolete planning / legacy docs: `BUILD_PLAN.md`, `NEXT_IMPROVEMENTS.md`, legacy simulations file (`ConsciousDB_Simulations_Phases_A-G.md`).
- `DOCS_RESTRUCTURE.md` (plan executed; retained in git history).

### Deprecated
- Legacy documentation references consolidated; any external links to removed planning files should now reference `docs/ROADMAP.md` and CHANGELOG for historical context.

### Security
- Defined vulnerability disclosure process in `SECURITY.md`.

## Historical (Pre-Changelog Extraction)
These items summarize earlier development milestones captured in the internal work log prior to formalizing this changelog file.

### Adaptive Coherence Engine Foundations
- Implemented coherence energy formulation with Laplacian-based SPD system solve (Conjugate Gradient).
- Local mutual-k kNN graph construction pipeline.
- Ranking blend of coherence drop vs. alignment with gating (easy / low-impact / fallback).
- Receipts containing energy deltas, neighbors, and term breakdowns for observability & auditing.

### Observability & Persistence
- Added latency, iteration counts, redundancy, and energy metrics.
- State persistence for adaptive parameters with failure counters & integrity logging.

### Robustness & Hardening
- Fallback pathways with reason metrics & guard rails.
- Bandit reward attribution bug fix and guard for invalid arms.
- Log integrity via HMAC signatures; rotation to cap disk usage.

---
Guidance: Add new unreleased changes above. On release:
1. Replace [Unreleased] with a versioned section (e.g., [0.1.0] - 2024-XX-YY).
2. Open a new [Unreleased] header at the top.
3. Keep sections (Added / Changed / Fixed / Removed / Security / Deprecated / Performance) as relevant.
