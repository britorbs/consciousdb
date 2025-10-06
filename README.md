<p align="center">
  <img src="docs/Wordmark%20Logo%20for%20ConsciousDB.svg" alt="ConsciousDB Wordmark" width="420" />
</p>

# ConsciousDB – Your Vector Database *Is* the Model

<!-- Badges -->
![CI](https://img.shields.io/github/actions/workflow/status/Maverick0351a/consciousdb/test.yml?branch=main&label=CI)
![Coverage](https://img.shields.io/codecov/c/github/Maverick0351a/consciousdb/main?logo=codecov&label=coverage)
![License](https://img.shields.io/badge/License-BSL%201.1-blue)

> Stop stacking opaque rerankers. ConsciousDB turns the structure already latent in your vectors into an **explainable retrieval intelligence layer** – no training, no drift, full receipts.

> Elevator (non‑technical): **ConsciousDB makes vector search explainable. See exactly *why* results rank—without adding another AI model.**

## 🚩 The Problem
Vector search gives you similarity – but not *understanding*. Teams struggle to answer:
- *Why* did these items outrank others?
- *How* do the results relate to each other (support / redundancy / gaps)?
- *What* specific structure change would improve relevance?

Typical fixes add another neural reranker (more latency, drift, & opacity) or a heavy offline graph build. Both increase operational surface and hide reasoning.

## 🎯 Core Idea (Database-as-Model)
Instead of inserting a new model, each query induces a tiny, ephemeral k‑NN graph over the recalled candidates. A fast **structure‑aware energy solve** (symmetric positive definite system) refines embeddings and produces a conserved ΔH (energy uplift) that naturally decomposes per item. That decomposition *is* the ranking explanation.

| You Want | Traditional Path | ConsciousDB Path |
|----------|------------------|------------------|
| Better ordering | Add / fine‑tune model | Solve energy on existing vectors |
| Explanation | Post‑hoc approximations | Built‑in per‑item ΔH terms |
| Low ops overhead | Maintain model infra | Stateless CPU sidecar |
| Stability | Weight drift & retrains | No learned weights, fresh graph per query |
| Auditability | Sparse logs | Structured receipt JSON |

## 💎 What You Get
**Energy Receipt** – `deltaH_total` plus per-item components (coherence contribution, anchor / ground terms, neighbors, timings, fallback reasons).  
**Model‑Free Uplift** – Improved ordering using only your existing vectors.  
**Transparent Math** – Reproducible linear algebra; no hidden gradient soup.  
**Low Latency** – Typical local/mock ~50 ms P95 for k≤8 (CPU).  
**Bring Your Own Vector DB** – Pinecone, pgvector, Chroma, Vertex AI, in‑memory.

## 📊 Results In Practice *(early internal / synthetic reference)*
| Metric | Improvement / Figure | Notes |
|--------|----------------------|-------|
| nDCG uplift | **~21%** vs raw cosine | Synthetic eval harness (see `docs/BENCHMARKS.md`) |
| P95 latency | **~50 ms** | Local/mock k≤8, CPU only |
| Follow-up LLM calls | **~35% fewer** | Higher initial relevance reduces clarifying turns |

*(Real public benchmark numbers will be published as dataset loaders land.)*

## 🤔 Why Not Just...
| Option | Hidden Cost | Still Lacks |
|--------|-------------|-------------|
| Add a neural reranker | Extra model infra, finetuning, drift | Native explanation, per-item energy traces |
| Build a knowledge graph | Heavy ETL, schema churn, stale edges | On-demand freshness, low ops footprint |
| Tune / re-embed corpus | Labeling effort, loss of generality | Live structural attribution, audit trail |

**ConsciousDB:** Light, explainable, works with what you already have.

## ✨ Quickstart (Local Mock)
```bash
python -m venv .venv
. ./.venv/Scripts/Activate.ps1   # PowerShell
pip install -r requirements.txt
$env:USE_MOCK='true'
uvicorn api.main:app --port 8080 --reload
```
Query:
```bash
curl -s -X POST http://localhost:8080/query \
  -H "content-type: application/json" \
  -d '{"query":"vector governance controls","k":6,"m":400}' | jq '.items[0],.diagnostics.deltaH_total'
```
Full schema: see `docs/API.md` & `docs/RECEIPTS.md`.

## ⚡ See It Work (60 Seconds)
Requires Docker + docker compose plugin.
```bash
git clone https://github.com/Maverick0351a/consciousdb
cd consciousdb
docker compose up -d       # launches API + (optionally) demo if compose file present
sleep 3
curl -s -X POST http://localhost:8080/query -H "content-type: application/json" \
  -d '{"query":"vector governance controls","k":6,"m":300}' | jq '.diagnostics.deltaH_total'
```
Optional (if demo container configured): open http://localhost:8501

## 🧪 High-Level Flow (Conceptual)
```
Query → Vectors → Local Graph → Physics Solve → Explained Rankings (Receipt)
```
Minimal mental model:
1. Pull candidates (M) from your existing vector DB.
2. Construct ephemeral similarity graph (only these M nodes).
3. Run a fast energy minimization (convergence in a handful of iterations).
4. Decompose total uplift (ΔH) into per-item parts.
5. Rank + return receipt.

<details>
<summary><strong>Technical Path (click to expand)</strong></summary>

```mermaid
flowchart LR
  Q[Query] --> E[Embed]
  E --> R[Recall M]
  R --> G[Mutual kNN Graph]
  G --> S[SPD Solve (CG)]
  S --> A[ΔH Attribution]
  A --> RK[Rank + Diversify]
  RK --> RC[Receipt JSON]
```

- Solve: Jacobi‑preconditioned CG over normalized Laplacian + anchor/ground diagonals.
- Attribution: Per-node split (coherence/anchor/ground) sums exactly to `deltaH_total`.
- Ranking blend: z‑scored coherence uplift + structure‑smoothed alignment (optional MMR when redundancy > threshold).

</details>

## 🧾 Receipt Snapshot
```json
{
  "deltaH_total": 2.314,
  "items": [{ "id": "doc_42", "coherence_drop": 0.156, "anchor_drop": -0.021, "neighbors": [{"id":"doc_17","weight":0.82}] }],
  "redundancy": 0.31,
  "cg_iters": 9,
  "fallback": false,
  "timings_ms": { "solve": 22.5, "total": 50.1 }
}
```
See full evolution in `docs/RECEIPTS.md`.

## 🔌 Connectors (BYOVDB)
```bash
# pgvector
$env:CONNECTOR='pgvector'
$env:PG_DSN='postgresql://user:pass@host:5432/db'

# Pinecone
$env:CONNECTOR='pinecone'
$env:PINECONE_API_KEY='...'
$env:PINECONE_INDEX='my-index'

# Chroma
$env:CONNECTOR='chroma'
$env:CHROMA_HOST='http://localhost:8000'
$env:CHROMA_COLLECTION='docs'
```
Embedders: `sentence_transformer` | `openai` | `vertex`. Configure via env (see `docs/CONFIGURATION.md`).

## ✅ When to Use
| Scenario | Benefit |
|----------|---------|
| RAG answer quality plateaued | Structure coherence signal beyond raw cosine |
| Need explainability / audit | Deterministic receipt; per-item decomposition |
| Avoid model fleet creep | No training / no extra neural runtime |
| Cost pressure | Substitute paid reranker API; fewer follow-up LLM calls |

## ⚖️ ConsciousDB vs Rerankers (Condensed)
| Aspect | Neural Reranker | ConsciousDB |
|--------|-----------------|-------------|
| Extra model hosting | Yes | No |
| Training / finetune | Required | None |
| Interpretability | Low | High (receipt) |
| Drift Surface | Weights drift | None (no weights) |
| Latency Source | Model inference | Small SPD solve |
| Audit Trail | Add-on | Built-in |

## 📈 Benchmarks & Metrics
Benchmark harness + methodology: `docs/BENCHMARKS.md`.  
Operational metrics & SLOs: `docs/OPERATIONS.md`.

## 🔄 Adaptive (Optional)
Feedback-driven alpha suggestion & bandit exploration are *opt‑in*; details in `docs/ADAPTIVE.md`.

---

## 📖 Deep Dive Documentation
Ready to go deeper? Start here:

| Topic | Where |
|-------|-------|
| API & Schemas | `docs/API.md` |
| Receipts Spec | `docs/RECEIPTS.md` |
| Configuration Matrix | `docs/CONFIGURATION.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Security Model | `docs/SECURITY.md` |
| Pricing Rationale | `docs/PRICING_MODEL.md` |
| Adaptive Loop | `docs/ADAPTIVE.md` |
| Benchmarks | `docs/BENCHMARKS.md` |

## 📚 More Documentation (Index)
| Topic | Where |
|-------|-------|
| API & Schemas | `docs/API.md` |
| Receipts Spec | `docs/RECEIPTS.md` |
| Configuration Matrix | `docs/CONFIGURATION.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Security Model | `docs/SECURITY.md` |
| Pricing Rationale | `docs/PRICING_MODEL.md` |
| Adaptive Loop | `docs/ADAPTIVE.md` |
| Benchmarks | `docs/BENCHMARKS.md` |

## 🛠 Contributing
Small, tested PRs welcome. Preserve backward compatibility of receipt fields; add new diagnostics additively. See `CONTRIBUTING.md`.

## 🔐 License
Business Source License 1.1 → converts to Apache 2.0 on **2028‑10‑05**. Evaluation & internal non‑prod use are free; commercial prod use requires a commercial grant until the change date. See `LICENSE` + `docs/LICENSING.md`.

> Elevator: *ConsciousDB turns your existing vector database into the model—an explainable, structure‑aware ranking layer with auditable energy receipts instead of another opaque reranker.*
