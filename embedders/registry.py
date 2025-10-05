from __future__ import annotations

from .sentence_transformer import SentenceTransformerEmbedder


def get_embedder(name: str):
    name = name.lower()
    if name == "sentence_transformer":
        return SentenceTransformerEmbedder()
    if name == "openai":
        # require OPENAI_API_KEY
        raise NotImplementedError("OpenAI embedder not wired in scaffold")
    if name == "vertex":
        # require GCP config
        raise NotImplementedError("Vertex embedder not wired in scaffold")
    raise RuntimeError(f"Unknown embedder: {name}")
