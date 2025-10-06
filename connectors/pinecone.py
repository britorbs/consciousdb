from __future__ import annotations

import logging
import time
from typing import Callable

import numpy as np

from .base import BaseConnector

logger = logging.getLogger(__name__)


class PineconeConnector(BaseConnector):
    """Pinecone connector using the v3 python client.

    Returns vectors directly in `top_m` by querying with `include_values=True` to
    avoid a second round-trip when possible. Falls back on `fetch_vectors` if
    vectors were not requested or if an older index configuration disallows it.
    """

    def __init__(self, api_key: str, index_name: str, namespace: str | None = None, max_retries: int = 3):
        try:
            from pinecone import Pinecone  # type: ignore
        except Exception as e:  # pragma: no cover - import guard
            raise RuntimeError("pinecone-client not installed. Install with 'pip install .[connectors-pinecone]'") from e
        self._pc_cls = Pinecone  # store for potential lazy re-init
        self.api_key = api_key
        self.index_name = index_name
        self.namespace = namespace
        self.max_retries = max_retries
        # Lazy index init (fast import; network only on first call)
        self._client = None
        self._index = None

    # ------------------ internal helpers ------------------
    def _ensure_index(self):
        if self._index is None:
            if self._client is None:
                self._client = self._pc_cls(api_key=self.api_key)
            self._index = self._client.Index(self.index_name)
        return self._index

    def _retry(self, op: str, fn: Callable[[], any]):
        delay = 0.25
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn()
            except Exception as e:  # broad: network / service exceptions
                if attempt == self.max_retries:
                    logger.error("pinecone_%s_failed", op, extra={"attempt": attempt, "error": str(e)})
                    raise
                logger.warning(
                    "pinecone_%s_retry", op, extra={"attempt": attempt, "error": str(e), "sleep_s": round(delay, 3)}
                )
                time.sleep(delay)
                delay = min(delay * 2, 2.0)

    # ------------------ interface methods ------------------
    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray | None]]:  # noqa: D401
        if m <= 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).ravel()
        if q.ndim != 1:
            raise ValueError("query_vec must be 1-D")
        index = self._ensure_index()

        def _do_query():
            # include_values=True returns embedding directly (saves fetch round-trip)
            return index.query(
                vector=q.tolist(),
                top_k=int(m),
                include_values=True,
                namespace=self.namespace,
            )

        res = self._retry("query", _do_query)
        matches = getattr(res, "matches", []) or []
        out: list[tuple[str, float, np.ndarray | None]] = []
        for match in matches:
            vid = getattr(match, "id", None)
            score = getattr(match, "score", 0.0)
            values = getattr(match, "values", None)
            vec = np.asarray(values, dtype=np.float32) if values is not None else None
            if vid is None:
                continue
            out.append((str(vid), float(score), vec))
        return out

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:  # noqa: D401
        if not ids:
            return np.zeros((0, 0), dtype=np.float32)
        index = self._ensure_index()

        def _do_fetch():
            return index.fetch(ids=ids, namespace=self.namespace)

        res = self._retry("fetch", _do_fetch)
        vectors = getattr(res, "vectors", {}) or {}
        dim = None
        ordered: list[np.ndarray] = []
        for vid in ids:
            entry = vectors.get(vid)
            if not entry or "values" not in entry:
                raise KeyError(f"Vector id '{vid}' missing in fetch response")
            arr = np.asarray(entry["values"], dtype=np.float32)
            if dim is None:
                dim = arr.shape[0]
            ordered.append(arr)
        return np.vstack(ordered).astype(np.float32)
