from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
from .base import BaseConnector

class PineconeConnector(BaseConnector):
    def __init__(self, api_key: str, index_name: str):
        # import pinecone  # optional
        self.api_key = api_key; self.index_name = index_name

    def top_m(self, query_vec: np.ndarray, m: int) -> List[Tuple[str, float, Optional[np.ndarray]]]:
        # TODO: call pinecone index query; request include_values=true to avoid fetch
        raise NotImplementedError

    def fetch_vectors(self, ids: List[str]) -> np.ndarray:
        # TODO: batch fetch values
        raise NotImplementedError
