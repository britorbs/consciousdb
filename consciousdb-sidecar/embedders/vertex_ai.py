from __future__ import annotations
import numpy as np
from .base import BaseEmbedder

class VertexAIEmbedder(BaseEmbedder):
    def __init__(self, project: str):
        self.project = project

    def embed_query(self, text: str) -> np.ndarray:
        # TODO: call Vertex AI text embeddings
        raise NotImplementedError
