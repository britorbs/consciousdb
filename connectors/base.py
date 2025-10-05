from __future__ import annotations

import numpy as np


class BaseConnector:
    def top_m(self, query_vec: np.ndarray, m: int) -> list[tuple[str, float, np.ndarray | None]]:
        raise NotImplementedError

    def fetch_vectors(self, ids: list[str]) -> np.ndarray:
        raise NotImplementedError
