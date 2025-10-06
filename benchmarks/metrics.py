from __future__ import annotations

from typing import List, Sequence


def dcg(relevances: Sequence[float]) -> float:
    """Discounted cumulative gain (log2)."""
    import math

    return sum((rel / math.log2(i + 2)) for i, rel in enumerate(relevances))


def ndcg_at_k(pred_ids: List[str], gold_ids: List[str], k: int) -> float:
    """Compute nDCG@k with binary relevance (1 if in gold)."""
    if k <= 0:
        return 0.0
    ideal = [1.0] * min(k, len(gold_ids))
    ideal_dcg = dcg(ideal) or 1.0
    rels = [1.0 if pid in gold_ids else 0.0 for pid in pred_ids[:k]]
    return dcg(rels) / ideal_dcg


def mrr_at_k(pred_ids: List[str], gold_ids: List[str], k: int) -> float:
    """Compute MRR@k with binary relevance set gold_ids."""
    for i, pid in enumerate(pred_ids[:k]):
        if pid in gold_ids:
            return 1.0 / (i + 1)
    return 0.0


def aggregate_metric(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    import numpy as np

    return float(np.percentile(values, pct))
