from __future__ import annotations

import os

from pydantic import BaseModel


class Settings(BaseModel):
    use_mock: bool = os.getenv("USE_MOCK", "true").lower() in ("1", "true", "yes")
    connector: str = os.getenv("CONNECTOR", "memory")  # memory|pgvector|pinecone|chroma|vertex
    embedder: str = os.getenv("EMBEDDER", "sentence_transformer")  # sentence_transformer|openai|vertex

    # DB DSNs/keys
    pg_dsn: str | None = os.getenv("PG_DSN")
    pinecone_api_key: str | None = os.getenv("PINECONE_API_KEY")
    pinecone_index: str | None = os.getenv("PINECONE_INDEX")
    chroma_host: str | None = os.getenv("CHROMA_HOST")
    chroma_collection: str | None = os.getenv("CHROMA_COLLECTION")
    gcp_project: str | None = os.getenv("GCP_PROJECT")
    vertex_index: str | None = os.getenv("VERTEX_INDEX")

    # Embedders
    st_model: str = os.getenv("ST_MODEL", "all-MiniLM-L6-v2")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    # Ranking/gates
    alpha_deltaH: float = float(os.getenv("ALPHA_DELTAH", "0.1"))
    similarity_gap_margin: float = float(os.getenv("SIMILARITY_GAP_MARGIN", "0.15"))
    coh_drop_min: float = float(os.getenv("COH_DROP_MIN", "0.01"))
    expand_when_gap_below: float = float(os.getenv("EXPAND_WHEN_GAP_BELOW", "0.08"))
    iters_cap: int = int(os.getenv("ITERS_CAP", "20"))
    residual_tol: float = float(os.getenv("RESIDUAL_TOL", "0.001"))

    # Graph / kNN params
    # Graph / kNN params (default k reduced from 10 -> 5 per Phase B findings)
    knn_k: int = int(os.getenv("KNN_K", "5"))
    knn_mutual: bool = os.getenv("KNN_MUTUAL", "true").lower() in ("1", "true", "yes")

    # Ranking / redundancy thresholds
    redundancy_threshold: float = float(os.getenv("REDUNDANCY_THRESHOLD", "0.35"))  # trigger MMR consideration
    mmr_lambda: float = float(os.getenv("MMR_LAMBDA", "0.3"))  # weighting inside MMR formula
    enable_mmr: bool = os.getenv("ENABLE_MMR", "false").lower() in ("1", "true", "yes")  # global force enable

    # Validation / health
    _env_expected = os.getenv("EXPECTED_DIM")
    expected_dim: int | None = int(_env_expected) if _env_expected is not None else None
    fail_on_dim_mismatch: bool = os.getenv("FAIL_ON_DIM_MISMATCH", "true").lower() in ("1", "true", "yes")

    # Auth
    api_keys: str | None = os.getenv("API_KEYS")  # comma-separated list; if None or empty => auth disabled
    api_key_header: str = os.getenv("API_KEY_HEADER", "x-api-key")

    # Feature flags (pivot)
    enable_audit_log: bool = os.getenv("ENABLE_AUDIT_LOG", "true").lower() in ("1", "true", "yes")
    enable_adaptive: bool = os.getenv("ENABLE_ADAPTIVE", "false").lower() in ("1", "true", "yes")
    enable_bandit: bool = os.getenv("ENABLE_BANDIT", "false").lower() in ("1", "true", "yes")
    enable_adaptive_apply: bool = os.getenv("ENABLE_ADAPTIVE_APPLY", "false").lower() in ("1", "true", "yes")
    # Adaptive persistence path (for adaptive/ bandit state); JSON snapshot
    adaptive_state_path: str = os.getenv("ADAPTIVE_STATE_PATH", "adaptive_state.json")
    audit_hmac_key: str | None = os.getenv("AUDIT_HMAC_KEY")
    # Phase 3 cleanup: normalization is permanent; legacy flags removed.
    use_normalized_coh: bool = True  # retained for backward compatibility in code paths
