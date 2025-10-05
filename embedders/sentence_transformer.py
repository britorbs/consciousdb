from __future__ import annotations
import time
import numpy as np
from .base import BaseEmbedder
from infra.logging import setup_logging

_LOG = setup_logging()


class SentenceTransformerEmbedder(BaseEmbedder):
    """Lazy sentence-transformers loader with deterministic fallback.

    If `sentence_transformers` is unavailable or load fails, a stable hash-based
    placeholder embedding of dimension 32 is used.
    """

    _model = None
    _model_dim: int | None = None
    _placeholder_state = 0xC0FFEE

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", timeout_s: float = 10.0):
        self.model_name = model_name
        self.timeout_s = timeout_s
        # Do not load immediately; defer until first call.

    def _ensure_loaded(self):
        if self._model is not None:
            return
        start = time.time()
        try:
            import importlib
            st_mod = importlib.import_module("sentence_transformers")
            model_cls = getattr(st_mod, "SentenceTransformer")
            self._model = model_cls(self.model_name, device="cpu")
            # Probe dim
            emb = self._model.encode(["dim-probe"], normalize_embeddings=True)
            self._model_dim = int(emb.shape[1])
            _LOG.info(
                "embedder_loaded",
                extra={
                    "embedder": "sentence_transformer",
                    "model": self.model_name,
                    "dim": self._model_dim,
                    "load_ms": int((time.time() - start) * 1000),
                },
            )
        except ModuleNotFoundError:
                _LOG.warning(
                    "embedder_module_missing",
                    extra={"missing_module": "sentence_transformers", "fallback_dim": 32},
                )
        except Exception as e:  # pragma: no cover
            _LOG.error(
                "embedder_load_failed",
                extra={"error": str(e), "model": self.model_name},
            )

    @property
    def dim(self) -> int:
        return self._model_dim if self._model_dim is not None else 32

    def _fallback_embed(self, text: str) -> np.ndarray:
        h = abs(hash(text)) % (10**9)
        rng = np.random.default_rng(h ^ self._placeholder_state)
        v = rng.normal(size=(32,)).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-12)

    def embed_query(self, text: str) -> np.ndarray:
        self._ensure_loaded()
        if self._model is None:
            return self._fallback_embed(text)
        emb = self._model.encode([text], normalize_embeddings=True)
        v = emb[0].astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-12)
