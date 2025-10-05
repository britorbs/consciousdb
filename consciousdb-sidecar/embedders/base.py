from __future__ import annotations
import numpy as np

class BaseEmbedder:
    def embed_query(self, text: str) -> np.ndarray:
        raise NotImplementedError
