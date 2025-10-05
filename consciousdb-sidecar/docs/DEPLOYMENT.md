# Deployment

## Local
- `uvicorn api.main:app --reload --port 8080`

## Docker

The project now ships with a multi-stage build that:
- Builds wheels in a builder stage (faster cold starts, smaller final image)
- Installs only runtime artifacts in the slim stage (no compilers)
- Runs as a non-root user `app`
- Provides a lightweight healthcheck hitting `/health`

Build (base dependencies only):
```
docker build -t consciousdb-sidecar:dev -f ops/Dockerfile .
```

Include optional extras (example: sentence-transformers + chromadb):
```
docker build --build-arg OPTIONAL_EXTRAS="sentence-transformers==2.7.0 chromadb==0.5.4" \
	-t consciousdb-sidecar:extras -f ops/Dockerfile .
```

Run:
```
docker run -p 8080:8080 --env-file .env consciousdb-sidecar:dev
```

Expected size improvements vs. previous single-stage image will depend on optional extras; base should exclude build-essential & test/docs folders.

## Cloud Run (GCP)
- `gcloud run deploy consciousdb-sidecar --source . --region us-central1 --allow-unauthenticated`
- Set env vars in Cloud Run → Variables & Secrets; use Secret Manager for keys.

## Multi-cloud
- The sidecar is stateless; deploy close to the data plane (VPC peering / private endpoints to the customer’s vector DB).
- For managed graph state (learning), use Redis/Memorystore/ElastiCache; keep memory footprints bounded.
