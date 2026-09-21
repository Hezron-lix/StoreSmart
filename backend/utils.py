"""Utils shim.

Re-exports helpers from ingestion.utils. Phase 5 ports the implementation.
"""

from ingestion.utils import (  # TODO(phase5): port impl
    clean_text,
    combine_date_time,
    get_logger,
    normalize_timestamp,
    split_file_name,
)

__all__ = [
    "clean_text",
    "get_logger",
    "split_file_name",
    "combine_date_time",
    "normalize_timestamp",
]
