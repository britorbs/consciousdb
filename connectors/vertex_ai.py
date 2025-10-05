from __future__ import annotations

import numpy as np

from .base import BaseConnector


class VertexConnector(BaseConnector):
    def __init__(self, project: str, index: str):
        self.project = project
        self.index = index

    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray | None]]:
        # TODO: call Vertex AI Vector Search index; request embeddings if possible
        raise NotImplementedError

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:
        raise NotImplementedError
