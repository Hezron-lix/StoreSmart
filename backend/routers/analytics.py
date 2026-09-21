"""Analytics router (forecast, compression, health, priority).

Endpoints moved here in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["analytics"])
