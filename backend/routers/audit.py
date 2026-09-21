"""Audit router: expose the raw audit CSV over HTTP.

Moved from ingestion/api.py. The endpoint returns the CSV file as
text/plain so the frontend can render it in a table or offer it as a
download.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.audit import get_audit_csv_content

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_class=PlainTextResponse)
def get_audit_log_endpoint():
    """Return the full audit log CSV as plain text."""
    return get_audit_csv_content()
