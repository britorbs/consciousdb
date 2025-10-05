from __future__ import annotations
import os

def get_secret(name: str, default: str | None = None) -> str | None:
    """Basic secret loader (env). Swap with GCP/AWS/Vault in managed deployments."""
    return os.getenv(name, default)
