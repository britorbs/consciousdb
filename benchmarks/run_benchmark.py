"""Benchmark runner comparing baseline cosine vs ConsciousDB ranking.

Modes:
  * Synthetic: fully self-contained random corpus (fast demo).
  * MS MARCO / NQ: uses dataset loader samples (either cached preprocessed
    JSONL or miniature embedded samples). For real evaluation you must ingest
    the actual corpus into your vector backend; this script's random corpus
    construction is only a placeholder for quality harness wiring.

Examples:
  Synthetic quick run
      python -m benchmarks.run_benchmark --dataset synthetic --queries 50 --k 10 --m 400 --output bench.md --json bench.json

  MS MARCO sample without API (baseline only wiring)
      python -m benchmarks.run_benchmark --dataset msmarco --queries 20 --k 10 --m 200 --no-api

  NQ sample attempting API methods (requires real ingestion)
      python -m benchmarks.run_benchmark --dataset nq --k 10 --m 400 --api http://localhost:8080
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests

from .datasets import (
    synthetic_dataset,
    load_msmarco,
    load_nq,
    build_random_corpus_from_gold,
)
from .metrics import (
    aggregate_metric,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
    ap_at_k,
    percentile,
    bootstrap_ci,
)

DEFAULT_API = os.getenv("CONSCIOUSDB_API", "http://localhost:8080")


@dataclass
class MethodResult:
    name: str
    ndcgs: list[float]
    mrrs: list[float]
    recalls: list[float]
    maps: list[float]
    latencies_ms: list[float]
    delta_h: list[float]

    def summary(self, k: int, bootstrap: bool = False, boots: int = 0, seed: int | None = None) -> dict:
        ndcg_mean = aggregate_metric(self.ndcgs)
        mrr_mean = aggregate_metric(self.mrrs)
        recall_mean = aggregate_metric(self.recalls)
        map_mean = aggregate_metric(self.maps)
        if bootstrap and boots > 0:
            ndcg_ci = bootstrap_ci(self.ndcgs, n_boot=boots, seed=seed)
            mrr_ci = bootstrap_ci(self.mrrs, n_boot=boots, seed=seed + 1 if seed is not None else None)
            recall_ci = bootstrap_ci(self.recalls, n_boot=boots, seed=seed + 2 if seed is not None else None)
            map_ci = bootstrap_ci(self.maps, n_boot=boots, seed=seed + 3 if seed is not None else None)
        else:
            ndcg_ci = (ndcg_mean, ndcg_mean, ndcg_mean)
            mrr_ci = (mrr_mean, mrr_mean, mrr_mean)
            recall_ci = (recall_mean, recall_mean, recall_mean)
            map_ci = (map_mean, map_mean, map_mean)
        return {
            "method": self.name,
            f"nDCG@{k}": round(ndcg_mean, 4),
            f"nDCG@{k}_ci": [round(x, 4) for x in ndcg_ci],
            f"MRR@{k}": round(mrr_mean, 4),
            f"MRR@{k}_ci": [round(x, 4) for x in mrr_ci],
            f"Recall@{k}": round(recall_mean, 4),
            f"Recall@{k}_ci": [round(x, 4) for x in recall_ci],
            f"MAP@{k}": round(map_mean, 4),
            f"MAP@{k}_ci": [round(x, 4) for x in map_ci],
            "P95_latency_ms": round(percentile(self.latencies_ms, 95), 2),
            "avg_deltaH": round(aggregate_metric(self.delta_h), 4),
            "explainability": "receipt" if self.name.startswith("ConsciousDB") else "none",
        }


def cosine_search(corpus_vecs: np.ndarray, ids: Sequence[str], query_vec: np.ndarray, k: int, m: int) -> list[str]:
    sims = corpus_vecs @ query_vec
    order = np.argsort(-sims)[:m]
    # Take top-k reranked (here same because no rerank logic)
    return [ids[i] for i in order[:k]]


def embed_query_local(q: str, dim: int) -> np.ndarray:
    # Placeholder deterministic embedding for synthetic benchmark (mirrors memory connector style)
    import hashlib

    h = hashlib.sha256(q.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(h[:4], "little"))
    v = rng.normal(size=(dim,)).astype(np.float32)
    v /= (np.linalg.norm(v) + 1e-12)
    return v


def run(args: argparse.Namespace):
    # ---------------- Dataset selection ----------------
    if args.dataset == "synthetic" or args.synthetic:  # legacy flag compat
        batches, corpus, ids = synthetic_dataset(n_queries=args.queries, dim=args.dim)
    elif args.dataset == "msmarco":
        batches = load_msmarco(sample_size=args.queries, seed=args.seed)
        corpus, ids = build_random_corpus_from_gold(batches, dim=args.dim, seed=args.seed)
    elif args.dataset == "nq":
        batches = load_nq(sample_size=args.queries, seed=args.seed)
        corpus, ids = build_random_corpus_from_gold(batches, dim=args.dim, seed=args.seed)
    else:
        raise ValueError(f"Unknown dataset: {args.dataset}")

    # Baseline: pure cosine (vector-only)
    baseline = MethodResult("Cosine", [], [], [], [], [], [])
    reranker_method: MethodResult | None = None
    coh = MethodResult("ConsciousDB", [], [], [], [], [], [])
    coh_mmr = MethodResult("ConsciousDB+MMR", [], [], [], [], [], [])

    # Optional reranker model (lazy load)
    reranker_model = None
    if args.reranker:
        try:  # pragma: no cover - heavy model path not unit tested
            from sentence_transformers import CrossEncoder  # type: ignore

            model_name = args.reranker_model or "cross-encoder/ms-marco-MiniLM-L-6-v2"
            t_load = time.perf_counter()
            reranker_model = CrossEncoder(model_name, trust_remote_code=True)
            load_ms = (time.perf_counter() - t_load) * 1000.0
            print(f"Loaded reranker model '{model_name}' in {load_ms:.0f} ms")
            reranker_method = MethodResult(f"Reranker({model_name.split('/')[-1]})", [], [], [], [], [], [])
        except Exception as e:  # pragma: no cover
            print("Failed to load reranker model (disable with --no-reranker):", e)
            args.reranker = False

    for b in batches:
        qv = embed_query_local(b.query.text, args.dim)
        # Baseline (vector-only ANN + cosine) retrieving top-m then slicing to k
        t0 = time.perf_counter()
        sims = corpus @ qv
        order = np.argsort(-sims)[: args.m]
        candidate_ids = [ids[i] for i in order]
        pred_cos = candidate_ids[: args.k]
        baseline.latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        baseline.ndcgs.append(ndcg_at_k(pred_cos, b.gold, args.k))
        baseline.mrrs.append(mrr_at_k(pred_cos, b.gold, args.k))
        baseline.recalls.append(recall_at_k(pred_cos, b.gold, args.k))
        baseline.maps.append(ap_at_k(pred_cos, b.gold, args.k))
        baseline.delta_h.append(0.0)

        # Optional reranker baseline (cross-encoder rescoring top-m)
        if reranker_model and reranker_method is not None:
            try:  # pragma: no cover - network/model path
                t_r0 = time.perf_counter()
                # Placeholder text: use doc id (real evaluation should pass actual doc text)
                pairs = [(b.query.text, doc_id) for doc_id in candidate_ids]
                scores = reranker_model.predict(pairs)  # type: ignore[attr-defined]
                order_r = np.argsort(-np.array(scores))[: args.k]
                pred_rr = [candidate_ids[i] for i in order_r]
                reranker_method.latencies_ms.append((time.perf_counter() - t_r0) * 1000.0)
                reranker_method.ndcgs.append(ndcg_at_k(pred_rr, b.gold, args.k))
                reranker_method.mrrs.append(mrr_at_k(pred_rr, b.gold, args.k))
                reranker_method.recalls.append(recall_at_k(pred_rr, b.gold, args.k))
                reranker_method.maps.append(ap_at_k(pred_rr, b.gold, args.k))
                reranker_method.delta_h.append(0.0)
            except Exception as e:  # pragma: no cover
                print("Reranker failure:", e)

        if args.no_api:
            continue

        # ConsciousDB default
        payload = {
            "query": b.query.text,
            "k": args.k,
            "m": args.m,
            "overrides": {
                "alpha_deltaH": 0.1,
                "similarity_gap_margin": 0.15,
                "coh_drop_min": 0.0,
                "expand_when_gap_below": 0.05,
                "iters_cap": 20,
                "residual_tol": 0.001,
                "use_mmr": False,
            },
            "receipt_detail": 1,
        }
        try:
            t1 = time.perf_counter()
            r = requests.post(f"{args.api}/query", json=payload, timeout=60)
            elapsed = (time.perf_counter() - t1) * 1000.0
            if r.status_code == 200:
                jd = r.json()
                returned_ids = [it["id"] for it in jd.get("items", [])]
                coh.latencies_ms.append(elapsed)
                coh.ndcgs.append(ndcg_at_k(returned_ids, b.gold, args.k))
                coh.mrrs.append(mrr_at_k(returned_ids, b.gold, args.k))
                coh.recalls.append(recall_at_k(returned_ids, b.gold, args.k))
                coh.maps.append(ap_at_k(returned_ids, b.gold, args.k))
                coh.delta_h.append(float(jd.get("diagnostics", {}).get("deltaH_total", 0.0)))
            else:  # pragma: no cover - network error path
                print("API error", r.status_code)
        except Exception as e:  # pragma: no cover - network path
            print("API request failed:", e)

        # ConsciousDB + MMR
        payload["overrides"]["use_mmr"] = True
        try:
            t2 = time.perf_counter()
            r2 = requests.post(f"{args.api}/query", json=payload, timeout=60)
            elapsed2 = (time.perf_counter() - t2) * 1000.0
            if r2.status_code == 200:
                jd2 = r2.json()
                returned_ids2 = [it["id"] for it in jd2.get("items", [])]
                coh_mmr.latencies_ms.append(elapsed2)
                coh_mmr.ndcgs.append(ndcg_at_k(returned_ids2, b.gold, args.k))
                coh_mmr.mrrs.append(mrr_at_k(returned_ids2, b.gold, args.k))
                coh_mmr.recalls.append(recall_at_k(returned_ids2, b.gold, args.k))
                coh_mmr.maps.append(ap_at_k(returned_ids2, b.gold, args.k))
                coh_mmr.delta_h.append(float(jd2.get("diagnostics", {}).get("deltaH_total", 0.0)))
            else:  # pragma: no cover
                print("API error (MMR)", r2.status_code)
        except Exception as e:  # pragma: no cover
            print("API request (MMR) failed:", e)

    methods = [baseline]
    if reranker_method is not None:
        methods.append(reranker_method)
    if not args.no_api:
        methods.extend([coh, coh_mmr])
    # Summaries
    summaries = [m.summary(args.k, bootstrap=args.bootstrap, boots=args.boots, seed=args.seed) for m in methods]
    # Compute uplifts vs baseline
    base_ndcg = summaries[0][f"nDCG@{args.k}"] or 1e-9
    base_mrr = summaries[0][f"MRR@{args.k}"] or 1e-9
    base_recall = summaries[0][f"Recall@{args.k}"] or 1e-9
    base_map = summaries[0][f"MAP@{args.k}"] or 1e-9
    for s in summaries[1:]:
        s["nDCG_uplift_pct"] = round(100.0 * (s[f"nDCG@{args.k}"] - base_ndcg) / base_ndcg, 2)
        s["MRR_uplift_pct"] = round(100.0 * (s[f"MRR@{args.k}"] - base_mrr) / base_mrr, 2)
        s["Recall_uplift_pct"] = round(100.0 * (s[f"Recall@{args.k}"] - base_recall) / base_recall, 2)
        s["MAP_uplift_pct"] = round(100.0 * (s[f"MAP@{args.k}"] - base_map) / base_map, 2)

    report = {
        "k": args.k,
        "m": args.m,
        "queries": len(batches),
        "api": args.api,
        "bootstrap": args.bootstrap,
        "methods": summaries,
        "notes": "Benchmark run. Real dataset integration requires preprocessed embeddings for non-synthetic modes.",
    }

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.output:
        lines = [
            "# Benchmark Results",
            "",
            f"Queries: {len(batches)}  |  k={args.k}  m={args.m}",
            "",
        ]
        header = (
            f"| Method | nDCG@{args.k} | MRR@{args.k} | Recall@{args.k} | MAP@{args.k} | P95 Lat (ms) | Avg ΔH | Explainability | nDCG Uplift % | MRR Uplift % | Recall Uplift % | MAP Uplift % |"
        )
        lines.append(header)
        lines.append(
            "|--------|---------|-------|-------------|---------|-------------|--------|---------------|---------------|--------------|----------------|--------------|"
        )
        for s in summaries:
            ndcg_val = s[f"nDCG@{args.k}"]
            mrr_val = s[f"MRR@{args.k}"]
            recall_val = s[f"Recall@{args.k}"]
            map_val = s[f"MAP@{args.k}"]
            p95 = s["P95_latency_ms"]
            avg_dh = s["avg_deltaH"]
            expl = s["explainability"]
            ndcg_u = s.get("nDCG_uplift_pct", "-") if s["method"] != "Cosine" else "-"
            mrr_u = s.get("MRR_uplift_pct", "-") if s["method"] != "Cosine" else "-"
            recall_u = s.get("Recall_uplift_pct", "-") if s["method"] != "Cosine" else "-"
            map_u = s.get("MAP_uplift_pct", "-") if s["method"] != "Cosine" else "-"
            line = (
                f"| {s['method']} | {ndcg_val:.4f} | {mrr_val:.4f} | {recall_val:.4f} | {map_val:.4f} | {p95:.1f} | {avg_dh:.4f} | {expl} | {ndcg_u} | {mrr_u} | {recall_u} | {map_u} |"
            )
            lines.append(line)
        Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Written", args.output)

    print(json.dumps(report, indent=2))


def main():  # noqa: D401
    p = argparse.ArgumentParser(description="Run ConsciousDB benchmarks")
    p.add_argument("--api", default=DEFAULT_API, help="Base URL of running sidecar API")
    p.add_argument(
        "--dataset",
        choices=["synthetic", "msmarco", "nq"],
        default="synthetic",
        help="Dataset selector (synthetic always available)",
    )
    p.add_argument("--synthetic", action="store_true", help="(Deprecated) use synthetic dataset")
    p.add_argument("--queries", type=int, default=25, help="Number of queries (sample size)")
    p.add_argument("--dim", type=int, default=32, help="Embedding dim for synthetic/random corpus")
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--m", type=int, default=400)
    p.add_argument("--seed", type=int, default=0, help="Random seed for sampling")
    p.add_argument("--no-api", action="store_true", help="Skip API calls (baseline only)")
    p.add_argument("--reranker", action="store_true", help="Include a cross-encoder reranker baseline (slow)")
    p.add_argument(
        "--reranker-model",
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        help="HuggingFace model id for cross-encoder reranker",
    )
    p.add_argument("--bootstrap", action="store_true", help="Enable bootstrap confidence intervals")
    p.add_argument("--boots", type=int, default=400, help="Number of bootstrap resamples (default 400)")
    p.add_argument("--output", help="Markdown output file")
    p.add_argument("--json", help="JSON output file")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":  # pragma: no cover
    main()
