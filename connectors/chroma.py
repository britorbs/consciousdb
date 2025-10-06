from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from .base import BaseConnector

logger = logging.getLogger(__name__)


class ChromaConnector(BaseConnector):
    """Chroma DB connector.

    Uses the HTTP / persistent client depending on installation. We assume the
    server is reachable at `host` (e.g. http://localhost:8000). Chroma's client
    surfaces embeddings on query when `include` contains 'embeddings'.
    """

    def __init__(self, host: str, collection: str, max_retries: int = 3):
        try:
            import chromadb  # runtime import (optional dependency)
            from chromadb.config import Settings as ChromaSettings
        except Exception as e:  # pragma: no cover - import guard
            raise RuntimeError("chromadb not installed. Install with 'pip install .[connectors-chroma]'") from e
        # Initialize REST client (strip protocol if provided).
        host_slim = host.replace("http://", "").replace("https://", "")
        self._client = chromadb.Client(
            ChromaSettings(
                chroma_api_impl="rest",
                chroma_server_host=host_slim,
            )
        )  # naive host parse
        self.collection_name = collection
        self.max_retries = max_retries
        self._collection = None

    def _col(self):
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(self.collection_name)
        return self._collection

    def _retry(self, op: str, fn: Callable[[], Any]):
        delay = 0.25
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn()
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error("chroma_%s_failed", op, extra={"attempt": attempt, "error": str(e)})
                    raise
                logger.warning(
                    "chroma_%s_retry", op, extra={"attempt": attempt, "error": str(e), "sleep_s": round(delay, 3)}
                )
                time.sleep(delay)
                delay = min(delay * 2, 2.0)

    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray | None]]:  # noqa: D401
        if m <= 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).ravel()
        if q.ndim != 1:
            raise ValueError("query_vec must be 1-D")
        collection = self._col()

        def _do_query():  # wrapped for retry; keep args explicit
            return collection.query(
                query_embeddings=[q.tolist()],
                n_results=int(m),
                include=[
                    "embeddings",
                    "distances",
                    "metadatas",
                    "documents",
                ],
            )

        res = self._retry("query", _do_query)
        ids = (res.get("ids") or [[]])[0]
        # Chroma returns distances; if they are cosine distances (1 - sim) we attempt to invert.
        dists = (res.get("distances") or [[]])[0]
        emb_list = (res.get("embeddings") or [[]])[0]
        out: list[tuple[str, float, np.ndarray | None]] = []
        for i, vid in enumerate(ids):
            dist = float(dists[i]) if i < len(dists) else 0.0
            # if distance is cosine distance treat similarity = 1 - dist (bounded)
            sim = 1.0 - dist
            emb = np.asarray(emb_list[i], dtype=np.float32) if i < len(emb_list) else None
            out.append((str(vid), sim, emb))
        return out

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:  # noqa: D401
        if not ids:
            return np.zeros((0, 0), dtype=np.float32)
        collection = self._col()

        def _do_get():
            return collection.get(ids=ids, include=["embeddings"])

        res = self._retry("get", _do_get)
        got_ids = res.get("ids") or []
        emb_list = res.get("embeddings") or []
        if len(got_ids) != len(ids):
            missing = set(ids) - set(got_ids)
            if missing:
                raise KeyError(f"Missing embeddings for ids: {sorted(missing)[:5]} (showing up to 5)")
        # Maintain requested order
        id_to_emb = {gid: np.asarray(emb_list[i], dtype=np.float32) for i, gid in enumerate(got_ids)}
        arrs = [id_to_emb[g] for g in ids]
        return np.vstack(arrs).astype(np.float32)
