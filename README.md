# ConsciousDB – The Coherence Layer for AI Retrieval

<p align="center">
  <img src="docs/Wordmark%20Logo%20for%20ConsciousDB.svg" alt="ConsciousDB Wordmark" width="420" />
</p>

<!-- Badges (activate once CI visible) -->
<!-- CI -->
![CI](https://img.shields.io/github/actions/workflow/status/your-org/consciousdb-sidecar/ci.yml?branch=main&label=CI)
<!-- Coverage (placeholder; integrate codecov or shields after first report) -->
![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey)

Tagline: ConsciousDB is the coherence layer for AI retrieval — it makes your existing vector database auditable, explainable, and adaptive, without moving data.

---

## Why it exists
Raw vector DBs return nearest neighbors but cannot tell you **why** results rank or how structure could adapt. Rerankers shuffle scores heuristically; global graph builds are heavy and intrusive. ConsciousDB induces a **local subgraph per query**, optimizes a convex coherence objective, and returns results with an **explainability receipt** (ΔH + per-item decomposition). You keep your embeddings where they already live (Pinecone, pgvector, Vertex AI, Chroma) — we pull only ephemeral candidate vectors.

---

## The Database-as-Model Paradigm

Traditional rerankers add another model layer on top of your vectors. **ConsciousDB takes a different path: your vector database *is* the model.** We do not introduce another neural network— we apply transparent convex optimization directly over the structure already latent in your embeddings.

### How it works
- **No training phase** — We operate directly on your existing embeddings (no finetuning, no labeled sets).
- **Query-time intelligence** — Each query induces a fresh, local k-NN subgraph from the retrieved candidates.
- **Physics-based reasoning** — We solve a positive-definite energy minimization (think molecular dynamics / springs) where similar vectors attract and incoherent structure is smoothed.
- **Structure from data** — The graph is emergent from your vectors (mutual cosine kNN); there are no learned parameters to drift.

### What this means for you
✅ No model versioning or silent drift

✅ Zero training data requirements

✅ No GPU model-serving fleet (CPU-friendly solve)

✅ Mathematical transparency (SPD linear system + per-term energy decomposition)

✅ Your data never leaves your infrastructure boundary

This “database as model” stance lets you gain model-like reranking uplift with the operational footprint of a thin sidecar.

---

## Core Value Pillars
- **Auditable** – Every answer ships with a receipt: `deltaH_total`, per-item `coherence_drop`, `anchor_drop`, `ground_penalty`, local neighbors & edge weights, CG iteration stats, gate/fallback reasons.
- **Explainable & Model‑Free** – No neural reranker or learned parameters: your vectors are the model. We blend z‑scored coherence improvement with smoothed alignment after a convex (SPD) solve—fully inspectable math, not another black box.
- **Adaptive (opt‑in)** – A sparse edge state (tenant-scoped) can learn edge strengths & hyper-parameters from feedback using lightweight bandit / Hebbian updates (no raw data copy).
- **Non‑invasive** – BYOVDB. No corpus migration, no re-indexing. Private connectivity / VPC compatible.

### ConsciousDB vs Traditional Rerankers
| Aspect | Traditional Reranker | ConsciousDB |
|--------|----------------------|-------------|
| Model | Separate neural network | Your vectors ARE the model |
| Training | Supervised / finetuning required | None – pure convex optimization |
| Interpretability | Opaque learned weights | Per-item energy decomposition (coherence / anchor / ground) |
| Data movement | Vectors → model → scores | Vectors → local graph → energy solve |
| Deployment | Model serving infra + scaling | Lightweight sidecar (stateless compute + optional tiny state) |
| Drift Surface | Silent weight drift over time | No learned weights; graph derived fresh each query |
| Hardware | Often GPU inference | CPU-friendly iterative solver |
| Auditing | Post-hoc approximations | First-class receipt (ΔH + terms + neighbors) |

---

## High-Level Flow
Unlike ML rerankers, we do not pass vectors through an additional neural model. We treat the retrieved vectors as nodes in a transient graph and optimize their coherence on-the-fly:
1. ANN Recall: Fetch top-M candidate vectors from your existing DB.
2. Local Graph: Build a k=5 mutual cosine adjacency (cos+), optionally expand 1‑hop on hard queries.
3. Coherence Solve: Solve SPD system (Jacobi-preconditioned CG) producing smoothed embeddings Q*.
4. Scoring: Compute `coherence_drop_i` + smoothed alignment; blend with α; conditional MMR only when k>8 & redundancy high.
5. Gates & Fallbacks: Easy-query gate (large gap ⇒ vector-only), low-impact gate (tiny ΔH), iteration/residual/SLO fallbacks.
6. Receipt: Return ranked items + per-item energy terms, neighbors, timings, iteration stats, redundancy, fallback_reason, and deltaH_total.

---

## Key Concepts
| Term | Meaning |
|------|---------|
| ΔH / deltaH_total | Total coherence (energy) improvement from optimization vs baseline. |
| coherence_drop_i | Node-level contribution to ΔH used in ranking. |
| Smoothed alignment | Cosine similarity using solved embedding Q*_i (structure-aware). |
| Redundancy | Mean pairwise cosine among provisional top-K (diversification signal). |
| Fallback Reason | Enumerated trigger (`forced`, `iters_cap`, `residual`). |

---

## Quickstart (Local / Mock)
```bash
python -m venv .venv
# PowerShell:
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:USE_MOCK = 'true'
uvicorn api.main:app --reload --port 8080
```
Query:
```bash
curl -s -X POST http://localhost:8080/query -H "content-type: application/json" -d '{
  "query": "vector governance controls",
  "k": 6, "m": 400,
  "overrides": {
    "alpha_deltaH": 0.1,
    "similarity_gap_margin": 0.15,
    "coh_drop_min": 0.01,
    "expand_when_gap_below": 0.08,
    "iters_cap": 20,
    "residual_tol": 0.001
  }
}' | jq
```

---

## BYOVDB Connectors
Set one connector (others ignored). For full configuration matrix (all env vars, defaults, security notes) see `docs/CONFIGURATION.md`.
```bash
# pgvector
$env:CONNECTOR = 'pgvector'
$env:PG_DSN = 'postgresql://user:pass@host:5432/db'

# Pinecone
$env:PINECONE_API_KEY = '...'
$env:PINECONE_INDEX = 'my-index'
$env:CONNECTOR = 'pinecone'

# Chroma
$env:CHROMA_HOST = 'http://localhost:8000'
$env:CHROMA_COLLECTION = 'docs'
$env:CONNECTOR = 'chroma'

# Vertex AI
$env:GCP_PROJECT = 'my-project'
$env:VERTEX_INDEX = 'my-index'
$env:CONNECTOR = 'vertex'
```
Embedders (see also `CONFIGURATION.md` for all options):
```bash
$env:EMBEDDER = 'sentence_transformer'   # openai | vertex | sentence_transformer
$env:ST_MODEL = 'all-MiniLM-L6-v2'
```

---

## Explainability Receipt (Preview)
(Fields marked * are planned additions in the pivot phases.)
```json
{
  "deltaH_total": 2.314,
  "items": [
    {
      "id": "doc_42",
      "score": 0.873,
      "coherence_drop": 0.156,
      "anchor_drop": -0.021,
      "ground_penalty": 0.004,
      "neighbors": [ { "id": "doc_17", "weight": 0.82 }, { "id": "doc_88", "weight": 0.79 } ],
      "activation": 0.093
    }
  ],
  "redundancy": 0.31,
  "similarity_gap": 0.42,
  "used_expand_1hop": false,
  "used_deltaH": true,
  "used_mmr": false,
  "cg_iters": 9,
  "residual": 0.0007,
  "fallback": false,
  "fallback_reason": null,
  "timings_ms": { "embed": 3.1, "ann": 18.6, "build": 4.2, "solve": 22.5, "rank": 1.7, "total": 50.1 }
}
```

Full specification & evolution: see `docs/RECEIPTS.md`.

---

## Roadmap (Pivot Phases)
1. Receipt Fundamentals – expose `deltaH_total`, populate neighbors with weights, alias old `coh_drop_total`.
2. Observability & Audit – audit log stream, deltaH histogram, gate counters, receipt completeness metrics.
3. Adaptive Scaffold – opt‑in edge-state store + feedback-driven updates (no raw data retention). (In progress: suggested_alpha v0, query_id linkage, feedback correlation.)
4. Bandit Hyperparameters – per-tenant tuning of α, expansion threshold, k_adj.
5. Connector Hardening & Security – real pgvector impl, retries, rate limiting, audit retention, VPC guidelines.
6. Benchmark & Uplift – harness, uplift vs vector-only, CI guard on edge overlap & uplift thresholds.
7. Docs & Dashboard – RECEIPTS.md, live receipt viewer / Postman collection; pricing switches.

---

## Metrics (Current + Planned)
(Condensed – full definitions & interpretation live in `docs/OPERATIONS.md`.)
Current:
- query_latency_ms, graph_build_ms, solve_ms, rank_ms
- query_total{fallback,easy_gate,coh_gate}
- cg_iterations_bucket
- redundancy histogram
- mmr_applied_total
- max_residual gauge
- deltaH_total histogram
- gate_easy_total, gate_low_impact_total, gate_fallback_total
- receipt_completeness_ratio gauge
- adaptive_feedback_total{positive}
- adaptive_suggested_alpha gauge
- adaptive_events_buffer_size gauge

Planned:
- adaptive_updates_total{outcome}
- bandit_arm_selected_total{arm}
- fallback_reason labeled counter (may reuse existing with label expansion)
 - learned_edge_strength histogram
 - adaptive_applied_alpha_total (count times system auto-applies suggestion)

---

## Adaptive Loop (Persistence, Auto-Apply & Bandit)
(See `docs/ADAPTIVE.md` for full algorithm, state schema, and precedence.)
When `ENABLE_ADAPTIVE=true` each `/query` receives a `query_id` caching its `(deltaH_total, redundancy)`. `/feedback` referencing that ID updates an in-memory ring buffer (≤200) and recomputes a correlation between coherence uplift and positive feedback (accept OR any click) every 5 events after a 15‑event warmup, yielding a `suggested_alpha` in [0.02, 0.5].

### Persistence
State (events, suggested_alpha, bandit arm stats) is snapshotted atomically to `adaptive_state.json` (override with `ADAPTIVE_STATE_PATH`) on feedback and shutdown, and reloaded at startup for continuity.

### Automatic Application
Enable `ENABLE_ADAPTIVE_APPLY=true` to automatically substitute `suggested_alpha` for the manual `alpha_deltaH` override in the ranking blend. Diagnostics expose:
- `suggested_alpha`
- `applied_alpha`
- `alpha_source` = `manual` | `suggested` | `bandit`
Precedence: suggested > bandit > manual.

### Bandit Hyperparameter Exploration
Set `ENABLE_BANDIT=true` to activate a UCB1 multi-armed bandit over alpha arms `[0.05, 0.1, 0.15, 0.2, 0.25, 0.3]`. The bandit ensures cold-start exploration (one pull per arm) then balances exploitation via classical UCB score. Reward = 1 if feedback included acceptance or any click, else 0. Arm stats persist with adaptive state. Average per-arm reward surfaces via metrics.

### Metrics Added
- `conscious_adaptive_feedback_total{positive}`
- `conscious_adaptive_suggested_alpha`
- `conscious_adaptive_events_buffer_size`
- `conscious_bandit_arm_select_total{alpha}`
- `conscious_bandit_arm_avg_reward{alpha}`
- `conscious_fallback_reason_total{reason}` (granular fallback attribution)

### Audit Log Signing
If `AUDIT_HMAC_KEY` is set, each JSONL audit entry gains `signature` (hex SHA-256 HMAC over sorted JSON sans signature) enabling integrity verification. Absent the key, logging remains unchanged.

---

## Pricing & Justification (Summary)
ConsciousDB pricing is a transparent value-capture model (see `docs/PRICING_MODEL.md`). We target ~35% (band 25–45%) of empirically measured customer savings across three channels:

- Token Savings – fewer follow-up LLM calls and pruned context.
- Time Savings – reduced human escalation / analyst minutes.
- Reranker Substitution – avoided spend vs. external rerank APIs (if previously used).

Public plan anchors (illustrative): Free (10K), Developer ($79 / 50K), Pro ($499 / 500K), Team ($999 / 1M), Scale ($1,499 / 2M), Enterprise (volume $0.0008–$0.0012/query). Marginal overage prices remain ROI-positive and scale down per‑1K as volume grows. A data dictionary and full sensitivity sweep live in `PRICING_RESEARCH_AND_SIMULATIONS.md` (CSV-backed).

Governance: quarterly capture band review (or sooner if LLM token pricing shifts >20%). If realized value capture drifts above 45%, we offer credits / reserved discounts; if below 25%, we may adjust overage for sustainability.

Why this matters: customers can audit the economics, avoiding opaque, lock-in style per-vector or storage fees—pricing tracks delivered coherence & retrieval uplift, not mere data volume.

---

## Further Documentation
| Topic | Doc |
|-------|-----|
| Full API schema & examples | `docs/API.md` |
| Explainability receipt spec | `docs/RECEIPTS.md` |
| Configuration matrix & precedence | `docs/CONFIGURATION.md` |
| Operations, metrics & SLO runbook | `docs/OPERATIONS.md` |
| Adaptive + bandit deep dive | `docs/ADAPTIVE.md` |
| Architecture & extensibility | `docs/ARCHITECTURE.md` |
| Security threat model & controls | `docs/SECURITY.md` |
| Bench & uplift methodology | `docs/BENCHMARKS.md` |
| Troubleshooting scenarios | `docs/TROUBLESHOOTING.md` |
| Simulation findings summary | `docs/SIMULATIONS.md` |

---

## SLO Guardrails
- P95 end-to-end latency budget target: ≤ 400 ms for K ≤ 8.
- Iteration SLO: warn if max CG iterations > 12.
- Residual SLO: warn if residual > 2× tolerance.
- Fallback rate target: < 5% (excluding forced tests).

---

## Security / Enterprise Posture
- API key auth (header, constant-time compare) – present.
- Planned: per-tenant rate limiting, audit log stream (JSONL, redactable), private networking guidance, credential rotation hook, optional HMAC signing.
- No raw customer corpus persisted; optional adaptive state stores only hashed IDs & edge weights.

---

## Contributing
Issues & PRs welcome. Keep changes small & covered by tests. Add structured log fields instead of ad-hoc prints. Follow existing style for diagnostics evolution (additive, backwards-compatible).

---

## License
Business Source License 1.1 (BSL) with automatic conversion to Apache-2.0 on **2028-10-05**. See `LICENSE` and `docs/LICENSING.md` for details, allowed use cases, and rationale. Evaluation, research, and internal non-production use are free; commercial production use requires a commercial license until the change date.

> Investor line: “ConsciousDB is the model-free coherence layer for AI retrieval. Instead of adding another neural network, it treats your vector database as the model itself—applying physics-based convex optimization (ΔH) to make search auditable, adaptive, and transparent. No training, no drift, no black box—just math on your existing vectors.”
