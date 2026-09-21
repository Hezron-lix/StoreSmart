"""Shared helpers for the StorageWise AI ingestion layer.

Pure functions only: no I/O side effects beyond logging, no database access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import posixpath
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Tuple

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s"

# ---------------------------------------------------------------------------
# Size conversion
# ---------------------------------------------------------------------------
# Multipliers that convert a value in <unit> into GB.
#
# NOTE: the KB / MB / TB rules below are taken verbatim from the StorageWise
# ingestion specification. Mathematically MB -> GB is normally /1024; the spec
# states /1_048_576, so that is what is implemented. Change it HERE only.
# "B" (raw bytes) is not in the spec table but is required, because the JSON
# telemetry and the CSV cloud metadata both report `size_bytes`.
SIZE_CONVERSIONS_TO_GB = {
    "B": 1.0 / (1024 ** 3),   # bytes  -> GB
    "KB": 1.0 / 1_048_576,    # spec:  KB / 1,048,576
    "MB": 1.0 / 1_048_576,    # spec:  MB / 1,048,576
    "GB": 1.0,                # spec:  already GB, keep as-is
    "TB": 1024.0,             # spec:  TB * 1024
}

SIZE_DECIMALS = 6

# Timestamp input formats we accept, tried in order.
_TIMESTAMP_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y%m%d",
)

_SHA256_LENGTH = 64
_HEX_DIGITS = set("0123456789abcdef")


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return a logger with a single stream handler (safe to call repeatedly)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------
def to_gb(value: Any, unit: str = "GB") -> float:
    """Convert a size expressed in `unit` into GB.

    Missing values (None / "") become 0.0, per the ingestion spec.
    A genuinely non-numeric value raises ValueError so the caller can report it
    instead of silently producing garbage.
    """
    unit_key = (unit or "GB").strip().upper()
    if unit_key not in SIZE_CONVERSIONS_TO_GB:
        raise ValueError(f"unsupported size unit: {unit!r}")

    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0

    if isinstance(value, bool):  # bool is a subclass of int; reject it explicitly
        raise ValueError("size value must be numeric, got bool")

    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"size value is not numeric: {value!r}") from exc

    return round(numeric * SIZE_CONVERSIONS_TO_GB[unit_key], SIZE_DECIMALS)


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------
def _to_iso(moment: datetime) -> str:
    """Render a datetime as an ISO-8601 string (UTC gets the trailing Z)."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def normalize_timestamp(value: Any) -> Optional[str]:
    """Normalize a timestamp into an ISO-8601 string, or None when absent.

    Never fabricates a timestamp. Raises ValueError on an unparseable value.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_iso(value)
    if not isinstance(value, str):
        raise ValueError(f"unsupported timestamp type: {type(value).__name__}")

    text = value.strip()
    if not text:
        return None

    iso_candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return _to_iso(datetime.fromisoformat(iso_candidate))
    except ValueError:
        pass

    for fmt in _TIMESTAMP_FORMATS:
        try:
            return _to_iso(datetime.strptime(text, fmt))
        except ValueError:
            continue

    raise ValueError(f"unparseable timestamp: {value!r}")


def is_iso8601(value: Any) -> bool:
    """True when `value` can be read back as an ISO-8601 timestamp."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        normalize_timestamp(value)
        return True
    except ValueError:
        return False


def combine_date_time(date_text: str, time_text: str) -> Optional[str]:
    """Combine mainframe YYYYMMDD + HHMMSS parts into one ISO-8601 string."""
    date_text = (date_text or "").strip()
    time_text = (time_text or "").strip()
    if not date_text:
        return None
    return normalize_timestamp(date_text + (time_text or "000000"))


# ---------------------------------------------------------------------------
# Text / paths / tags
# ---------------------------------------------------------------------------
def clean_text(value: Any, default: Optional[str] = None) -> Optional[str]:
    """Trim a value into a non-empty string, else return `default`."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def coerce_tags(value: Any) -> list:
    """Coerce a tags value into a list of non-empty strings (defaults to [])."""
    if value is None:
        return []
    if isinstance(value, str):
        parts: Iterable[str] = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        parts = [str(item) for item in value]
    else:
        raise ValueError(f"tags must be a list or string, got {type(value).__name__}")
    return [part.strip() for part in parts if str(part).strip()]


def split_file_name(path: Any) -> Tuple[Optional[str], Optional[str]]:
    """Derive (file_name, file_extension) from a path-like string.

    Returns (None, None) when the source does not describe a real file, so we
    never invent a filename (VM disks, for example).
    """
    text = clean_text(path)
    if text is None:
        return None, None

    file_name = posixpath.basename(text.replace("\\", "/").rstrip("/"))
    if not file_name:
        return None, None

    stem, _, extension = file_name.rpartition(".")
    if not stem or not extension:
        return file_name, None
    return file_name, "." + extension.lower()


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------
def sha256_fingerprint(payload: dict) -> str:
    """Deterministic SHA-256 hex digest of a dict.

    IMPORTANT: this hashes *normalized metadata attributes*, not the bytes of
    the original file - we only ever receive metadata. Described accurately as
    a "deterministic SHA-256 fingerprint of the normalized asset attributes".

    The dict is serialized as sorted, compact canonical JSON so the digest is
    stable across runs, machines and Python versions. str(dict) is never used.
    """
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def is_sha256_hex(value: Any) -> bool:
    """True when `value` looks like a lowercase SHA-256 hex digest."""
    return (
        isinstance(value, str)
        and len(value) == _SHA256_LENGTH
        and set(value) <= _HEX_DIGITS
    )
