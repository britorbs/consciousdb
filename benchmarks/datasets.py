from __future__ import annotations

"""Dataset loader stubs for benchmarking.

Real MS MARCO / Natural Questions integration requires downloading the
public datasets. To avoid licensing / large downloads inside the base
repo, we provide thin adapters expecting preprocessed JSONL.

Expected JSONL schema examples:
- queries.jsonl: {"id": "q1", "text": "what is coherence"}
- corpus.jsonl: {"id": "doc123", "text": "..."}
- qrels.jsonl: {"query_id": "q1", "relevant_ids": ["doc42", "doc77"]}

Synthetic loader creates a small random embedding-backed corpus for rapid smoke.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Query:
    id: str
    text: str


@dataclass
class CorpusItem:
    id: str
    text: str


@dataclass
class QRel:
    query_id: str
    relevant_ids: list[str]


@dataclass
class BenchmarkBatch:
    query: Query
    gold: list[str]


def load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            import json

            out.append(json.loads(line))
    return out


def load_dataset(root: str) -> list[BenchmarkBatch]:
    root_path = Path(root)
    qrels = load_jsonl(root_path / "qrels.jsonl")
    queries = {r["id"]: Query(id=r["id"], text=r["text"]) for r in load_jsonl(root_path / "queries.jsonl")}
    batches: list[BenchmarkBatch] = []
    for qr in qrels:
        qid = qr["query_id"]
        batches.append(BenchmarkBatch(query=queries[qid], gold=qr["relevant_ids"]))
    return batches


def synthetic_dataset(n_queries: int = 25, dim: int = 32) -> tuple[list[BenchmarkBatch], np.ndarray, list[str]]:
    """Produce a synthetic dataset with a ground-truth vector for each query.

    For each query we mark top-3 nearest corpus vectors (by cosine) as relevant.
    """
    rng = np.random.default_rng(0)
    corpus_size = 500
    corpus = rng.normal(size=(corpus_size, dim)).astype(np.float32)
    corpus /= (np.linalg.norm(corpus, axis=1, keepdims=True) + 1e-12)
    ids = [f"doc:{i}" for i in range(corpus_size)]
    batches: list[BenchmarkBatch] = []
    for qi in range(n_queries):
        qv = rng.normal(size=(dim,)).astype(np.float32)
        qv /= (np.linalg.norm(qv) + 1e-12)
        sims = corpus @ qv
        top = np.argsort(-sims)[:3]
        batches.append(BenchmarkBatch(query=Query(id=f"q{qi}", text=f"synthetic query {qi}"), gold=[ids[t] for t in top]))
    return batches, corpus, ids
