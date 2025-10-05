from __future__ import annotations
from typing import Any
from infra.settings import Settings
from .memory import MemoryConnector
from .pgvector import PgVectorConnector
from .pinecone import PineconeConnector
from .chroma import ChromaConnector
from .vertex_ai import VertexConnector

def get_connector(name: str, settings: Settings):
    name = name.lower()
    if name == "memory":
        return MemoryConnector()
    if name == "pgvector":
        if not settings.pg_dsn:
            raise RuntimeError("PG_DSN required for pgvector connector")
        return PgVectorConnector(dsn=settings.pg_dsn)
    if name == "pinecone":
        if not settings.pinecone_api_key or not settings.pinecone_index:
            raise RuntimeError("PINECONE_API_KEY and PINECONE_INDEX required")
        return PineconeConnector(api_key=settings.pinecone_api_key, index_name=settings.pinecone_index)
    if name == "chroma":
        if not settings.chroma_host or not settings.chroma_collection:
            raise RuntimeError("CHROMA_HOST and CHROMA_COLLECTION required")
        return ChromaConnector(host=settings.chroma_host, collection=settings.chroma_collection)
    if name == "vertex":
        if not settings.gcp_project or not settings.vertex_index:
            raise RuntimeError("GCP_PROJECT and VERTEX_INDEX required")
        return VertexConnector(project=settings.gcp_project, index=settings.vertex_index)
    raise RuntimeError(f"Unknown connector: {name}")
