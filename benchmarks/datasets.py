"""Dataset loaders for benchmarking.

Currently supports three dataset *modes*:

1. ``synthetic`` – small randomly generated corpus with constructed relevance
     (fast, deterministic, zero external downloads).
2. ``msmarco`` – lightweight in-repo sample of MS MARCO passage style queries
     (NOT the full dataset; the full collection is very large and must be
     prepared externally). Function `load_msmarco` returns a sample batch list
     derived from an embedded miniature subset for quick harness wiring.
3. ``nq`` – lightweight sample of Natural Questions style queries.

The real, large-scale datasets require manual preprocessing into JSONL files
(`queries.jsonl`, `qrels.jsonl`) plus a vectorized corpus. To keep this
repository slim and license-safe we *do not* auto-download the corpora.
Instead we expose helper loaders that:

* First attempt to locate a prepared JSONL set in a cache directory
    (``~/.cache/consciousdb/benchmarks/<dataset>/``) if environment variable
    ``CONSCIOUSDB_CACHE_DIR`` is provided or default path exists.
* If not found, fall back to the embedded miniature samples so that the
    benchmark harness remains runnable end-to-end for demonstration & tests.

Follow-up (future): add a preprocessing script that converts official MS MARCO
TSV and NQ JSON into the expected simplified JSONL format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import json
from typing import Iterable

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
        batches.append(
            BenchmarkBatch(
                query=Query(id=f"q{qi}", text=f"synthetic query {qi}"),
                gold=[ids[t] for t in top],
            )
        )
    return batches, corpus, ids


# ---------------------------------------------------------------------------
# Embedded miniature samples (small enough for tests)
# ---------------------------------------------------------------------------
_MSMARCO_SAMPLE = [
    {"id": "q1", "text": "what is a vector database", "relevant_ids": ["d1", "d7"]},
    {"id": "q2", "text": "benefits of coherence optimization", "relevant_ids": ["d3"]},
    {"id": "q3", "text": "define structural reranking", "relevant_ids": ["d5", "d9"]},
]

_NQ_SAMPLE = [
    {"id": "nq1", "text": "who wrote the iliad", "relevant_ids": ["nq_d2"]},
    {"id": "nq2", "text": "capital of new zealand", "relevant_ids": ["nq_d4"]},
    {"id": "nq3", "text": "largest desert on earth", "relevant_ids": ["nq_d6"]},
]


def _cache_dir() -> Path:
    base = os.environ.get("CONSCIOUSDB_CACHE_DIR", None)
    if base:
        return Path(base).expanduser() / "benchmarks"
    return Path.home() / ".cache" / "consciousdb" / "benchmarks"


def _load_external_or_sample(dataset: str, sample: list[dict]) -> list[dict]:
    """Attempt to load preprocessed JSONL else fall back to embedded sample.

    Expected layout if present:
        <cache>/<dataset>/queries.jsonl
        <cache>/<dataset>/qrels.jsonl  (schema: {"query_id":..., "relevant_ids":[...]})
    """
    cache_root = _cache_dir() / dataset
    queries_p = cache_root / "queries.jsonl"
    qrels_p = cache_root / "qrels.jsonl"
    if queries_p.exists() and qrels_p.exists():
        queries = {q["id"]: q for q in load_jsonl(queries_p)}
        out: list[dict] = []
        for r in load_jsonl(qrels_p):
            qid = r["query_id"]
            out.append({"id": qid, "text": queries[qid]["text"], "relevant_ids": r["relevant_ids"]})
        return out
    # Fallback to baked sample
    return sample


def _sample_batches(records: list[dict], sample_size: int, seed: int) -> list[BenchmarkBatch]:
    if sample_size >= len(records):
        chosen = records
    else:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(records), size=sample_size, replace=False)
        chosen = [records[i] for i in idx]
    return [BenchmarkBatch(query=Query(id=r["id"], text=r["text"]), gold=r["relevant_ids"]) for r in chosen]


def load_msmarco(sample_size: int = 50, seed: int = 0) -> list[BenchmarkBatch]:
    """Load a sample of MS MARCO passage queries.

    If a cached preprocessed dataset is present it will be sampled; otherwise a
    tiny embedded sample (3 queries) is used. ``sample_size`` larger than the
    available records is clamped.
    """
    records = _load_external_or_sample("msmarco", _MSMARCO_SAMPLE)
    return _sample_batches(records, sample_size=sample_size, seed=seed)


def load_nq(sample_size: int = 50, seed: int = 0) -> list[BenchmarkBatch]:
    """Load a sample of Natural Questions queries (mini subset)."""
    records = _load_external_or_sample("nq", _NQ_SAMPLE)
    return _sample_batches(records, sample_size=sample_size, seed=seed)


def build_random_corpus_from_gold(batches: Iterable[BenchmarkBatch], dim: int, seed: int = 0) -> tuple[np.ndarray, list[str]]:
    """Utility: build random normalized vectors for the union of gold IDs.

    This allows the harness to compute a *placeholder* cosine baseline when
    real corpus embeddings are not materialized. It is **not** a substitute
    for evaluating against the actual corpus; use only for quick sanity tests
    of dataset wiring.
    """
    ids: list[str] = sorted({doc for b in batches for doc in b.gold})
    rng = np.random.default_rng(seed)
    mat = rng.normal(size=(len(ids), dim)).astype(np.float32)
    mat /= (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    return mat, ids
