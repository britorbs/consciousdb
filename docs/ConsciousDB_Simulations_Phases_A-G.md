# ConsciousDB — Simulation Phases Report (A–G)

**Purpose.** Establish a repeatable, documented workflow to evaluate retrieval policy choices, graph construction, expansion, and ranking strategies for the ConsciousDB sidecar. This document records scenarios, steps, results, and a checklist of gaps/improvements to apply in the repo.

> **Repro note:** No code is included. Each section lists the dataset setup, parameters, and seeds required to recreate the runs using the simulation harness.

---

## Contents
- Phase A — Core policy validation
- Phase B — Graph construction sensitivity
- Phase C — Expansion policy sweep
- Phase D — Ranking α & MMR sensitivity
- Phase E — Preconditioner impact
- Phase F — Approximate kNN parity vs exact
- Phase G — MMR at larger K=20
- Artifacts
- Gaps & Improvements (checklist)
- Next steps

---

## Global setup (applies unless overridden)

- Synthetic corpus: `N = 900` items, `C = 6` clusters, `d = 32`.
- Cluster generation: unit-norm random centers; points sampled with Gaussian noise and L2-normalized.
- Candidate pool per query: top-`M ∈ {200, 400}` by raw cosine vs query embedding.
- Query embedding: near the true cluster center with small Gaussian perturbation; normalized.
- Graph adjacency over the pool: cosine kNN (defaults vary by phase).
- System: solve \( M Q = \lambda_G X + \lambda_Q b y^\top \) with \( M = \lambda_G I + \lambda_C L_{sym} + \lambda_Q B \).
- Anchors: \( b_i \propto \max(0, \cos(x_i, y)) \), normalized.
- Default hyperparameters: \( \lambda_G = 1.0, \lambda_C = 0.5, \lambda_Q = 4.0 \).
- Gating:
  - Easy-query gate: trigger if similarity gap `gap = cos_top1 − cos_top10 > 0.15` → use vector-only ranking.
  - Low-impact gate: trigger if `sum(coherence_drop) < 1e−2` → use vector-only ranking.
- Ranking policy (unless testing variations):
  - Score = `α·z(coherence_drop) + (1−α)·cos(q*, y)` with `α = 0.1` and **smoothed alignment** cos(q*, y).
  - MMR off by default; enabled explicitly per phase.
- CG solver: max iterations 20, residual tolerance `1e−3`, warm start at X; times include only solve.
- Seeds are specified per phase to ensure determinism.

---

## Phase A — Core policy validation

**Goal.** Validate uplift of the policy (coherence-only + smoothed alignment + gates + conditional 1-hop).

**Parameters.**
- Difficulty `σ ∈ {0.25, 0.40, 0.55}`.
- Pool size `M ∈ {200, 400}`.
- Adjacency: cosine kNN, `k_adj = 10`, weights = cos+, mutualized.
- Expansion: triggered if `gap < 0.08`, cap = `1.5×M`.
- Seeds: corpus=7, query per cluster=42.

**Key results (nDCG@10 uplift vs cosine).**
- `σ=0.25`: +3.39% (M=200), **+4.81% (M=400)**.
- `σ=0.40`: +2.02% (M=200), **+2.91% (M=400)**.
- `σ=0.55`: +1.99% (M=200), **+2.07% (M=400)**.
- p95 CG iterations ≈ 3; p50 solve ~28–118 ms depending on M.

**Conclusion.** Uplift is consistent, increases with pool size, and remains within latency SLO headroom.

---

## Phase B — Graph construction sensitivity

**Goal.** Find adjacency settings that improve uplift and compute profile.

**Parameters.**
- Difficulty `σ=0.40` (moderate).
- Pool `M ∈ {200, 400}`.
- Grid: `k_adj ∈ {5, 10, 20}`, weights ∈ {cos+, binary}, mutual ∈ {True, False}.
- Seeds: corpus=13, query=77.

**Key results (M=400).**
- `k_adj=5`, cos+, mutual=True → **+4.88% uplift**, p50 solve ~135 ms.
- `k_adj=10`, cos+, mutual=True → +4.15% uplift, ~156 ms.
- `k_adj=5`, binary, mutual=True → +4.77% uplift, but slower (~202 ms).

