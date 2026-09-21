"""Auth router (login, signup, current user).

Endpoints moved here in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])
