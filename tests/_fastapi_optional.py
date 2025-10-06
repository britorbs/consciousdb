"""Optional FastAPI test utilities.

Provides a unified import surface for tests that rely on `fastapi.testclient`.
If the `fastapi` (server extra) dependency is absent, exposes `FASTAPI_AVAILABLE = False`
so tests can apply a skip marker consistently.
"""
from __future__ import annotations

FASTAPI_AVAILABLE = True
try:  # pragma: no cover - exercised implicitly when fastapi installed
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    FASTAPI_AVAILABLE = False
    class _NoFastAPI:  # minimal placeholder to avoid NameError if mistakenly used
        def __init__(self, *_, **__):  # noqa: D401
            raise RuntimeError("FastAPI not installed; install consciousdb[server] to run this test")
    TestClient = _NoFastAPI  # type: ignore

__all__ = ["TestClient", "FASTAPI_AVAILABLE"]
