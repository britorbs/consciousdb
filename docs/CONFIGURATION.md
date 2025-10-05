# Configuration Reference

Single source of truth for environment variables, override precedence, and security notes.

## Precedence
1. Request overrides (per `/query` payload `overrides`) – highest for that request only
2. Adaptive suggestion (if `ENABLE_ADAPTIVE_APPLY=true`)
3. Bandit arm (if `ENABLE_BANDIT=true`)
4. Environment variables (this document)
5. Library defaults embedded in `infra.settings.Settings`

## Core Retrieval & Ranking
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `CONNECTOR` | memory | str | Active connector: memory|pgvector|pinecone|chroma|vertex |
| `EMBEDDER` | sentence_transformer | str | Embedding backend: sentence_transformer|openai|vertex |
| `ST_MODEL` | all-MiniLM-L6-v2 | str | SentenceTransformer model name |
| `ALPHA_DELTAH` | 0.1 | float | Default blend weight (manual α) when adaptive/bandit not applied |
| `SIMILARITY_GAP_MARGIN` | 0.15 | float | Easy-query gate threshold (gap>margin) |
| `COH_DROP_MIN` | 0.01 | float | Low-impact gate threshold (deltaH_total below → vector-only) |
| `EXPAND_WHEN_GAP_BELOW` | 0.08 | float | 1-hop expansion trigger (gap < value) |
| `ITERS_CAP` | 20 | int | CG iteration limit per solve |
| `RESIDUAL_TOL` | 0.001 | float | Convergence tolerance (L2 residual) |
| `KNN_K` | 5 | int | k for local mutual kNN adjacency |
| `KNN_MUTUAL` | true | bool | Require mutual edges for adjacency symmetry |
| `REDUNDANCY_THRESHOLD` | 0.35 | float | Redundancy gating threshold for conditional MMR |
| `MMR_LAMBDA` | 0.3 | float | Trade-off in MMR selection step |
| `ENABLE_MMR` | false | bool | Force enable global MMR (else conditional) |

## Adaptive / Bandit
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `ENABLE_ADAPTIVE` | false | bool | Enable adaptive alpha suggestion pipeline |
| `ENABLE_ADAPTIVE_APPLY` | false | bool | Auto-apply suggested alpha when available |
| `ENABLE_BANDIT` | false | bool | Enable UCB1 bandit over alpha arms |
| `ADAPTIVE_STATE_PATH` | adaptive_state.json | str | JSON snapshot path for adaptive & bandit state |

## Connectors & Credentials
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `PG_DSN` | – | str | Postgres DSN for pgvector |
| `PINECONE_API_KEY` | – | str | Pinecone API key |
| `PINECONE_INDEX` | – | str | Pinecone index name |
| `CHROMA_HOST` | – | str | Chroma service URL |
| `CHROMA_COLLECTION` | – | str | Chroma collection name |
| `GCP_PROJECT` | – | str | GCP project for Vertex services |
| `VERTEX_INDEX` | – | str | Vertex AI Vector Search index ID |
| `OPENAI_API_KEY` | – | str | OpenAI embeddings key |

## Validation & Safety
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `EXPECTED_DIM` | – | int | Enforce embedding dimensionality if provided |
| `FAIL_ON_DIM_MISMATCH` | true | bool | Raise fatal error if expected != actual dim (else warn) |

## Auth & Security
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `API_KEYS` | – | str | Comma-separated API keys (auth disabled if empty) |
| `API_KEY_HEADER` | x-api-key | str | Header name for API key lookup |
| `ENABLE_AUDIT_LOG` | true | bool | Emit per-query audit JSONL lines |
| `AUDIT_HMAC_KEY` | – | str | Secret key to sign each audit entry (HMAC-SHA256) |

## Logging & Observability
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `LOG_LEVEL` | INFO | str | Logging level (DEBUG/INFO/WARN/ERROR) |
|
## Misc / Dev
| Env Var | Default | Type | Description |
|---------|---------|------|-------------|
| `USE_MOCK` | true | bool | Use mock connector/embedder shortcuts for local dev |

## Security Notes
- Treat all credentials as secrets; inject via orchestrator secret manager (no hardcoding).
- Disable `ENABLE_AUDIT_LOG` in high-sensitivity mode or ensure HMAC signing + secure shipping.
- If `AUDIT_HMAC_KEY` is set, rotate regularly and plan re-verification procedure.

## Configuration Examples
Minimal local dev (.env PowerShell style):
```
$env:USE_MOCK='true'
$env:CONNECTOR='memory'
$env:EMBEDDER='sentence_transformer'
$env:ALPHA_DELTAH='0.1'
```

Production (excerpt):
```
API_KEYS='key1,key2'
CONNECTOR='pgvector'
PG_DSN='postgresql://user:***@host:5432/db'
EMBEDDER='openai'
OPENAI_API_KEY='sk-...'
ENABLE_ADAPTIVE='true'
ENABLE_ADAPTIVE_APPLY='true'
ENABLE_BANDIT='true'
ENABLE_AUDIT_LOG='true'
AUDIT_HMAC_KEY='hmac-secret'
EXPECTED_DIM='384'
FAIL_ON_DIM_MISMATCH='true'
```

## Change Management
- Add new variables here first; reference from README / ARCHITECTURE via links.
- Breaking semantic changes (e.g., default shift affecting correctness) must appear in CHANGELOG.

## Related
- `ARCHITECTURE.md` (flow, gating, precedence summary)
- `OPERATIONS.md` (metrics & SLO response strategies)
- `ADAPTIVE.md` (alpha suggestion algorithm)
