"""Parser for StorageWise telemetry JSON.

Supports:
- JSONL / NDJSON
- Standard JSON array
- Single JSON object

Supports both nested telemetry format and flat records.

Nested example:
{
    "event": "file_created",
    "payload": {
        "file_id": "...",
        "path": "...",
        "size_bytes": 123
    }
}

Flat example:
{
    "asset_id": "...",
    "source_path": "...",
    "size_gb": 1.2
}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from ingestion.utils import get_logger, split_file_name


logger = get_logger(__name__)

SOURCE_TYPE = "json"
CREATED_EVENTS = {"file_created"}


def parse_payload(
    payload: Dict[str, Any],
    event: Any = None,
) -> Dict[str, Any]:
    """Convert one JSON payload into a raw StorageWise record."""

    if not isinstance(payload, dict):
        raise ValueError("payload is missing or not an object")

    # --------------------------------------------------
    # PATH / FILE NAME
    # --------------------------------------------------
    source_path = (
        payload.get("path")
        or payload.get("source_path")
        or payload.get("file_path")
        or payload.get("key")
        or payload.get("object_key")
    )

    derived_file_name, derived_extension = split_file_name(source_path)

    file_name = (
        payload.get("file_name")
        or payload.get("filename")
        or payload.get("name")
        or derived_file_name
    )

    file_extension = (
        payload.get("file_extension")
        or payload.get("extension")
        or derived_extension
    )

    # --------------------------------------------------
    # ASSET ID
    # --------------------------------------------------
    asset_id = (
        payload.get("file_id")
        or payload.get("fileId")
        or payload.get("fileID")
        or payload.get("asset_id")
        or payload.get("assetId")
        or payload.get("id")
        or payload.get("object_id")
        or payload.get("objectId")
        or payload.get("vm_id")
        or payload.get("vmId")
        or payload.get("key")
        or source_path
        or file_name
    )

    if asset_id is None or not str(asset_id).strip():
        raise ValueError(
            f"asset identifier missing. Available fields: {list(payload.keys())}"
        )

    asset_id = str(asset_id).strip()

    # --------------------------------------------------
    # SIZE
    # --------------------------------------------------
    size_bytes = (
        payload.get("size_bytes")
        or payload.get("sizeBytes")
        or payload.get("bytes")
    )

    size_gb = (
        payload.get("size_gb")
        or payload.get("sizeGB")
    )

    if size_bytes is not None:
        size_value = size_bytes
        size_unit = "B"

    elif size_gb is not None:
        size_value = size_gb
        size_unit = "GB"

    else:
        size_value = 0
        size_unit = "B"

    # --------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------
    created_ts = (
        payload.get("created_ts")
        or payload.get("created")
        or payload.get("created_at")
    )

    modified_ts = (
        payload.get("modified_ts")
        or payload.get("modified")
        or payload.get("updated_at")
    )

    timestamp = payload.get("timestamp")

    is_creation = (
        isinstance(event, str)
        and event in CREATED_EVENTS
    )

    if created_ts is None and modified_ts is None and timestamp is not None:
        if is_creation:
            created_ts = timestamp
        else:
            modified_ts = timestamp

    # --------------------------------------------------
    # OWNER / DEPARTMENT
    # --------------------------------------------------
    owner_dept = (
        payload.get("owner_dept")
        or payload.get("department")
        or payload.get("owner")
        or "unknown"
    )

    # --------------------------------------------------
    # TAGS
    # --------------------------------------------------
    tags = payload.get("tags")

    if tags is None:
        tags = []

    elif isinstance(tags, str):
        tags = [tags]

    # --------------------------------------------------
    # POLICY
    # --------------------------------------------------
    policy_id = (
        payload.get("policy_id")
        or payload.get("policyId")
    )

    return {
        "asset_id": asset_id,
        "source_type": SOURCE_TYPE,
        "size_value": size_value,
        "size_unit": size_unit,
        "created_ts": created_ts,
        "modified_ts": modified_ts,
        "owner_dept": owner_dept,
        "tags": tags,
        "policy_id": policy_id,
        "source_path": source_path,
        "file_name": file_name,
        "file_extension": file_extension,
        "source_event": event,
    }


def _process_event_object(
    event_object: Any,
    location: str,
    records: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
) -> None:
    """Process one JSON object."""

    if not isinstance(event_object, dict):
        errors.append(
            {
                "stage": "parse",
                "source_type": SOURCE_TYPE,
                "location": location,
                "error": "top-level JSON value is not an object",
            }
        )
        return

    try:
        # Nested telemetry payload
        payload = event_object.get("payload")

        # Flat JSON fallback
        if not isinstance(payload, dict):
            payload = event_object

        event = event_object.get("event")

        record = parse_payload(
            payload=payload,
            event=event,
        )

    except ValueError as exc:
        errors.append(
            {
                "stage": "parse",
                "source_type": SOURCE_TYPE,
                "location": location,
                "error": str(exc),
            }
        )

        logger.warning(
            "JSON record error at %s - %s",
            location,
            exc,
        )

        return

    record["source_location"] = location
    records.append(record)


def parse_json_file(
    path: str,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """
    Parse StorageWise JSON input.

    Supports:
    1. Standard JSON array
    2. Single JSON object
    3. JSONL / NDJSON

    Returns:
        (raw_records, errors)
    """

    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    try:
        with open(
            path,
            "r",
            encoding="utf-8-sig",
        ) as handle:
            content = handle.read().strip()

    except OSError as exc:
        errors.append(
            {
                "stage": "read",
                "source_type": SOURCE_TYPE,
                "location": path,
                "error": str(exc),
            }
        )
        return records, errors

    if not content:
        errors.append(
            {
                "stage": "parse",
                "source_type": SOURCE_TYPE,
                "location": path,
                "error": "JSON file is empty",
            }
        )
        return records, errors

    # --------------------------------------------------
    # STANDARD JSON
    # --------------------------------------------------
    try:
        parsed = json.loads(content)

        if isinstance(parsed, dict):
            objects = [parsed]

        elif isinstance(parsed, list):
            objects = parsed

        else:
            errors.append(
                {
                    "stage": "parse",
                    "source_type": SOURCE_TYPE,
                    "location": path,
                    "error": "top-level JSON must be an object or array",
                }
            )
            return records, errors

        for index, event_object in enumerate(
            objects,
            start=1,
        ):
            location = f"{path}:item:{index}"

            _process_event_object(
                event_object,
                location,
                records,
                errors,
            )

        logger.info(
            "parsed %s JSON records from %s",
            len(records),
            path,
        )

        return records, errors

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------
    # JSONL / NDJSON FALLBACK
    # --------------------------------------------------
    for line_number, raw_line in enumerate(
        content.splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        location = f"{path}:{line_number}"

        try:
            event_object = json.loads(line)

        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "stage": "parse",
                    "source_type": SOURCE_TYPE,
                    "location": location,
                    "error": f"invalid JSON: {exc.msg}",
                }
            )

            logger.warning(
                "JSON parse error at %s - %s",
                location,
                exc.msg,
            )

            continue

        _process_event_object(
            event_object,
            location,
            records,
            errors,
        )

    logger.info(
        "parsed %s JSON records from %s",
        len(records),
        path,
    )

    return records, errors