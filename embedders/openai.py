from __future__ import annotations
import numpy as np
from .base import BaseEmbedder

class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def embed_query(self, text: str) -> np.ndarray:
        # TODO: call OpenAI embeddings
        raise NotImplementedError
