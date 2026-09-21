"""Database shim.

Re-exports connection and query helpers from the legacy
`ingestion.database` module. Phase 5 replaces the internals here with
a fully-ported implementation; routers do not need to change then.
"""

from ingestion.database import (  # TODO(phase5): port impl
    fetch_asset,
    fetch_assets,
    fetch_compression_insights,
    fetch_storage_history,
    get_connection,
    upsert_prediction,
)

__all__ = [
    "get_connection",
    "fetch_assets",
    "fetch_asset",
    "fetch_storage_history",
    "upsert_prediction",
    "fetch_compression_insights",
]
