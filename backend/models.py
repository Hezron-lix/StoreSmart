"""Pydantic request models shared across routers.

Populated incrementally as endpoints are moved from ingestion/api.py.
Each class is a faithful copy of the corresponding class in the old
monolith; no behavior changes.
"""

from pydantic import BaseModel


class SignupRequest(BaseModel):
    username: str
    password: str
    role: str = "Viewer"


class LoginRequest(BaseModel):
    username: str
    password: str