**Conclusion.** **Set defaults to `k_adj=5`, weights=`cos+`, `mutual=True`**. Smaller degree reduces leakage and improves both iterations and relevance.

---

## Phase C — Expansion policy sweep

**Goal.** Tune 1‑hop expansion gate and cap for hard queries.

**Parameters.**
- Difficulty `σ=0.55` (hard), `M=400`.
- Gap triggers: `{0.05, 0.08, 0.12}`; cap ratios `{1.2, 1.5, 2.0}`.
- Seeds: corpus=21, query=99.

**Key results.**
- Uplift ~**+1.1% to +1.2%** across the grid.
- Solve cost rises with cap ratio; uplift flat beyond **1.5×**.

**Conclusion.** Keep **gap trigger = 0.08** and **cap = 1.5×M**. Expansion remains a targeted booster (useful, not overused).

---

## Phase D — Ranking α & MMR sensitivity

**Goal.** Calibrate α and examine MMR impact.

**Parameters.**
- Difficulty `σ=0.40`, `M=400`, `k_adj=10`.
- α ∈ {0.0, 0.05, 0.1, 0.2}; MMR ∈ {off, on}; K=10.
- Seeds: corpus=31, query=55.

**Key results.**
- Best band: **α = 0.05–0.10**. α=0.1 gives +3.66% uplift (MMR off).
- MMR **reduces redundancy** but **hurt nDCG@10** in these runs.

**Conclusion.** Default **α=0.1**. Keep **MMR OFF** by default; consider enabling for **K>8 only** when redundancy exceeds a threshold.

---

## Phase E — Preconditioner impact (none vs Jacobi)

**Goal.** Measure latency/iteration improvements from a diagonal preconditioner.

**Parameters.**
- Difficulty `σ=0.40`, `M=400`, `k_adj=5`, weights=cos+, mutualized.
- Preconditioner: off vs **Jacobi** (diagonal of λG I + λC L + λQ B).
- Seeds: corpus=123, query=1000+cluster.

**Results (averaged over clusters).**
- **No preconditioner:** p50 solve ≈ **270 ms**, p95 iters=3, uplift +3.38%.
- **Jacobi preconditioner:** p50 solve ≈ **201 ms**, p95 iters=3, uplift +3.38%.

**Conclusion.** **Enable Jacobi preconditioner by default** for ~25% median latency reduction with identical quality.

---

## Phase F — Approximate kNN parity vs exact

**Goal.** Understand how approximate adjacency quality (edge overlap) impacts uplift.

**Parameters.**
- Difficulty `σ=0.40`, `M=400`, `k_adj=5`, weights=cos+, mutualized.
- Approximation modes: projection to 16d and 8d; additive noise ε∈{0.05, 0.1}. Edge overlap measured vs exact kNN on the same pool.
- Seeds: corpus=222; projection/noise=12345+cluster.

**Results (mean across clusters).**
- **proj16:** overlap ≈ 0.13, uplift ≈ **+0.5%** (near-neutral).
- **proj8:** overlap ≈ 0.06, uplift **−4.4%** (harmful).
- **noisy 0.05:** overlap ≈ 0.43, uplift **+6.0%** (regularization effect observed on this synthetic set).
- **noisy 0.1:** overlap ≈ 0.20, uplift **+3.4%** (below exact).

**Conclusion.**
- Do not deploy low-overlap approximations (e.g., **overlap < 0.10**); quality drops sharply.
- Target **edge-overlap ≥ 0.25–0.30** when using approximate kNN to retain most of the uplift.
- Mild stochasticity can sometimes help by reducing over-smoothing, but treat it as an implementation detail, not a promise.

---

## Phase G — MMR at larger K = 20

**Goal.** Quantify diversity/relevance trade-off for larger context sizes.

**Parameters.**
- Difficulty `σ=0.40`, `M=400`, `k_adj=5`, K=20.
- MMR: off vs on (λ=0.3), operate on smoothed vectors (q*).
- Seeds: corpus=333, query=3000+cluster.

