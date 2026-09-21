"""Parser for the cloud metadata CSV source.

Header: bucket,key,size_bytes,created,owner,policy_id
"""

from __future__ import annotations

import csv
import hashlib
from typing import Any, Dict, List, Tuple

from backend.utils import clean_text, get_logger, split_file_name

logger = get_logger(__name__)

SOURCE_TYPE = "csv"
SIZE_UNIT = "B"  # size_bytes
REQUIRED_COLUMNS = ("bucket", "key", "size_bytes", "created", "owner", "policy_id")

# The downstream assets table declares asset_id VARCHAR(100). Very long object
# keys are folded into a deterministic (never random) short id instead.
MAX_ASSET_ID_LENGTH = 100


def build_asset_id(bucket: str, key: str) -> str:
    """Derive a deterministic asset id from bucket + key.

    The same bucket/key always yields the same id; no random UUIDs are used.
    """
    natural_id = f"{bucket}/{key}"
    if len(natural_id) <= MAX_ASSET_ID_LENGTH:
        return natural_id
    digest = hashlib.sha256(natural_id.encode("utf-8")).hexdigest()[:32]
    return f"csv-{digest}"


def parse_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one CSV row into a raw record. Raises ValueError if unusable."""
    bucket = clean_text(row.get("bucket"))
    key = clean_text(row.get("key"))
    if not bucket or not key:
        raise ValueError("bucket and key are required to derive an asset_id")

    file_name, file_extension = split_file_name(key)

    return {
        "asset_id": build_asset_id(bucket, key),
        "source_type": SOURCE_TYPE,
        "size_value": row.get("size_bytes"),
        "size_unit": SIZE_UNIT,
        # The CSV exposes only a creation timestamp; modified stays null.
        "created_ts": clean_text(row.get("created")),
        "modified_ts": None,
        "owner_dept": row.get("owner"),
        "tags": [],
        "policy_id": clean_text(row.get("policy_id")),
        "source_path": f"{bucket}/{key}",
        "file_name": file_name,
        "file_extension": file_extension,
        "source_event": None,
    }


def parse_csv_file(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse a cloud metadata CSV file. Returns (raw_records, errors)."""
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            errors.append(
                {
                    "stage": "parse",
                    "source_type": SOURCE_TYPE,
                    "location": path,
                    "error": "CSV file is empty (no header row)",
                }
            )
            return records, errors

        header = [name.strip() for name in reader.fieldnames]
        missing = [column for column in REQUIRED_COLUMNS if column not in header]
        if missing:
            errors.append(
                {
                    "stage": "parse",
                    "source_type": SOURCE_TYPE,
                    "location": path,
                    "error": f"CSV header is missing columns: {missing}",
                }
            )
            logger.error("CSV header missing columns %s in %s", missing, path)
            return records, errors

        for line_number, row in enumerate(reader, start=2):
            location = f"{path}:{line_number}"
            try:
                record = parse_row(row)
            except ValueError as exc:
                errors.append(
                    {
                        "stage": "parse",
                        "source_type": SOURCE_TYPE,
                        "location": location,
                        "error": str(exc),
                    }
                )
                logger.warning("CSV row error at %s - %s", location, exc)
                continue

            record["source_location"] = location
            records.append(record)

    logger.info("parsed %s CSV records from %s", len(records), path)
    return records, errors
