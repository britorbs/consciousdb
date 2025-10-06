"""Optional FastAPI test utilities.

Provides a unified import surface for tests that rely on `fastapi.testclient`.
If the `fastapi` (server extra) dependency is absent, exposes `FASTAPI_AVAILABLE = False`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

FASTAPI_AVAILABLE = False

if TYPE_CHECKING:  # static typing context only
    from fastapi.testclient import TestClient as TestClient  # noqa: F401
else:  # runtime import / fallback
    try:  # pragma: no cover
        from fastapi.testclient import TestClient  # type: ignore  # noqa: F401
        FASTAPI_AVAILABLE = True
    except Exception:  # pragma: no cover
        class TestClient:  # minimal runtime placeholder
            def __init__(self, *_, **__):  # noqa: D401
                raise RuntimeError(
                    "FastAPI not installed; install consciousdb[server] to run this test"
                )

__all__ = ["TestClient", "FASTAPI_AVAILABLE"]
