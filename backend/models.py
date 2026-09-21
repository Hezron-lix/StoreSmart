"""Pydantic request models shared across routers.

Populated incrementally as endpoints are moved from ingestion/api.py.
Each class is a faithful copy of the corresponding class in the old
monolith; no behavior changes.
"""

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str
    password: str
    role: str = "Viewer"


class LoginRequest(BaseModel):
    username: str
    password: str


class ForecastRequest(BaseModel):
    history: list[dict] = Field(default_factory=list)


class HealthScoreRequest(BaseModel):
    usedStorage: float
    totalStorage: float
    averageCompressionPercent: float
    daysToFull: float


class PriorityScoreRequest(BaseModel):
    risk: float
    savings: float


class CompressionRequest(BaseModel):
    entropy_score: float
    file_extension: str
    size_gb: float


class CompressionBatchRequest(BaseModel):
    limit: int = 100
    source_type: str | None = None


class ActionRequest(BaseModel):
    action: str
