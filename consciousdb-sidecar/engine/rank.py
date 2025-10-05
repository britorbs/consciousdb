from __future__ import annotations
import numpy as np

def zscore(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    mu = float(np.mean(x))
    sd = float(np.std(x))
    if sd < 1e-6:
        # Stabilize: if variance ~0 return zeros to avoid amplifying noise
        return np.zeros_like(x, dtype=np.float32)
    return (x - mu) / (sd + 1e-12)

def mmr(ids, vectors, scores, lambda_mmr=0.3, k=8):
    ids = list(ids)
    V = vectors
    selected = []
    remaining = set(range(len(ids)))
    out = []
    while remaining and len(out) < k:
        best_j = None
        best_val = -1e9
        for j in list(remaining):
            rel = scores[j]
            redund = 0.0
            if selected:
                redund = max(float(np.dot(V[j], V[s])) for s in selected)
            val = lambda_mmr * rel - (1.0 - lambda_mmr) * redund
            if val > best_val:
                best_val = val
                best_j = j
        selected.append(best_j); remaining.remove(best_j); out.append(ids[best_j])
    return out
