"""Actions router (delete, compress, governance gate).

Endpoints moved here in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/actions", tags=["actions"])
