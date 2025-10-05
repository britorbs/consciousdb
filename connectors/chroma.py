from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
from .base import BaseConnector

class ChromaConnector(BaseConnector):
    def __init__(self, host: str, collection: str):
        self.host = host; self.collection = collection

    def top_m(self, query_vec: np.ndarray, m: int) -> List[Tuple[str, float, Optional[np.ndarray]]]:
        # TODO: use chromadb client
        raise NotImplementedError

    def fetch_vectors(self, ids: List[str]) -> np.ndarray:
        raise NotImplementedError
