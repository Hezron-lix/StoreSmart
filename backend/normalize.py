"""Normalization shim.

Re-exports normalization helpers from ingestion.normalize. Phase 5 ports
the implementation.
"""

from ingestion.normalize import (  # TODO(phase5): port impl
    build_fingerprint,
    deduplicate,
    normalize_record,
    normalize_records,
    to_canonical,
    to_handoff,
    validate_record,
    validate_records,
)

__all__ = [
    "build_fingerprint",
    "normalize_record",
    "normalize_records",
    "validate_record",
    "validate_records",
    "deduplicate",
    "to_canonical",
    "to_handoff",
]
