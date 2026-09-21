"""Audit router (read audit CSV).

Endpoints moved here in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/audit", tags=["audit"])
