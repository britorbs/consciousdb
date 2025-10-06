"""Public SDK facade for ConsciousDB.

Initial minimal surface:
- ConsciousClient (synchronous) for query operations.

Future (deferred):
- Config object (centralized param management)
- Async client
- Caching / persistence
"""
from .client import ConsciousClient, QueryResult, RankedItem  # noqa: F401
