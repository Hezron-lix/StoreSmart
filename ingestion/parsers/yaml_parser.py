"""Parser for the multi-document VM configuration YAML source.

Documents are separated by '---' and read with yaml.safe_load_all(), so each
VM becomes its own asset. The file is never treated as a single asset.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import yaml

from ingestion.utils import clean_text, get_logger, normalize_timestamp

logger = get_logger(__name__)

SOURCE_TYPE = "yaml"
SIZE_UNIT = "GB"  # disk.size_gb is already GB


def _latest_snapshot_timestamp(disk: Dict[str, Any]) -> Any:
    """Return the most recent snapshot timestamp, or None when there are none.

    A VM config carries no timestamp of its own. The newest snapshot is the only
    real evidence of when the disk last changed, so it is used as modified_ts;
    created_ts stays null rather than being fabricated.
    """
    snapshots = disk.get("snapshots") if isinstance(disk, dict) else None
    if not isinstance(snapshots, list):
        return None

    stamps = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        try:
            normalized = normalize_timestamp(snapshot.get("created"))
        except ValueError:
            continue
        if normalized:
            stamps.append(normalized)

    return max(stamps) if stamps else None


def parse_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one YAML document into a raw record. Raises ValueError if bad."""
    if not isinstance(document, dict):
        raise ValueError("YAML document is not a mapping")

    vm_id = clean_text(document.get("vm_id"))
    if not vm_id:
        raise ValueError("vm_id is missing or empty")

    disk = document.get("disk")
    if disk is not None and not isinstance(disk, dict):
        raise ValueError("disk must be a mapping when present")
    size_gb = disk.get("size_gb") if isinstance(disk, dict) else None

    # `department` is the owning department; `owner` is kept as a fallback only.
    owner_dept = clean_text(document.get("department")) or clean_text(
        document.get("owner")
    )

    return {
        "asset_id": vm_id,
        "source_type": SOURCE_TYPE,
        "size_value": size_gb,
        "size_unit": SIZE_UNIT,
        "created_ts": None,
        "modified_ts": _latest_snapshot_timestamp(disk or {}),
        "owner_dept": owner_dept,
        "tags": document.get("tags"),
        "policy_id": clean_text(document.get("policy_id")),
        # A VM disk is not a file, so no filename is invented.
        "source_path": None,
        "file_name": None,
        "file_extension": None,
        "source_event": None,
    }


def parse_yaml_file(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse a multi-document VM config YAML file. Returns (raw_records, errors)."""
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with open(path, "r", encoding="utf-8") as handle:
        documents = yaml.safe_load_all(handle)
        index = 0
        while True:
            index += 1
            location = f"{path}#doc{index}"
            try:
                document = next(documents)
            except StopIteration:
                break
            except yaml.YAMLError as exc:
                errors.append(
                    {
                        "stage": "parse",
                        "source_type": SOURCE_TYPE,
                        "location": location,
                        "error": f"invalid YAML: {exc}",
                    }
                )
                logger.error("YAML parse error at %s - %s", location, exc)
                break  # the stream position is no longer trustworthy

            if document is None:
                continue

            try:
                record = parse_document(document)
            except ValueError as exc:
                errors.append(
                    {
                        "stage": "parse",
                        "source_type": SOURCE_TYPE,
                        "location": location,
                        "error": str(exc),
                    }
                )
                logger.warning("YAML document error at %s - %s", location, exc)
                continue

            record["source_location"] = location
            records.append(record)

    logger.info("parsed %s YAML records from %s", len(records), path)
    return records, errors