**Results (mean).**
- **MMR off:** nDCG@20 ≈ **0.848**, redundancy (mean pairwise cosine) ≈ **0.307**.
- **MMR on:** nDCG@20 ≈ **0.458**, redundancy ≈ **0.090**.

**Conclusion.** MMR substantially reduces redundancy but at a large relevance cost in this synthetic setup. Keep **OFF by default**, use only when diversity is an explicit objective (e.g., multi-topic contexts), and gate by a redundancy threshold.

---

## Artifacts

All CSV outputs are available for inspection:

- Phase A: `phaseA_core_summary.csv`, `phaseA_core_per_query.csv`
- Phase B: `phaseB_graph_summary.csv`, `phaseB_graph_per_query.csv`
- Phase C: `phaseC_expand_summary.csv`, `phaseC_expand_per_query.csv`
- Phase D: `phaseD_alpha_mmr_summary.csv`, `phaseD_alpha_mmr_per_query.csv`
- Phase E: `phaseE_precond_summary.csv`, `phaseE_precond_per_query.csv`
- Phase F: `phaseF_approx_knn_summary.csv`, `phaseF_approx_knn_per_query.csv`
- Phase G: `phaseG_mmr20_summary.csv`, `phaseG_mmr20_per_query.csv`

(Place them under a `/benchmarks/` directory in the repo for reference.)

---

## Gaps & Improvements (checklist)

**Adjacency & Graph**
- [ ] Default `k_adj = 5`, weights = cos+, `mutual=True` (Phase B).
- [ ] Add diagnostics: `edge_count`, `avg_degree`, `weights_mode` (Phase B).
- [ ] Implement approximate kNN mode behind a flag; **enforce edge-overlap ≥ 0.25** vs exact in CI parity test (Phase F).

**Ranking & Expansion**
- [ ] Keep `α = 0.1` and **smoothed alignment**; **MMR OFF** by default (Phase D, G).
- [ ] Enable MMR only for `K>8` and when redundancy > threshold; surface redundancy metric (Phase D/G).
- [ ] Maintain expansion gate `gap < 0.08` and `cap_ratio = 1.5`; log `used_expand_1hop` (Phase C).

**Solver / Numeric**
- [ ] Turn **Jacobi preconditioner ON** by default (Phase E).
- [ ] Record `cg_iters_min/median/max` and residual; set SLO alert on p95 iters > 12 (Phases A/E).

**Gating & Safety**
- [ ] Easy-query gate at gap > 0.15; Low-impact gate at `coh_drop_min = 1e−2` (Phases A/C).
- [ ] Add per-tenant calibration hooks for `coh_drop_min` (to bound negative uplift on real data).

**Observability**
- [ ] Prometheus `/metrics` with counters: `queries_total`, `used_deltaH_total`, `used_expand_total`.
- [ ] Histograms: latency per stage (ANN/build/solve/rank), `cg_iters`, redundancy.
- [ ] Structured JSON logs with `request_id`, tenant, and gate/fallback reasons.

**Connectors & Embeddings**
- [ ] Complete pgvector & Pinecone connectors; validate dim checks on startup.
- [ ] Lazy-load SentenceTransformer; keep deterministic placeholder for tests.

**CI/Bench**
- [ ] Add benchmark harness target producing a JSON summary of SLOs.
- [ ] CI parity test for approximate kNN (edge-overlap threshold).

---

## Next steps

1. Fold defaults into the codebase:
   - `k_adj=5`, cos+, mutual; α=0.1; MMR OFF; expansion at gap<0.08 & cap=1.5×.
   - Jacobi preconditioner default ON.
2. Add metrics & diagnostics listed above; wire to Prometheus.
3. Implement pgvector connector end-to-end; smoke test with a small table and vector column.
4. Re-run these phases on one **real dataset** (partner corpus) to calibrate `coh_drop_min` and expansion rate per tenant.
5. Add a CI “parity check” for any approximate kNN build; fail if edge-overlap < 0.25 or if uplift falls by >20% vs exact on a fixed synthetic set.

**Owner note:** Copy this file into `docs/BENCHMARKS.md` and list CSVs in `/benchmarks/`.
