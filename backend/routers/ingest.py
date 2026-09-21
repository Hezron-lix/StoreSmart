"""Ingestion router (multi-format file upload).

Endpoints moved here in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ingest", tags=["ingest"])
