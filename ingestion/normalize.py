"""Normalization, fingerprinting, validation and deduplication.

Parsers hand over loosely-typed "raw records". Everything in this module turns
those into canonical records and reports anything that is wrong.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ingestion.utils import (
    clean_text,
    coerce_tags,
    get_logger,
    is_iso8601,
    is_sha256_hex,
    normalize_timestamp,
    sha256_fingerprint,
    to_gb,
)

logger = get_logger(__name__)

# The official 9-field canonical contract (schemas/canonical.avsc).
CANONICAL_FIELDS = (
    "asset_id",
    "source_type",
    "size_gb",
    "created_ts",
    "modified_ts",
    "owner_dept",
    "tags",
    "checksum",
    "policy_id",
)

# Extra, clearly separated fields for the database teammate. These are NOT part
# of the Avro contract - they live in the handoff output only.
INGESTION_META_FIELDS = (
    "source_path",
    "file_name",
    "file_extension",
    "source_event",
    "is_duplicate",
    "duplicate_of",
)

VALID_SOURCE_TYPES = ("json", "txt", "csv", "yaml")

DEFAULT_OWNER_DEPT = "unknown"

# Attributes that make up the deduplication fingerprint.
#
# asset_id and source_type are deliberately EXCLUDED: the point of StorageWise
# is to spot the same underlying asset appearing in two different systems under
# two different ids. Including asset_id would make every record unique and the
# duplicate count would always be zero.
FINGERPRINT_FIELDS = (
    "size_gb",
    "owner_dept",
    "policy_id",
    "created_ts",
    "modified_ts",
    "tags",
    "file_name",
)


def build_fingerprint(record: Dict[str, Any]) -> str:
    """Deterministic SHA-256 fingerprint of a normalized record's attributes."""
    payload = {field: record.get(field) for field in FINGERPRINT_FIELDS}
    payload["tags"] = sorted(payload.get("tags") or [])
    return sha256_fingerprint(payload)


def normalize_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one raw parser record into a normalized record with a checksum.

    Raises ValueError when a value is present but genuinely unusable (a
    non-numeric size, an unparseable timestamp). Missing optional values fall
    back to the documented defaults instead of raising.
    """
    record: Dict[str, Any] = {
        "asset_id": clean_text(raw.get("asset_id")),
        "source_type": (clean_text(raw.get("source_type")) or "").lower(),
        "size_gb": to_gb(raw.get("size_value"), raw.get("size_unit", "GB")),
        "created_ts": normalize_timestamp(raw.get("created_ts")),
        "modified_ts": normalize_timestamp(raw.get("modified_ts")),
        "owner_dept": clean_text(raw.get("owner_dept"), DEFAULT_OWNER_DEPT),
        "tags": sorted(coerce_tags(raw.get("tags"))),
        "policy_id": clean_text(raw.get("policy_id")),
        # ingestion metadata (not part of the Avro contract)
        "source_path": clean_text(raw.get("source_path")),
        "file_name": clean_text(raw.get("file_name")),
        "file_extension": clean_text(raw.get("file_extension")),
        "source_event": clean_text(raw.get("source_event")),
        "is_duplicate": False,
        "duplicate_of": None,
    }
    record["checksum"] = build_fingerprint(record)
    return record


def normalize_records(
    raws: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Normalize many raw records. Returns (records, errors)."""
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for raw in raws:
        try:
            records.append(normalize_record(raw))
        except ValueError as exc:
            errors.append(
                {
                    "stage": "normalize",
                    "source_type": raw.get("source_type"),
                    "location": raw.get("source_location"),
                    "asset_id": raw.get("asset_id"),
                    "error": str(exc),
                }
            )
            logger.warning(
                "normalization failed (%s): %s", raw.get("source_location"), exc
            )

    return records, errors


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_record(record: Dict[str, Any]) -> List[str]:
    """Return a list of validation errors for one record (empty == valid)."""
    errors: List[str] = []

    asset_id = record.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id.strip():
        errors.append("asset_id is missing or empty")

    if record.get("source_type") not in VALID_SOURCE_TYPES:
        errors.append(
            f"source_type must be one of {list(VALID_SOURCE_TYPES)}, "
            f"got {record.get('source_type')!r}"
        )

    size_gb = record.get("size_gb")
    if isinstance(size_gb, bool) or not isinstance(size_gb, (int, float)):
        errors.append(f"size_gb must be numeric, got {size_gb!r}")
    elif size_gb < 0:
        errors.append(f"size_gb must be >= 0, got {size_gb}")

    owner_dept = record.get("owner_dept")
    if not isinstance(owner_dept, str) or not owner_dept.strip():
        errors.append("owner_dept is missing (should have defaulted to 'unknown')")

    tags = record.get("tags")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        errors.append("tags must be a list of strings")

    if not is_sha256_hex(record.get("checksum")):
        errors.append("checksum must be a 64-character SHA-256 hex digest")

    policy_id = record.get("policy_id")
    if policy_id is not None and not isinstance(policy_id, str):
        errors.append("policy_id must be null or a string")

    for field in ("created_ts", "modified_ts"):
        value = record.get(field)
        if value is not None and not is_iso8601(value):
            errors.append(f"{field} must be null or a valid ISO-8601 string")

    return errors


def validate_records(
    records: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split records into (valid, invalid). Invalid records are never dropped."""
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []

    for record in records:
        errors = validate_record(record)
        if errors:
            invalid.append({"record": record, "errors": errors})
            logger.warning(
                "invalid record %s (%s): %s",
                record.get("asset_id"),
                record.get("source_type"),
                "; ".join(errors),
            )
        else:
            valid.append(record)

    return valid, invalid


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
def deduplicate(
    records: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Mark duplicates by checksum.

    Behaviour is explicit and lossless:
      * the FIRST record with a given checksum wins and is returned as unique
      * later records with the same checksum get is_duplicate=True and
        duplicate_of=<winning asset_id>, and are returned in the second list
      * nothing is thrown away

    Returns (unique_records, duplicate_records).
    """
    seen: Dict[str, str] = {}
    unique: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []

    for record in records:
        checksum = record["checksum"]
        if checksum in seen:
            record["is_duplicate"] = True
            record["duplicate_of"] = seen[checksum]
            duplicates.append(record)
        else:
            seen[checksum] = record["asset_id"]
            record["is_duplicate"] = False
            record["duplicate_of"] = None
            unique.append(record)

    return unique, duplicates


# ---------------------------------------------------------------------------
# Output shaping
# ---------------------------------------------------------------------------
def to_canonical(record: Dict[str, Any]) -> Dict[str, Any]:
    """Strict 9-field canonical record matching schemas/canonical.avsc."""
    return {field: record.get(field) for field in CANONICAL_FIELDS}


def to_handoff(record: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical record plus clearly separated ingestion metadata."""
    handoff = to_canonical(record)
    handoff["ingestion_meta"] = {
        field: record.get(field) for field in INGESTION_META_FIELDS
    }
    return handoff
