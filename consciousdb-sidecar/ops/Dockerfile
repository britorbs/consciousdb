##############################
# Builder image: install deps
##############################
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1

WORKDIR /builder

# Install build tools only in builder
RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential curl \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

# Separate optional extras via build arg (comma-separated pip packages)
ARG OPTIONAL_EXTRAS=""
ENV OPTIONAL_EXTRAS=${OPTIONAL_EXTRAS}

# Pre-build wheels for faster, smaller runtime layer
RUN pip wheel --wheel-dir /wheels -r requirements.txt \
	&& if [ -n "$OPTIONAL_EXTRAS" ]; then \
		 pip wheel --wheel-dir /wheels $OPTIONAL_EXTRAS; \
	   fi

COPY . /builder/src

##############################
# Runtime image: minimal
##############################
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

# Copy wheels then install (no build tools needed now)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
	&& rm -rf /wheels

# Copy application source only (exclude tests & docs for lean image)
COPY --from=builder /builder/src/api ./api
COPY --from=builder /builder/src/engine ./engine
COPY --from=builder /builder/src/graph ./graph
COPY --from=builder /builder/src/infra ./infra
COPY --from=builder /builder/src/embedders ./embedders
COPY --from=builder /builder/src/connectors ./connectors
COPY --from=builder /builder/src/README.md ./README.md
COPY --from=builder /builder/src/pyproject.toml ./pyproject.toml

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app \
	&& chown -R app:app /app
USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import httpx,os;\nurl='http://127.0.0.1:8080/health';\nresp=httpx.get(url,timeout=2);\nexit(0 if resp.status_code==200 else 1)" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
