"""Tests for record validation."""

from ingestion.normalize import normalize_record, validate_record, validate_records


def _valid(raw_record):
    return normalize_record(raw_record)


def test_a_normalized_record_is_valid(raw_record):
    assert validate_record(_valid(raw_record)) == []


def test_missing_asset_id_fails(raw_record):
    record = _valid(raw_record)
    record["asset_id"] = ""
    assert any("asset_id" in error for error in validate_record(record))


def test_unknown_source_type_fails(raw_record):
    record = _valid(raw_record)
    record["source_type"] = "parquet"
    assert any("source_type" in error for error in validate_record(record))


def test_negative_size_fails(raw_record):
    record = _valid(raw_record)
    record["size_gb"] = -1.0
    assert any("size_gb" in error for error in validate_record(record))


def test_non_numeric_size_fails(raw_record):
    record = _valid(raw_record)
    record["size_gb"] = "big"
    assert any("size_gb" in error for error in validate_record(record))


def test_tags_must_be_list_of_strings(raw_record):
    record = _valid(raw_record)
    record["tags"] = ["ok", 5]
    assert any("tags" in error for error in validate_record(record))


def test_checksum_must_be_sha256_hex(raw_record):
    record = _valid(raw_record)
    record["checksum"] = "abc123"
    assert any("checksum" in error for error in validate_record(record))


def test_policy_id_may_be_null(raw_record):
    record = _valid(raw_record)
    record["policy_id"] = None
    assert validate_record(record) == []


def test_bad_timestamp_fails(raw_record):
    record = _valid(raw_record)
    record["created_ts"] = "yesterday"
    assert any("created_ts" in error for error in validate_record(record))


def test_invalid_records_are_kept_and_reported(raw_record):
    good = _valid(raw_record)
    bad = _valid(raw_record)
    bad["source_type"] = "nope"

    valid, invalid = validate_records([good, bad])
    assert len(valid) == 1
    assert len(invalid) == 1
    assert invalid[0]["errors"]           # reported, not silently discarded
    assert invalid[0]["record"] is bad    # and not thrown away
