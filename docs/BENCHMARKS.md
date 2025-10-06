# Benchmark Methodology

This document describes how to measure retrieval uplift and operational cost for ConsciousDB vs a vanilla cosine baseline (and optional rerankers).

## Objectives
1. Quantify ranking quality improvement (nDCG@K, MRR@K) produced by coherence optimization and optional MMR diversification.
2. Measure latency overhead and solver efficiency (ΔH per millisecond) relative to baseline.
3. Capture explainability value surface (receipt completeness vs opaque scores).

## Metrics
| Category | Metric | Description |
|----------|--------|-------------|
| Quality | nDCG@K | Discounted gain using binary or graded relevance |
| Quality | MRR@K | Reciprocal rank of first relevant item |
| Quality (future) | Recall@K | Fraction of gold set retrieved |
| Explainability | ΔH distribution | Histogram / summary of `deltaH_total` showing structural uplift |
| Explainability | coherence_fraction | Share of ΔH attributable to Laplacian term |
| Performance | P95 latency | End-to-end sidecar latency over queries |
| Performance | Solver efficiency | ΔH_total / solve_ms (higher is better) |
| Stability | κ(M) bound p95 | Conditioning bound distribution (optional gate) |

## Methods Compared
| Method Key | Description |
|------------|-------------|
| Cosine | Pure ANN / cosine ranking (no structural solve) |
| ConsciousDB | Coherence solve + structural blend (alpha) |
| ConsciousDB+MMR | Above + diversification (conditional MMR) |
| Reranker-X (optional) | External transformer reranker baseline (not implemented in repo) |

## Synthetic Dataset Procedure
1. Generate corpus embeddings (normalized Gaussian) of size N (default 500).
2. For each query create a vector; mark top-3 cosine neighbors as relevant set.
3. Evaluate each method's top-K list (default K=10) against the synthetic relevance set.
4. Compute metrics and uplifts vs baseline.

Synthetic limitations: relevance is purely cosine-based; structural uplift may appear modest if coherence correlates strongly with baseline similarity. Real datasets (MS MARCO, NQ) introduce semantic variation benefiting structure smoothing.

## Real Dataset Integration (Deferred)
To evaluate on public corpora:
1. Preprocess queries and qrels into `queries.jsonl`, `qrels.jsonl` (see `benchmarks/datasets.py`).
2. Generate / load corpus embeddings accessible to the connector (e.g., ingest into Pinecone or pgvector).
3. Run sidecar pointing at that backend with `USE_MOCK=false`.
4. Use `benchmarks/run_benchmark.py --dataset-root <path> --k 10 --m 400` (extension required to fetch actual ANN results; current script implements synthetic path only).

## Report Format
Markdown table with absolute metrics and uplift percentages, plus a JSON artifact for downstream plotting / dashboards.

Example (illustrative numbers):

| Method | nDCG@10 | MRR@10 | P95 Lat (ms) | Avg ΔH | Explainability | nDCG Uplift % | MRR Uplift % |
|--------|---------|--------|--------------|--------|----------------|---------------|--------------|
| Cosine | 0.4200 | 0.3800 | 12.0 | 0.0000 | none | - | - |
| ConsciousDB | 0.5100 | 0.4500 | 48.0 | 2.3100 | receipt | 21.43 | 18.42 |
| ConsciousDB+MMR | 0.5050 | 0.4480 | 52.0 | 2.2800 | receipt | 20.24 | 17.89 |

> MMR can slightly trade off MRR if diversification displaces the first relevant doc while improving broader coverage metrics.

## Interpreting ΔH
`deltaH_total` is an energy improvement; higher typical values indicate stronger structural incoherence corrected by optimization. Pairing uplift with ΔH distribution demonstrates that *explainability* (receipt) correlates with measurable ranking gain.

## Extending the Suite
Planned enhancements:
- Graded relevance (gain values) from MS MARCO BM25 judgments.
- Recall@K and MAP.
- Cumulative throughput & cost simulation (CPU time vs GPU reranker cost).
- Confidence intervals via bootstrap resampling.
- Latency decomposition percentiles (embed / ann / build / solve / rank).
- Comparative reranker baseline (e.g., cross-encoder). *Out-of-scope for open-core; added in premium eval toolkit.*

