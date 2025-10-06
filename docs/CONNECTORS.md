# BYOVDB Connectors

A connector implements:

```python
class Connector(Protocol):
    def top_m(self, query_vec: np.ndarray, m: int) -> List[Tuple[str, float, Optional[np.ndarray]]]:
        """Return [(id, similarity), ...]; optionally include per-item vectors."""

    def fetch_vectors(self, ids: List[str]) -> np.ndarray:
        """Return embeddings for ids (shape [len(ids), d]). Optional if top_m returns vectors."""
```

Included adapters:
- `connectors/pgvector.py` (SQL using `<->`; returns ids+similarities)
- `connectors/pinecone.py` (client API, returns vectors inline when `include_values` allowed)
- `connectors/chroma.py` (REST client, returns embeddings + distances -> similarity = 1 - distance)
- `connectors/vertex_ai.py` (stub)
- `connectors/memory.py` (brute-force dev)

Capability notes:
- Pinecone: retries with exponential backoff; `fetch_vectors` only used when inline values absent.
- Chroma: retries on query/get; similarity derived from distance (assumes cosine distance scale).
- pgvector: optional future optimization is to materialize vectors in query or implement `fetch_vectors`.

**Security:** Use `infra/secrets.py` to load credentials from env or your secret manager (GCP Secret Manager, AWS Secrets Manager, Vault). Never log secrets.

**Tuning per backend:** Premium connectors may apply backend-specific ANN params (e.g., IVFFlat `lists`, Pinecone pods, Vertex partitioning). Provide these via env/tenant config.
