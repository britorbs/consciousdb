# BYOVDB Connectors

A connector implements:

```python
class Connector(Protocol):
    def top_m(self, query_vec: np.ndarray, m: int) -> List[Tuple[str, float, Optional[np.ndarray]]]:
        """Return [(id, similarity), ...]; optionally include per-item vectors."""

    def fetch_vectors(self, ids: List[str]) -> np.ndarray:
        """Return embeddings for ids (shape [len(ids), d]). Optional if top_m returns vectors."""
```

Included adapters (stubs):
- `connectors/pgvector.py` (SQL using `<->`)
- `connectors/pinecone.py` (client API)
- `connectors/chroma.py`
- `connectors/vertex_ai.py`
- `connectors/memory.py` (brute-force dev)

**Security:** Use `infra/secrets.py` to load credentials from env or your secret manager (GCP Secret Manager, AWS Secrets Manager, Vault). Never log secrets.

**Tuning per backend:** Premium connectors may apply backend-specific ANN params (e.g., IVFFlat `lists`, Pinecone pods, Vertex partitioning). Provide these via env/tenant config.
