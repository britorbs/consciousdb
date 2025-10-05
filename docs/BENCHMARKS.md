# Benchmark & Uplift Methodology

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
