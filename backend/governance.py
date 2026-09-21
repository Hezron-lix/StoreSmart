"""Governance shim.

Re-exports policy evaluation from the legacy ingestion.governance module.
Audit writing has moved to backend.audit — do NOT import write_audit_record
from here.

Phase 5 ports the implementation.
"""

from ingestion.governance import (  # TODO(phase5): port impl
    calculate_file_age_days,
    evaluate_action,
    is_legal_or_protected,
    is_valid_sha256,
    load_retention_policies,
    parse_datetime,
)

__all__ = [
    "evaluate_action",
    "load_retention_policies",
    "parse_datetime",
    "calculate_file_age_days",
    "is_valid_sha256",
    "is_legal_or_protected",
]