## Running the Synthetic Benchmark
```bash
# Ensure sidecar running locally (mock connector for speed)
$env:USE_MOCK = 'true'
uvicorn api.main:app --port 8080 --workers 1

# New terminal
python -m pip install -e .[bench]
python -m benchmarks.run_benchmark --synthetic --queries 50 --k 10 --m 400 --output benchmark_report.md --json benchmark_report.json
```
Output:
- `benchmark_report.md` – human-readable table.
- `benchmark_report.json` – structured artifact for charts.

## Governance & Regression
Integrate a reduced-query smoke benchmark (e.g., 10 queries) into CI (scheduled) asserting minimum uplift thresholds once you have stable empirical baselines (e.g., nDCG uplift ≥ 10%). Avoid gating the main PR flow until variance characterized.

---# Benchmark & Uplift Methodology

Establish consistent measurement of relevance uplift, latency, and stability.

## Objectives
- Quantify nDCG@K uplift vs vector-only baseline
- Track latency distribution (P50/P95) across M and k
- Monitor fallback & gate rates (ensure gates do not hide regressions)
- Validate structural fidelity (edge overlap) when experimenting with approximate adjacency

## Key Metrics
| Metric | Definition | Target / Interpretation |
|--------|------------|-------------------------|
| nDCG@K (K=5,10) | Standard DCG normalized by ideal ordering | +3–5% vs baseline indicates value |
| Δ nDCG (relative) | (nDCG_conscious - nDCG_vector) / nDCG_vector | >0 without regress on easy queries |
| Latency P95 | 95th percentile end-to-end | Within SLO budget (≤400ms for K≤8) |
| Fallback Rate | Fallback count / total | <5% (excluding forced tests) |
| Easy Gate Rate | Rate of gap-based vector-only path | Healthy 30–60% (corpus dependent) |
| Edge Overlap | Jaccard or fraction of shared edges vs exact kNN | ≥0.25 when using approx kNN (tunable) |
| Redundancy | Mean pairwise cosine in top-K | Used for conditional MMR gating |

## Data Preparation
1. Collect representative query set (≥200) with relevance judgments (implicit or explicit).
2. Store as JSONL: `{ "query": "...", "relevant": ["doc_id1", ...] }`.
3. Ensure embeddings in underlying vector DB correspond to same corpus snapshot.

## Harness Outline (Pseudo)
```
for each query:
  resp_vec = vector_only(connector, m, k)
  resp_cdb = conscious_query(m, k, overrides={})
  compute DCG lists from relevance labels
aggregate metrics (nDCG, latency, gates)
```

Vector-only baseline can be approximated by invoking `/query` with overrides forcing easy gate (large similarity_gap_margin) or by directly scoring initial ANN similarities.

## Edge Overlap Validation
When experimenting with approximate adjacency:
1. Build exact mutual kNN (k=5) adjacency for sample of queries.
2. Build approximate adjacency.
3. Compute overlap = |E_exact ∩ E_approx| / |E_exact|.
4. Record distribution (median, P10).
5. If below threshold, tighten approximate parameters or fall back to exact.

## Reporting Template
```
Date: YYYY-MM-DD
Corpus: <name>
Queries: <count>
M: <value>  K: <values tested>
Alpha: <value or adaptive>

nDCG@5 (vector, conscious): 0.412 / 0.437 (+6.1%)
nDCG@10 (vector, conscious): 0.451 / 0.472 (+4.7%)
Latency P50/P95 (ms): 82 / 221
Fallback Rate: 3.2% (forced excluded)
Easy Gate Rate: 44%
Edge Overlap (median): 0.31
Redundancy (mean top-10 pre-MMR): 0.37
Suggested Alpha (median): 0.11
```

## Interpreting ΔH vs Uplift
- ΔH_total high but low uplift: coherence improving on off-topic cluster → inspect relevance labels; consider connector filter.
- ΔH_total low but positive uplift: small structural smoothing suffices; gating thresholds may be near optimal.
- Negative correlation between redundancy and uplift: consider enabling MMR earlier or adjusting threshold.

## Automation & CI Guards (Future)
- Store baseline JSON with benchmark summary.
- CI job re-runs harness on sample; fail if P95 latency > baseline * 1.25 or nDCG uplift < configured floor.

## Related
- `OPERATIONS.md`
- `CONFIGURATION.md`
- `ADAPTIVE.md`
- `SIMULATIONS.md`
