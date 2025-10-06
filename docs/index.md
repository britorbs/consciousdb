---
title: ConsciousDB Documentation
layout: default
---

# ConsciousDB Documentation

ConsciousDB is a physics-inspired, model-free coherence optimization + ranking layer for retrieval augmented generation (RAG). It treats your vector database as the model, applying a convex coherence optimization that yields auditable ΔH energy receipts. Formerly packaged as a network "sidecar", it is now offered primarily as a lightweight Python SDK.

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
1. Install SDK: `pip install consciousdb`
2. (Optional) Install server wrapper: `pip install "consciousdb[server]"`
3. Create a `ConsciousClient` with your connector + embedder objects.
4. Call `client.query("your query", k=6, m=400)` and inspect `result.diagnostics` & per-item energy terms.
5. Use the deprecated HTTP wrapper only if you require transitional REST access.

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
