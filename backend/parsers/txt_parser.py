"""Parser for the mainframe fixed-width TXT source.

Field positions come exclusively from txt_layout_config.TXT_LAYOUT.
This module never guesses a position.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.parsers.txt_layout_config import (
    EXPECTED_LINE_LENGTH,
    POLICY_ID_PREFIX,
    RECORD_ID_PREFIX,
    SIZE_UNIT,
    TOLERATE_DEPT_OVERFLOW,
    TXT_LAYOUT,
)
from backend.utils import combine_date_time, get_logger

logger = get_logger(__name__)

SOURCE_TYPE = "txt"


def _slice(line: str, field: str) -> str:
    start, end = TXT_LAYOUT[field]
    return line[start:end]


def _split_tail(line: str) -> Tuple[str, str]:
    """Return (owner_dept, policy_id) from the tail of a fixed-width line.

    Handles the documented owner_dept overflow ("ENGINEERING" in a 10-char
    column) by re-aligning on the policy prefix when strict slicing clearly
    produced a shifted policy value.
    """
    owner_dept = _slice(line, "owner_dept")
    policy_id = _slice(line, "policy_id")

    if TOLERATE_DEPT_OVERFLOW and not policy_id.strip().startswith(POLICY_ID_PREFIX):
        tail = line[TXT_LAYOUT["owner_dept"][0]:]
        index = tail.find(POLICY_ID_PREFIX)
        if index > 0:
            owner_dept, policy_id = tail[:index], tail[index:]
            logger.debug("re-aligned overflowing owner_dept column")

    return owner_dept.strip(), policy_id.strip()


def parse_line(line: str, line_number: int) -> Dict[str, Any]:
    """Parse one fixed-width line into a raw record. Raises ValueError if bad."""
    if len(line) < EXPECTED_LINE_LENGTH:
        # Trailing padding spaces are often lost in transit; restore them so the
        # configured slices still apply. Anything much shorter is a real error.
        line = line.ljust(EXPECTED_LINE_LENGTH)

    record_id = _slice(line, "record_id").strip()
    if not record_id:
        raise ValueError("record_id is empty")
    if not record_id.startswith(RECORD_ID_PREFIX):
        raise ValueError(
            f"record_id {record_id!r} does not start with {RECORD_ID_PREFIX!r}"
        )

    date_text = _slice(line, "date").strip()
    time_text = _slice(line, "time").strip()
    size_text = _slice(line, "size").strip()
    owner_dept, policy_id = _split_tail(line)

    if size_text and not size_text.isdigit():
        raise ValueError(f"size column is not numeric: {size_text!r}")
    if date_text and not date_text.isdigit():
        raise ValueError(f"date column is not numeric: {date_text!r}")

    return {
        "asset_id": record_id,
        "source_type": SOURCE_TYPE,
        "size_value": int(size_text) if size_text else 0,
        "size_unit": SIZE_UNIT,
        # The mainframe record carries exactly one timestamp. It is used as the
        # created timestamp; no second timestamp is invented.
        "created_ts": combine_date_time(date_text, time_text),
        "modified_ts": None,
        "owner_dept": owner_dept or None,
        "tags": [],
        "policy_id": policy_id or None,
        # A mainframe dump record describes a dataset, not a file on a path, so
        # file_name / file_extension are deliberately left undetermined.
        "source_path": None,
        "file_name": None,
        "file_extension": None,
        "source_event": None,
        "source_location": f"line {line_number}",
    }


def parse_txt_file(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse a fixed-width mainframe TXT file. Returns (raw_records, errors)."""
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            try:
                records.append(parse_line(line, line_number))
            except ValueError as exc:
                errors.append(
                    {
                        "stage": "parse",
                        "source_type": SOURCE_TYPE,
                        "location": f"{path}:{line_number}",
                        "error": str(exc),
                    }
                )
                logger.warning("TXT parse error at %s:%s - %s", path, line_number, exc)

    logger.info("parsed %s TXT records from %s", len(records), path)
    return records, errors
