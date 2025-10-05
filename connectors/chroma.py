from __future__ import annotations

import numpy as np

from .base import BaseConnector


class ChromaConnector(BaseConnector):
    def __init__(self, host: str, collection: str):
        self.host = host
        self.collection = collection

    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray | None]]:
        # TODO: use chromadb client
        raise NotImplementedError

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:
        raise NotImplementedError
