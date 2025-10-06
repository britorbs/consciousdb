"""Metrics integration example.

Demonstrates how to emit basic custom metrics around SDK queries. The core
package avoids pulling in Prometheus by default; if you installed the
`server` extra you have `prometheus_client` available.

Run:
    pip install "consciousdb[server]"  # if not already
    python examples/metrics_integration.py

This script will:
  * Execute a few queries
  * Record latency histogram & counter
  * Expose metrics on a simple HTTP endpoint (optional)
"""
from __future__ import annotations

import time
from threading import Thread
from wsgiref.simple_server import make_server

import numpy as np

from consciousdb import Config, ConsciousClient

try:
    from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
except Exception as e:  # pragma: no cover
    raise SystemExit("prometheus_client not installed – install server extra: pip install 'consciousdb[server]'") from e


class TinyConnector:
    def __init__(self):
        rng = np.random.default_rng(11)
        self.ids = [f"doc{i}" for i in range(25)]
        self.vecs = rng.standard_normal((25, 24)).astype("float32")
        self.vecs /= np.linalg.norm(self.vecs, axis=1, keepdims=True) + 1e-12

    def top_m(self, query_vec, m: int):
        sims = self.vecs @ (query_vec / (np.linalg.norm(query_vec) + 1e-12))
        idx = np.argsort(-sims)[:m]
        return [(self.ids[i], float(sims[i]), self.vecs[i]) for i in idx]

    def fetch_vectors(self, ids):
        lookup = {d: i for i, d in enumerate(self.ids)}
        return self.vecs[[lookup[i] for i in ids]]


class HashEmbedder:
    def embed(self, text: str):  # noqa: D401
        import numpy as _np
        seed = abs(hash(text)) % (2**32)
        rng = _np.random.default_rng(seed)
        v = rng.standard_normal(24).astype("float32")
        v /= _np.linalg.norm(v) + 1e-12
        return v


# Prometheus metrics
registry = CollectorRegistry()
QUERY_LATENCY = Histogram(
    "consciousdb_query_latency_seconds",
    "End-to-end ConsciousClient query latency",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2),
    registry=registry,
)
QUERY_COUNT = Counter(
    "consciousdb_queries_total",
    "Total ConsciousClient queries executed",
    registry=registry,
)


def serve_metrics():  # noqa: D401
    def app(environ, start_response):  # WSGI minimal app
        if environ.get("PATH_INFO") == "/metrics":
            payload = generate_latest(registry)
            start_response("200 OK", [("Content-Type", "text/plain; version=0.0.4")])
            return [payload]
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"not found"]

    httpd = make_server("0.0.0.0", 8009, app)
    httpd.serve_forever()


Thread(target=serve_metrics, daemon=True).start()


def timed_query(client: ConsciousClient, q: str):  # noqa: D401
    t0 = time.time()
    res = client.query(q, k=5, m=40)
    dt = time.time() - t0
    QUERY_LATENCY.observe(dt)
    QUERY_COUNT.inc()
    print(f"{q!r} -> first={res.items[0].id if res.items else 'NA'} latency={dt*1000:.2f}ms")


def main():  # noqa: D401
    client = ConsciousClient(connector=TinyConnector(), embedder=HashEmbedder(), config=Config())
    queries = [
        "graph diffusion",
        "embedding alignment",
        "coherence regularization",
        "adaptive expansion",
        "redundancy penalty",
    ]
    for _ in range(3):
        for q in queries:
            timed_query(client, q)
        time.sleep(0.2)
    print("Metrics available at http://localhost:8009/metrics")


if __name__ == "__main__":  # pragma: no cover
    main()
