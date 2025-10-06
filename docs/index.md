---
title: ConsciousDB Documentation
layout: default
---

# ConsciousDB Documentation

ConsciousDB is a physics-inspired, model-free reranking sidecar for retrieval augmented generation (RAG). It treats your vector database as the model, applying a convex coherence optimization that yields auditable ΔH energy receipts.

## Quick Links
- API Reference: [API.md](API.md)
- Receipt Specification: [RECEIPTS.md](RECEIPTS.md)
- Algorithm & Math: [ALGORITHM.md](ALGORITHM.md)
- Connectors: [CONNECTORS.md](CONNECTORS.md)
- Benchmarks & Methodology: [BENCHMARKS.md](BENCHMARKS.md)
- Operations & Metrics: [OPERATIONS.md](OPERATIONS.md)
- Adaptive / Bandit: [ADAPTIVE.md](ADAPTIVE.md)
- Security: [SECURITY.md](SECURITY.md)
- Pricing Model: [PRICING_MODEL.md](PRICING_MODEL.md)

## Getting Started
1. Install sidecar: `pip install consciousdb-sidecar`
2. Export connector environment variables (e.g. `CONNECTOR=pgvector` + DSN) or set `USE_MOCK=true` for synthetic mode.
3. Run: `uvicorn api.main:app --port 8080 --reload`
4. Query endpoint: `POST /query` with `{ "query": "...", "k": 6, "m": 400 }`.
5. Inspect returned `diagnostics` & per-item energy terms.

## Core Concepts
| Concept | Summary |
|---------|---------|
| ΔH Energy Gap | Improvement between baseline embeddings and solved coherent embeddings. |
| Per-Node Attribution | Degree-normalized Laplacian + ground + anchor decomposition summing to ΔH. |
| Scope Diff | Divergence between full-scope ΔH and truncated top-k contributions (`deltaH_scope_diff`). |
| Conditioning Bound | Heuristic κ(M) proxy for numerical stability monitoring. |

## Release Notes
See [CHANGELOG.md](../CHANGELOG.md) for the latest release history.

## Contributing
Read [CONTRIBUTING.md](../CONTRIBUTING.md) and open focused PRs with tests & doc updates.

## License
Business Source License 1.1 (BSL) auto-converting to Apache 2.0 on 2028-10-05. See [LICENSE](../LICENSE).

---
Generated index page for GitHub Pages (enable Pages pointing to `/docs`).
