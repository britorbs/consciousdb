# Migration Guide: Legacy REST Wrapper → SDK (Package renamed)

This guide helps you migrate from the deprecated FastAPI HTTP wrapper (previously packaged as `consciousdb-sidecar`) to the in‑process Python SDK (`consciousdb` / `ConsciousClient`).

## Why Migrate
| Legacy HTTP Wrapper | SDK (`ConsciousClient`) |
|-----------------------|-------------------------|
| Extra web server process (FastAPI + Uvicorn) | In‑process — no network hop |
| Env var configuration scattered | Explicit `Config` object (`from consciousdb import Config`) |
| Harder local debugging (serialize JSON) | Direct Python objects (dataclasses) |
| Higher latency (serialization + HTTP) | Lower latency (function call) |
| Hard to version per service | Pin normal Python dependency |

The server is now **deprecated** (still available via `pip install "consciousdb[server]"`). New integrations should use the SDK.

## Installation
```bash
# Lean algorithmic core
pip install consciousdb

# If you still need the HTTP server temporarily
pip install "consciousdb[server]"
```

## Core Concepts Mapping
| Concept | REST (JSON) | SDK (Python) |
|---------|-------------|--------------|
| Query endpoint | `POST /query` | `client.query()` |
| Payload root | `{ "query": "...", "k": 6, "m": 400, "overrides": {...} }` | `client.query(q, k=6, m=400, overrides={...})` |
| Overrides object | `overrides` JSON block | `overrides` dict (same keys) |
| Receipt detail (neighbors/energy) | `receipt_detail: 0|1` | Always full (future: param) |
| Diagnostics | `diagnostics` JSON section | `QueryResult.diagnostics` dict |
| Items | `items[]` | `QueryResult.items` (list of `RankedItem`) |
| Timings | `diagnostics.timings_ms` | `QueryResult.timings_ms` |
| Alpha mix param | `overrides.alpha_deltaH` | same key in overrides |
| Force fallback | `overrides.force_fallback` | same key in overrides |
| Enable MMR | `overrides.use_mmr` | same key in overrides |

## Environment → Config Field Mapping
| Env Var | `Config` Field | Notes |
|---------|----------------|-------|
| `CONNECTOR` | `connector` | memory | pgvector | pinecone | chroma | vertex |
| `EMBEDDER` | `embedder` | sentence_transformer | openai | vertex |
| `USE_MOCK` | `use_mock` | Lightweight internal mock path |
| `KNN_K` | `knn_k` | Graph degree for adjacency build |
| `KNN_MUTUAL` | `knn_mutual` | Enforce mutual edges |
| `ALPHA_DELTAH` | `alpha_deltaH` | Mix weight between ΔH z-score & alignment |
| `SIMILARITY_GAP_MARGIN` | `similarity_gap_margin` | Easy gate threshold |
| `COH_DROP_MIN` | `coh_drop_min` | Low-impact gate threshold |
| `EXPAND_WHEN_GAP_BELOW` | `expand_when_gap_below` | Conditional context expansion |
| `ITERS_CAP` | `iters_cap` | CG iteration cap |
| `RESIDUAL_TOL` | `residual_tol` | Convergence tolerance |
| `REDUNDANCY_THRESHOLD` | `redundancy_threshold` | MMR gating metric |
| `MMR_LAMBDA` | `mmr_lambda` | MMR tradeoff factor |
| `ENABLE_MMR` | `enable_mmr` | Global enable (still conditional on redundancy) |
| `ST_MODEL` | `st_model` | SentenceTransformer model name |
| `OPENAI_API_KEY` | `openai_api_key` | Passed to OpenAI embedder |
| `PG_DSN` | `pg_dsn` | PostgreSQL DSN for pgvector |
| `PINECONE_API_KEY` | `pinecone_api_key` | Pinecone client key |
| `PINECONE_INDEX` | `pinecone_index` | Pinecone index name |
| `CHROMA_HOST` | `chroma_host` | Chroma URL |
| `CHROMA_COLLECTION` | `chroma_collection` | Chroma collection |
| `GCP_PROJECT` | `gcp_project` | Vertex AI context |
| `VERTEX_INDEX` | `vertex_index` | Vertex index name |

## Minimal SDK Example
```python
from consciousdb import Config, ConsciousClient

# Acquire or implement concrete connector & embedder objects.
# For illustration we sketch simple protocol expectations.
class MemoryConnector:
    def top_m(self, query_vec, m):
        # return list of (id, similarity, vector)
        raise NotImplementedError
    def fetch_vectors(self, ids):
        raise NotImplementedError

class STEmbedder:
    def embed(self, text: str):
        raise NotImplementedError

cfg = Config.from_env()  # or Config(connector='pinecone', pinecone_api_key='...')
client = ConsciousClient(connector=MemoryConnector(), embedder=STEmbedder(), config=cfg)
result = client.query("vector governance controls", k=6, m=400)
print(result.diagnostics.get("deltaH_total"), len(result.items))
```

## Old REST Call vs New SDK
### Before (REST)
```bash
curl -s -X POST http://localhost:8080/query \
  -H "content-type: application/json" \
  -d '{"query":"vector governance controls","k":6,"m":400,"overrides":{"alpha_deltaH":0.15}}'
```
### After (SDK)
```python
res = client.query("vector governance controls", k=6, m=400, overrides={"alpha_deltaH": 0.15})
print(res.items[0].id, res.diagnostics["deltaH_total"])
```

## Parameter Override Precedence
1. Explicit `overrides` passed to `client.query()` (highest)
2. `solver_overrides` passed to `ConsciousClient(...)` constructor
3. Values derived from `Config.to_overrides()`
4. Internal defaults (hard-coded fallbacks)

## Deprecation Timeline (Draft)
| Component | Status | Planned Removal |
|-----------|--------|-----------------|
| FastAPI sidecar | Deprecated | TBD (publish in CHANGELOG after feedback phase) |
| Settings (env-scatter) | Transitional | After server removal |
| Direct env param tuning without `Config` | Supported (legacy) | With server removal |

A finalized schedule will land in `CHANGELOG` once the migration guide is adopted by early users (#38).

## Testing Migration
| Step | Action | Expected |
|------|--------|----------|
| 1 | Create new branch & add SDK code path | Both REST & SDK produce similar ordering |
| 2 | Compare top-k IDs for sample queries | Minor differences acceptable (float noise) |
| 3 | Remove HTTP calls from application layer | Latency drops by ~serialization overhead |
| 4 | Drop server extra from requirements | Smaller install tree |

## FAQ
**Do I still get receipts?**  Yes — `QueryResult.diagnostics` retains all fields (`deltaH_total`, scope metrics, timings, redundancy, etc.).

**How do I adjust solver iterations globally?** Set `ITERS_CAP` env before process start or pass `Config(iters_cap=30)`.

**Is async supported?** Not yet. Async client is a deferred roadmap item; current focus is minimal synchronous adoption friction.

**What about telemetry & persistence?** Both are deferred; current SDK intentionally keeps no implicit local caching to stay predictable.

## Next Steps
1. Update your app to construct a `Config` explicitly.
2. Replace REST calls with `ConsciousClient.query`.
3. Remove server dependency from base environment.
4. Provide feedback via issues for any gaps not covered here.

---
*Generated as part of the SDK transition (Phase: Migration Guide).*