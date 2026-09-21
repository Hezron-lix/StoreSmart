"""Database connection shim.

Re-exports the connection factory from the legacy `ingestion.database`
module. This exists so that new backend modules can import
`from backend.db import get_connection` without depending directly on
the old package.

Phase 5 replaces the internals here with the fully-ported
implementation. Router modules should NOT need to change when that
happens.
"""

from ingestion.database import get_connection  # TODO(phase5): port impl

__all__ = ["get_connection"]
