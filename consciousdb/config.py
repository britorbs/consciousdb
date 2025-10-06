"""SDK Configuration object.

Environment variable defaults consolidated into a structured dataclass so
applications can explicitly construct / modify configuration instead of
reaching into ``os.environ`` throughout the codebase.

Only the subset required by the synchronous client and solver surface is
included here; server/auth/adaptive flags can migrate later to keep initial
footprint lean.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}


def _b(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    return val.lower() in _TRUE


@dataclass(slots=True)
class Config:
    connector: str = "memory"
    embedder: str = "sentence_transformer"
    use_mock: bool = True

    # Graph / retrieval
    knn_k: int = 5
    knn_mutual: bool = True

    # Solver / ranking
    alpha_deltaH: float = 0.1  # noqa: N815 (domain-specific name retained)
    similarity_gap_margin: float = 0.15
    coh_drop_min: float = 0.01
    expand_when_gap_below: float = 0.08
    iters_cap: int = 20
    residual_tol: float = 0.001
    redundancy_threshold: float = 0.35
    mmr_lambda: float = 0.3
    enable_mmr: bool = False

    # Embedding / keys
    st_model: str = "all-MiniLM-L6-v2"
    openai_api_key: str | None = None

    # Connector creds
    pg_dsn: str | None = None
    pinecone_api_key: str | None = None
    pinecone_index: str | None = None
    chroma_host: str | None = None
    chroma_collection: str | None = None
    gcp_project: str | None = None
    vertex_index: str | None = None

    @classmethod
    def from_env(cls) -> Config:  # pragma: no cover simple mapping
        g = os.getenv
        return cls(
            connector=g("CONNECTOR", "memory"),
            embedder=g("EMBEDDER", "sentence_transformer"),
            use_mock=_b(g("USE_MOCK"), True),
            knn_k=int(g("KNN_K", "5")),
            knn_mutual=_b(g("KNN_MUTUAL"), True),
            alpha_deltaH=float(g("ALPHA_DELTAH", "0.1")),
            similarity_gap_margin=float(g("SIMILARITY_GAP_MARGIN", "0.15")),
            coh_drop_min=float(g("COH_DROP_MIN", "0.01")),
            expand_when_gap_below=float(g("EXPAND_WHEN_GAP_BELOW", "0.08")),
            iters_cap=int(g("ITERS_CAP", "20")),
            residual_tol=float(g("RESIDUAL_TOL", "0.001")),
            redundancy_threshold=float(g("REDUNDANCY_THRESHOLD", "0.35")),
            mmr_lambda=float(g("MMR_LAMBDA", "0.3")),
            enable_mmr=_b(g("ENABLE_MMR"), False),
            st_model=g("ST_MODEL", "all-MiniLM-L6-v2"),
            openai_api_key=g("OPENAI_API_KEY"),
            pg_dsn=g("PG_DSN"),
            pinecone_api_key=g("PINECONE_API_KEY"),
            pinecone_index=g("PINECONE_INDEX"),
            chroma_host=g("CHROMA_HOST"),
            chroma_collection=g("CHROMA_COLLECTION"),
            gcp_project=g("GCP_PROJECT"),
            vertex_index=g("VERTEX_INDEX"),
        )

    def to_overrides(self) -> dict:
        """Expose solver-related parameters as overrides dict."""
        return {
            "alpha_deltaH": self.alpha_deltaH,
            "similarity_gap_margin": self.similarity_gap_margin,
            "coh_drop_min": self.coh_drop_min,
            "expand_when_gap_below": self.expand_when_gap_below,
            "iters_cap": self.iters_cap,
            "residual_tol": self.residual_tol,
            "redundancy_threshold": self.redundancy_threshold,
            "mmr_lambda": self.mmr_lambda,
            "enable_mmr": self.enable_mmr,
            "knn_k": self.knn_k,
            "knn_mutual": self.knn_mutual,
        }
