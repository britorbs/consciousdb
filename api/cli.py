from __future__ import annotations

import argparse
import os
import sys

import uvicorn


def main():  # pragma: no cover (thin wrapper)
    parser = argparse.ArgumentParser(
        description="Launch ConsciousDB HTTP server (deprecated wrapper)"
    )
    # Detect invocation name for deprecation notice (alias consciousdb-sidecar slated for removal)
    invoked_as = sys.argv[0] or ""
    if "sidecar" in invoked_as.lower():  # pragma: no cover - simple runtime path
        msg = (
            "[DEPRECATION] The 'consciousdb-sidecar' entrypoint is deprecated and will be removed "
            "in version 3.2.0; use 'consciousdb-server' or the SDK (ConsciousClient) instead."
        )
        print(msg, file=sys.stderr)
    parser.add_argument(
        "--host", default=os.environ.get("HOST", "0.0.0.0"), help="Bind host (default 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("PORT", 8080)), help="Port (default 8080)"
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    parser.add_argument(
        "--log-level", default=os.environ.get("LOG_LEVEL", "info"), help="Uvicorn log level"
    )
    args = parser.parse_args()
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
