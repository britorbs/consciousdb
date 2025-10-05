# Build plan (updated from findings)

## Week 1–2 (Core service)
- New ranker (coherence-only + smoothed alignment)
- Gates & conditional 1-hop expansion
- Memory connector for local dev
- API contracts + diagnostics

## Week 3–4 (BYOVDB connectors)
- pgvector + Chroma adapters
- Pinecone + Vertex AI stubs (enable when creds present)
- Embedder registry (ST/OpenAI/Vertex)

## Week 5–6 (Reliability & polish)
- Vector-only fallback path + force_fallback for tests
- Bench harness on customer data
- Cloud Run deployment + secrets wiring + ROI dashboard
