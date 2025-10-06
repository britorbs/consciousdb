from __future__ import annotations

from collections.abc import Sequence
from typing import Callable, Tuple


# --------------------- Core Metric Primitives ---------------------
def dcg(relevances: Sequence[float]) -> float:
    """Discounted cumulative gain (log2)."""
    import math

    return sum((rel / math.log2(i + 2)) for i, rel in enumerate(relevances))


def ndcg_at_k(pred_ids: list[str], gold_ids: list[str], k: int) -> float:
    """Compute nDCG@k with binary relevance (1 if in gold)."""
    if k <= 0:
        return 0.0
    if not gold_ids:
        return 0.0
    ideal = [1.0] * min(k, len(gold_ids))
    ideal_dcg = dcg(ideal) or 1.0
    rels = [1.0 if pid in gold_ids else 0.0 for pid in pred_ids[:k]]
    return dcg(rels) / ideal_dcg


def mrr_at_k(pred_ids: list[str], gold_ids: list[str], k: int) -> float:
    """Compute MRR@k with binary relevance set gold_ids."""
    for i, pid in enumerate(pred_ids[:k]):
        if pid in gold_ids:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(pred_ids: list[str], gold_ids: list[str], k: int) -> float:
    """Recall@k = |relevant retrieved in top-k| / |relevant| (binary)."""
    if k <= 0 or not gold_ids:
        return 0.0
    top = set(pred_ids[:k])
    rel_retrieved = sum(1 for g in gold_ids if g in top)
    return rel_retrieved / len(gold_ids)


def ap_at_k(pred_ids: list[str], gold_ids: list[str], k: int) -> float:
    """Average Precision@k for binary relevance.

    AP = sum( precision@i * rel_i ) / min(|gold|, k) over i in 1..k
    where rel_i = 1 if the i-th retrieved item is relevant.
    """
    if k <= 0 or not gold_ids:
        return 0.0
    gold_set = set(gold_ids)
    hits = 0
    precisions = 0.0
    denom = min(len(gold_set), k)
    for i, pid in enumerate(pred_ids[:k], start=1):
        if pid in gold_set:
            hits += 1
            precisions += hits / i
    if denom == 0:
        return 0.0
    return precisions / denom


# --------------------- Aggregation Helpers ---------------------
def aggregate_metric(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    import numpy as np

    return float(np.percentile(values, pct))


# --------------------- Bootstrap Confidence Intervals ---------------------
def bootstrap_ci(
    values: list[float],
    n_boot: int = 1000,
    seed: int | None = None,
    ci: float = 0.95,
    agg: Callable[[list[float]], float] = aggregate_metric,
) -> Tuple[float, float, float]:
    """Return (mean, lower, upper) non-parametric bootstrap CI.

    Uses simple iid resampling with replacement. If insufficient samples (<2) or
    n_boot <= 0, returns the aggregate value with identical bounds.
    """
    if not values:
        return 0.0, 0.0, 0.0
    point = agg(values)
    if len(values) < 2 or n_boot <= 0:
        return point, point, point
    import numpy as np

    rng = np.random.default_rng(seed)
    samples = []
    n = len(values)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        resample = [values[i] for i in idx]
        samples.append(agg(resample))
    alpha = (1 - ci) / 2.0
    lower = float(np.quantile(samples, alpha))
    upper = float(np.quantile(samples, 1 - alpha))
    return point, lower, upper

