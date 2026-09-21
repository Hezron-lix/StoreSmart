"""Tests for size, timestamp, tag and default-value normalization."""

import pytest

from ingestion.normalize import normalize_record, normalize_records, to_canonical, to_handoff
from ingestion.utils import coerce_tags, normalize_timestamp, split_file_name, to_gb


@pytest.mark.parametrize(
    "value, unit, expected",
    [
        (1_073_741_824, "B", 1.0),
        (1_048_576, "KB", 1.0),
        (1_048_576, "MB", 1.0),  # per the StorageWise spec table
        (250, "GB", 250.0),
        (2, "TB", 2048.0),
        (None, "GB", 0.0),
        ("", "B", 0.0),
    ],
)
def test_size_conversions(value, unit, expected):
    assert to_gb(value, unit) == expected


def test_non_numeric_size_raises():
    with pytest.raises(ValueError):
        to_gb("many gigabytes", "GB")


def test_unknown_unit_raises():
    with pytest.raises(ValueError):
        to_gb(10, "PB")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2024-03-06T08:04:23Z", "2024-03-06T08:04:23Z"),
        ("2024-03-06 08:04:23", "2024-03-06T08:04:23"),
        ("20240306080423", "2024-03-06T08:04:23"),
        (None, None),
        ("", None),
    ],
)
def test_timestamp_normalization(value, expected):
    assert normalize_timestamp(value) == expected


def test_unparseable_timestamp_raises():
    with pytest.raises(ValueError):
        normalize_timestamp("last Tuesday")


def test_missing_values_use_documented_defaults():
    record = normalize_record(
        {"asset_id": "A-1", "source_type": "csv", "size_value": None, "size_unit": "B"}
    )
    assert record["owner_dept"] == "unknown"
    assert record["size_gb"] == 0.0
    assert record["tags"] == []
    assert record["created_ts"] is None
    assert record["modified_ts"] is None
    assert record["policy_id"] is None


def test_tags_are_coerced_and_sorted():
    assert coerce_tags(None) == []
    assert coerce_tags("log, metric") == ["log", "metric"]
    record = normalize_record(
        {"asset_id": "A-1", "source_type": "json", "size_value": 0, "tags": ["z", "a"]}
    )
    assert record["tags"] == ["a", "z"]


def test_file_name_split():
    assert split_file_name("/foo/bar/report.pdf") == ("report.pdf", ".pdf")
    assert split_file_name("bucket/key/report.csv") == ("report.csv", ".csv")
    assert split_file_name("/foo/bar/README") == ("README", None)
    assert split_file_name(None) == (None, None)


def test_canonical_output_has_exactly_nine_fields(raw_record):
    canonical = to_canonical(normalize_record(raw_record))
    assert set(canonical) == {
        "asset_id", "source_type", "size_gb", "created_ts", "modified_ts",
        "owner_dept", "tags", "checksum", "policy_id",
    }


def test_handoff_keeps_db_metadata_separate(raw_record):
    handoff = to_handoff(normalize_record(raw_record))
    assert handoff["ingestion_meta"]["file_name"] == "app_1.log"
    assert handoff["ingestion_meta"]["file_extension"] == ".log"
    assert handoff["ingestion_meta"]["is_duplicate"] is False
    assert "file_name" not in handoff  # canonical contract stays clean


def test_bad_record_is_reported_not_crashing(raw_record):
    broken = dict(raw_record, size_value="not-a-number")
    records, errors = normalize_records([raw_record, broken])
    assert len(records) == 1
    assert len(errors) == 1
    assert errors[0]["stage"] == "normalize"
