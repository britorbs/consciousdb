# SDK-Only Transition Plan

_Last updated: <!--DATE-->_

## Executive Summary
We are shifting from a hosted sidecar service model to an SDK-first, self-host / embed model. Objectives:
- Lower initial operational overhead (no managed infra required to evaluate).
- Broaden adoption: frictionless `pip install` + optional Docker quickstart.
- Preserve backward compatibility short term via a deprecated server wrapper.
- Simplify extension & experimentation: connectors, embedders, ranking logic as composable Python objects.

Scope explicitly excludes (initially): advanced persistence engine, multi-tenant auth, managed telemetry. These may arrive after SDK traction.

## Guiding Principles
1. Fast Time-to-First-Result (< 60s fresh venv / Docker run).
2. Lightweight Base Install (minimal transitive dependencies).
3. Deterministic, explicit configuration via a `Config` object (env vars optional convenience only).
4. Safe deprecation: clear roadmap, warnings, semantic version discipline.
5. Extensibility: connectors & embedders pluggable with stable surface.

## Target Architecture (High-Level)
```
consciousdb/
  __init__.py            # exports ConsciousClient, Config (phases 1–2)
  client.py              # core synchronous client facade
  config.py              # Config object (phase 2)
  server/ (optional)     # Thin FastAPI wrapper (phase 3, deprecated path)
  docker/                # Docker entrypoints / compose (phase 3)
engine/                  # Existing optimization logic
connectors/              # External vector store connectors
embedders/               # Embedding backends
```

## Phases Overview
| Phase | Name | Goal | Included | Excluded | Success Criteria |
|-------|------|------|----------|----------|------------------|
| 0 | Planning | Shared understanding | This document | Code changes | Plan approved |
| 1 | SDK Facade | Public `ConsciousClient` | `client.py`, exports | Async client | `from consciousdb import ConsciousClient` works |
| 2 | Slim Dependencies | Minimal base footprint | Extras reorg | Caching | Base install < ~9 deps |
| 3 | Config Refactor | Central config object | `config.py` | Deep persistence | All runtime params resolved via Config |
| 4 | Legacy Wrapper & Docker | Transitional server & eval container | FastAPI thin layer, Docker image | New managed features | Docker run + curl works; server warns deprecated |
| 5 (Deferred) | Persistence & Cache | Simple local caching | diskcache integration | Custom engine | >30% repeat query speedup |
| 6 (Deferred) | Telemetry (Opt-in) | Usage insights | Sink interface | Default on | Off-by-default; no PII |
| 7 | Docs & Migration | Developer clarity | MIGRATION.md, README rewrite | Removal of deprecated code | Clear mapping REST→SDK |
| 8 | Test Matrix & Hardening | Reliability | Sync tests, connectors matrix | Performance profiling suite | Coverage threshold maintained |
| 9 | Deprecation Finalization | Remove server path | CHANGELOG updates | Server code after grace | Server removed in major release |

## Detailed Phase Breakdown
### Phase 1 – SDK Facade
- Add package `consciousdb` with `client.py`.
- `ConsciousClient.query(query: str, k: int, m: int, overrides: dict | None = None, receipt: bool = True)`.
- Internally reuse solver logic; minimal result dataclasses (avoid Pydantic to keep base light).
- Output shape loosely mirrors existing REST JSON minus transport wrapper.
- Deliverables: code, smoke test, README quick snippet.

### Phase 2 – Slim Dependencies (Moved Earlier)
- Reclassify optional pieces into extras: `server`, `demo`, `bench`, `connectors-*`, `embedders-*`.
- Ensure importing `ConsciousClient` does not pull FastAPI / Uvicorn.
- CI job to assert import speed / dependency count (optional future improvement).

### Phase 3 – Config Refactor
- Introduce `Config` (dataclass or Pydantic-lite if needed) with all tunables: alpha, similarity gap, iteration caps, etc.
- Provide `Config.from_env()` for migration ease.
- Replace scattered `os.getenv` usages.

### Phase 4 – Legacy Server & Docker Wrapper
- Thin FastAPI wrapper calling `ConsciousClient`.
- Embed deprecation warning headers + logs.
- Docker image uses SDK internally; marketed as evaluation / integration test harness.
- Provide `docker run -p 8080:8080 consciousdb/server` one-liner in docs.

### Phase 5 (Deferred) – Persistence & Caching
- Introduce `diskcache` for receipts & embeddings.
- Cache key includes parameter hash + index signature.
- Basic metrics: hit ratio (in-memory counter).

### Phase 6 (Deferred) – Telemetry (Opt-In)
- Scoped out of initial traction path; revisit after adoption.

### Phase 7 – Documentation & Migration
- `MIGRATION.md`: REST examples vs SDK usage.
- README pivot: SDK first, server/Docker collapsible section.
- Add design notes for configuration and extension points.

### Phase 8 – Test Matrix & Hardening
- Tests: sync client across connectors (skipped if extras missing).
- Snapshot test for result schema stability.
- Ensure coverage threshold maintained (>= existing 85%).

### Phase 9 – Deprecation Finalization
- Announce removal timeline early (e.g., server removed in 4.0.0).
- Provide final reminder in two minor releases before removal.

## Result / Data Structures (Draft)
```python
@dataclass
class RankedItem:
    id: str
    score: float
    align: float | None = None
    baseline_align: float | None = None
    energy_terms: dict[str, float] | None = None

@dataclass
class QueryResult:
    items: list[RankedItem]
    diagnostics: dict[str, float | int | str]
    timings_ms: dict[str, float]
```

## Migration Mapping (Preview)
| REST Endpoint | SDK Call | Notes |
|---------------|----------|-------|
| POST /query | `client.query(query, k, m, overrides)` | Receipt detail auto included; filter fields client-side |
| (future) /health | N/A | Not needed in embedded usage |

## Dependency Reclassification (Planned)
| Extra | Includes |
|-------|----------|
| server | fastapi, uvicorn |
| demo | streamlit, requests |
| bench | requests, tqdm |
| connectors-pinecone | pinecone-client |
| connectors-chroma | chromadb |
| connectors-pgvector | psycopg2-binary |
| embedders-openai | openai |
| embedders-sentencetransformers | sentence-transformers |

## Risk Register
| Risk | Mitigation |
|------|------------|
| Hidden FastAPI coupling | Early extraction & tests without server extra installed |
| Confusing deprecation | MIGRATION.md + runtime warnings + CHANGELOG entries |
| Over-engineering cache early | Defer; leverage `diskcache` when needed |
| Async demand earlier than expected | Design client core so async wrapper can reuse internal `_run_query` |
| Dependency regression | CI check import graph / freeze base extras |

## Success Metrics
| Metric | Target |
|--------|--------|
| Time-to-first query | < 60s (fresh venv) |
| Base install dependency count | ≤ 9 direct |
| Coverage retention | ≥ 85% |
| Deprecated server usage (if telemetry later) | < 20% before removal window |

## Versioning & Deprecation Timeline (Proposed)
| Version | Changes |
|---------|---------|
| 3.1.0 | SDK facade introduced; server deprecated (warn) |
| 3.2.x / 3.3.x | Reinforced warnings; docs emphasize SDK |
| 4.0.0 | Server code removed (or externalized) |

## Update Log
| Date | Change | Author |
|------|--------|--------|
| 2025-10-05 | Initial plan document created | automation |

(Add entries as phases complete.)

## Next Action
Proceed with Phase 1: implement `consciousdb` package and `ConsciousClient` minimal query path.

---
_This document is a living artifact; update after each phase and commit changes._
