# Documentation Restructure Proposal (2025-10-05)

## Goals
- Single source of truth per concept (eliminate drift / duplication)
- Faster onboarding: clear entrypoints for "what it is", "how to run", "how to operate", "how to adapt"
- Enterprise readiness: explicit security & operations guidance
- Future scalability: easy to add feature-specific deep dives without bloating README

## Target Top-Level Doc Map
| Category | File | Purpose | Primary Audience |
|----------|------|---------|------------------|
| Overview | README.md | Product pitch, quickstart, high-level flow | Engineers, stakeholders |
| Concepts | ARCHITECTURE.md | Internal design, flow, adaptive/bandit, extensibility | Contributors, advanced users |
| Concepts | ALGORITHM.md | Mathematical formulation & ranking equations | Researchers, eng |
| Concepts | COHERENCE_LAYER_PIVOT.md | Strategic positioning (may merge into README appendix later) | Internal / GTM |
| API | API.md | Request/response schema, endpoints, examples | Integrators |
| API | RECEIPTS.md | Receipt schema & evolution | Integrators, audit teams |
| Configuration | CONFIGURATION.md (new) | Env vars matrix, precedence, security notes | Operators, DevOps |
| Operations | OPERATIONS.md (new) | Metrics catalog, log field dictionary, SLO runbook, audit integrity | SRE / Ops |
| Adaptive | ADAPTIVE.md (new) | Alpha heuristic, bandit, state schema, failure modes | ML / Relevance |
| Troubleshooting | TROUBLESHOOTING.md (new) | Common issues & resolutions | Support, users |
| Performance | BENCHMARKS.md (new) | Uplift methodology, benchmarks procedure | Engineering, product |
| Connectors | CONNECTORS.md | Interface & backend capability matrix | Integrators |
| Deployment | DEPLOYMENT.md | Deployment patterns (local, Docker, Cloud) | DevOps |
| Security | SECURITY.md | Threat model, controls, roadmap | Security reviewers |
| Roadmap | ROADMAP.md | Phases, backlog, KPIs | Internal planning |
| History | WORKLOG.md | Chronological implementation notes | Contributors |
| Simulations | SIMULATIONS.md | Summaries of simulation findings (uplift, default choices) | Internal relevance |
| Gap Tracking | GAP_ANALYSIS.md | Snapshot of open documentation gaps | Maintainers |
| Restructure | DOCS_RESTRUCTURE.md | This plan (will be removed after execution) | Maintainers |
| Licensing | LICENSING.md | License terms & change date explanation | Legal, users |

## Files to Deprecate / Merge
| File | Action | Rationale |
|------|--------|-----------|
| BUILD_PLAN.md | Archive (git history) | Superseded by ROADMAP.md (living planning) |
| NEXT_IMPROVEMENTS.md | Merge salient items into ROADMAP.md then delete | Redundant backlog container |
| ConsciousDB_Simulations_Phases_A-G.md | Delete after migrating any unique insights to SIMULATIONS.md | Legacy name & partial duplication |

## New Files (Detailed Outlines)
### CONFIGURATION.md
Sections: Overview, Precedence (request override > adaptive > bandit > env), Core Variables Table, Security-Sensitive Variables, Example Minimal `.env`, Change Management.

### OPERATIONS.md
Sections: Metrics Dictionary (name, type, label semantics, interpretation), Log Fields, SLO Guardrails (iteration/residual/fallback targets), Audit Log Integrity Verification (step & sample script), Deployment Hardening Checklist.

### ADAPTIVE.md
Sections: Goals, State Schema (JSON keys), Alpha Suggestion Algorithm (pseudo-code), Bandit (UCB1 math), Precedence & Alpha Source, Failure Modes & Safeguards, Reproducibility Guide.

### TROUBLESHOOTING.md
Sections: Quick Decision Table (Symptom → Likely Cause → Fix), Detailed Scenarios (dimension mismatch, empty ANN, persistent fallback, high residual, no neighbors, unexpected redundancy, slow solve), Support Data Collection (which metrics/log lines to attach).

### BENCHMARKS.md
Sections: Purpose, Metrics (nDCG@K, redundancy, fallback rate, P95 latency), Harness Invocation, Edge Overlap Validation, Interpreting ΔH vs Uplift, Reporting Template.

## Migration Steps
1. Create new core docs (CONFIGURATION, OPERATIONS, ADAPTIVE, TROUBLESHOOTING, BENCHMARKS) with initial content (iterative expansion allowed).
2. Extract duplicated configuration snippets from README, API.md into CONFIGURATION.md (leave concise pointers behind).
3. Fold `NEXT_IMPROVEMENTS.md` actionable items into ROADMAP backlog; remove file.
4. Confirm all unique insights from legacy simulations file are transferred to SIMULATIONS.md; delete legacy file.
5. Link cross-references: README → (Architecture, API, Configuration, Receipts); RECEIPTS → (Audit Logging in OPERATIONS); SECURITY → (Audit Integrity in OPERATIONS).
6. Add a short Deprecations section in ROADMAP.md referencing doc retirements.
7. Remove this restructure plan file after execution (or mark completed).

## Cross-Reference Strategy
- Use relative links (`docs/CONFIGURATION.md`) from README for portability.
- Each new doc includes a "Related" section linking to complementary docs (avoid re-explaining concepts).
- Single authoritative tables: Configuration in CONFIGURATION.md; Metrics in OPERATIONS.md; Env precedence stated in both but sourced from CONFIGURATION.md.

## Ownership & Update Triggers
| Doc | Owner (Suggested) | Update Trigger |
|-----|-------------------|----------------|
| CONFIGURATION.md | Core maintainer | New env var or precedence change |
| OPERATIONS.md | SRE / core maintainer | New metric or SLO adjustment |
| ADAPTIVE.md | Relevance maintainer | Algorithm change, new bandit arm logic |
| TROUBLESHOOTING.md | Support / maintainer | New recurring issue pattern |
| BENCHMARKS.md | Perf / relevance | New uplift methodology or metric |

## Acceptance Criteria for Completion
- All new docs exist with MVP content (tables + outlines fleshed to ≥80% of identified sections).
- Removed files (`BUILD_PLAN.md`, `NEXT_IMPROVEMENTS.md`, legacy simulations file) no longer in repo.
- README size reduced (configuration matrix replaced with a link) while remaining self-contained for first run.
- Cross-link audit: no dead links; each doc has a Related section.
- Gap analysis updated to reflect closure of initial high-priority items.

## Post-Execution Cleanup
- Delete `DOCS_RESTRUCTURE.md` (retain in git history) OR move to `/docs/archive/` if policy prefers explicit archival.
- Update CHANGELOG with “Docs restructure executed” entry.

---
Status: Draft (to be executed next).