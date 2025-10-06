from __future__ import annotations

"""Benchmark runner comparing vanilla cosine vs ConsciousDB coherence ranking.

Usage (synthetic quick run):

    python -m benchmarks.run_benchmark --synthetic --queries 50 --k 10 --m 400 \
        --output benchmark_report.md --json benchmark_report.json

For real datasets provide --dataset-root pointing to a folder with
queries.jsonl, qrels.jsonl and ensure the sidecar is running on an API
URL you pass via --api.
"""

import argparse
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests

from .datasets import load_dataset, synthetic_dataset
from .metrics import aggregate_metric, mrr_at_k, ndcg_at_k, percentile

DEFAULT_API = os.getenv("CONSCIOUSDB_API", "http://localhost:8080")


@dataclass
class MethodResult:
    name: str
    ndcgs: list[float]
    mrrs: list[float]
    latencies_ms: list[float]
    deltaH: list[float]

    def summary(self, k: int) -> dict:
        return {
            "method": self.name,
            "nDCG@%d" % k: round(aggregate_metric(self.ndcgs), 4),
            "MRR@%d" % k: round(aggregate_metric(self.mrrs), 4),
            "P95_latency_ms": round(percentile(self.latencies_ms, 95), 2),
            "avg_deltaH": round(aggregate_metric(self.deltaH), 4),
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
    if args.synthetic:
        batches, corpus, ids = synthetic_dataset(n_queries=args.queries, dim=args.dim)
    else:
        batches = load_dataset(args.dataset_root)
        # For external dataset you would pre-compute / load corpus vectors here.
        raise NotImplementedError("Non-synthetic embedding flow not implemented in this quick benchmark stub.")

    # Baseline: pure cosine (vector-only)
    baseline = MethodResult("Cosine", [], [], [], [])
    coh = MethodResult("ConsciousDB", [], [], [], [])
    coh_mmr = MethodResult("ConsciousDB+MMR", [], [], [], [])

    for b in batches:
        qv = embed_query_local(b.query.text, args.dim)
        # Baseline
        t0 = time.perf_counter()
        pred_cos = cosine_search(corpus, ids, qv, args.k, args.m)
        baseline.latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        baseline.ndcgs.append(ndcg_at_k(pred_cos, b.gold, args.k))
        baseline.mrrs.append(mrr_at_k(pred_cos, b.gold, args.k))
        baseline.deltaH.append(0.0)

        # ConsciousDB (call API)
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
        t1 = time.perf_counter()
        r = requests.post(f"{args.api}/query", json=payload, timeout=60)
        elapsed = (time.perf_counter() - t1) * 1000.0
        if r.status_code != 200:
            print("API error", r.status_code, r.text)
            continue
        jd = r.json()
        returned_ids = [it["id"] for it in jd.get("items", [])]
        coh.latencies_ms.append(elapsed)
        coh.ndcgs.append(ndcg_at_k(returned_ids, b.gold, args.k))
        coh.mrrs.append(mrr_at_k(returned_ids, b.gold, args.k))
        coh.deltaH.append(float(jd.get("diagnostics", {}).get("deltaH_total", 0.0)))

        # ConsciousDB + forced MMR
        payload["overrides"]["use_mmr"] = True
        t2 = time.perf_counter()
        r2 = requests.post(f"{args.api}/query", json=payload, timeout=60)
        elapsed2 = (time.perf_counter() - t2) * 1000.0
        if r2.status_code != 200:
            print("API error (MMR)", r2.status_code, r2.text)
            continue
        jd2 = r2.json()
        returned_ids2 = [it["id"] for it in jd2.get("items", [])]
        coh_mmr.latencies_ms.append(elapsed2)
        coh_mmr.ndcgs.append(ndcg_at_k(returned_ids2, b.gold, args.k))
        coh_mmr.mrrs.append(mrr_at_k(returned_ids2, b.gold, args.k))
        coh_mmr.deltaH.append(float(jd2.get("diagnostics", {}).get("deltaH_total", 0.0)))

    methods = [baseline, coh, coh_mmr]
    # Summaries
    summaries = [m.summary(args.k) for m in methods]
    # Compute uplifts vs baseline
    base_ndcg = summaries[0][f"nDCG@{args.k}"] or 1e-9
    base_mrr = summaries[0][f"MRR@{args.k}"] or 1e-9
    for s in summaries[1:]:
        s["nDCG_uplift_pct"] = round(100.0 * (s[f"nDCG@{args.k}"] - base_ndcg) / base_ndcg, 2)
        s["MRR_uplift_pct"] = round(100.0 * (s[f"MRR@{args.k}"] - base_mrr) / base_mrr, 2)

    report = {
        "k": args.k,
        "m": args.m,
        "queries": len(batches),
        "api": args.api,
        "methods": summaries,
        "notes": "Synthetic benchmark. Real dataset integration requires preprocessed embeddings.",
    }

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.output:
        lines = ["# Benchmark Results", "", f"Queries: {len(batches)}  |  k={args.k}  m={args.m}", ""]
        header = f"| Method | nDCG@{args.k} | MRR@{args.k} | P95 Lat (ms) | Avg ΔH | Explainability | nDCG Uplift % | MRR Uplift % |"
        lines.append(header)
        lines.append("|--------|---------|-------|-------------|--------|---------------|---------------|--------------|")
        for s in summaries:
            lines.append(
                f"| {s['method']} | {s[f'nDCG@{args.k}']:.4f} | {s[f'MRR@{args.k}']:.4f} | {s['P95_latency_ms']:.1f} | {s['avg_deltaH']:.4f} | {s['explainability']} | {s.get('nDCG_uplift_pct','-') if s['method']!='Cosine' else '-'} | {s.get('MRR_uplift_pct','-') if s['method']!='Cosine' else '-'} |"
            )
        Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Written", args.output)

    print(json.dumps(report, indent=2))


def main():  # noqa: D401
    p = argparse.ArgumentParser(description="Run ConsciousDB benchmarks")
    p.add_argument("--api", default=DEFAULT_API, help="Base URL of running sidecar API")
    p.add_argument("--synthetic", action="store_true", help="Use synthetic dataset")
    p.add_argument("--dataset-root", help="Path to dataset root (queries.jsonl/qrels.jsonl)")
    p.add_argument("--queries", type=int, default=25)
    p.add_argument("--dim", type=int, default=32)
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--m", type=int, default=400)
    p.add_argument("--output", help="Markdown output file")
    p.add_argument("--json", help="JSON output file")
    args = p.parse_args()
    if not args.synthetic and not args.dataset_root:
        p.error("Provide --synthetic or --dataset-root")
    run(args)


if __name__ == "__main__":  # pragma: no cover
    main()
