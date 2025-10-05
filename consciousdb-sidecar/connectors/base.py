from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np

class BaseConnector:
    def top_m(self, query_vec: np.ndarray, m: int) -> List[Tuple[str, float, Optional[np.ndarray]]]:
        raise NotImplementedError

    def fetch_vectors(self, ids: List[str]) -> np.ndarray:
        raise NotImplementedError
