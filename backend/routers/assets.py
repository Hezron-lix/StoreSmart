"""Assets router (list, detail, filtering).

Endpoints moved here in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/assets", tags=["assets"])
