# Release Notes: v3.0.0 (2025-10-05)

Major milestone introducing normalized-only coherence attribution, full audit identity, and production-quality developer experience.

## Highlights
- Normalized Laplacian per-node attribution (legacy path removed) with exact ΔH conservation.
- Added `deltaH_trace` identity & parity enforcement.
- Introduced `deltaH_scope_diff` to quantify truncation divergence.
- 85% coverage CI gate, Codecov integration, CONTRIBUTING guide.
- Streamlit demo + example notebook for coherence receipts and diagnostics visualization.

## Breaking Changes
- Removed legacy unnormalized path & `coherence_mode` field; receipts are v2-only.
- Renamed diagnostic `deltaH_rel_diff` → `deltaH_scope_diff`.

## New Diagnostics & Metrics
- `kappa_bound` conditioning heuristic.
- Prometheus histograms for solve, ΔH distributions, redundancy.
- Gate & fallback counters; simplified post-rollout metrics set.

## Developer Experience
- Architecture diagram & clarified README positioning (physics-based RAG reranking).
- Example Jupyter notebook demonstrating attribution math, audits, and scope divergence.

## Internal Refactors
- Unified solver path; removed feature flags & adoption counters.
- Consolidated docs (ALGORITHM, API, RECEIPTS) to normalized-only semantics.

## Next (Roadmap Preview)
- Real dataset loaders (MS MARCO / NQ) + additional relevance metrics (Recall@K, MAP, bootstrap CIs).
- Reranker baseline (cross-encoder) comparative benchmarks.
- Nightly benchmark CI gating minimum uplift thresholds.

Commit this file together with `CHANGELOG.md` and version bump in `pyproject.toml`.
