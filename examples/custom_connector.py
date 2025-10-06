"""Custom connector example.

Shows how to implement a minimal connector that wraps an existing list of
(pre-embedded) documents. In a real system the embeddings would be produced
at ingestion time and stored alongside IDs.

Run:
    python examples/custom_connector.py
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from consciousdb import Config, ConsciousClient


@dataclass
class Doc:
    id: str
    text: str
    vec: np.ndarray


class ListConnector:
    """Connector built around a Python list of Doc objects."""

    def __init__(self, docs: list[Doc]):
        self.docs = docs
        self._id_to_idx = {d.id: i for i, d in enumerate(docs)}
        self._mat = np.vstack([d.vec for d in docs]).astype("float32")

    def top_m(self, query_vec: np.ndarray, m: int):  # noqa: D401
        q = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        sims = self._mat @ q
        order = np.argsort(-sims)[:m]
        return [(self.docs[i].id, float(sims[i]), self.docs[i].vec) for i in order]

    def fetch_vectors(self, ids: list[str]):  # noqa: D401
        return np.vstack([self.docs[self._id_to_idx[i]].vec for i in ids])


class HashEmbedder:
    def embed(self, text: str):  # noqa: D401
        seed = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(32).astype("float32")
        v /= np.linalg.norm(v) + 1e-12
        return v


def build_docs(n: int) -> list[Doc]:
    rng = np.random.default_rng(123)
    docs: list[Doc] = []
    for i in range(n):
        # Synthetic text (embedding randomness not derived from text here for clarity)
        text = f"synthetic document {i} about graphs"
        vec = rng.standard_normal(32).astype("float32")
        vec /= np.linalg.norm(vec) + 1e-12
        docs.append(Doc(id=f"doc{i}", text=text, vec=vec))
    return docs


def main():  # noqa: D401
    docs = build_docs(40)
    connector = ListConnector(docs)
    embedder = HashEmbedder()
    client = ConsciousClient(connector=connector, embedder=embedder, config=Config())

    q = "graph regularization"
    res = client.query(q, k=5, m=30)
    print("Query:", q)
    for it in res.items:
        print(f"  {it.id}\tscore={it.score:.4f}")


if __name__ == "__main__":  # pragma: no cover
    main()
