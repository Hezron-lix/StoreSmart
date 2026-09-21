"""Tests for deterministic fingerprints and duplicate detection."""

from ingestion.normalize import build_fingerprint, deduplicate, normalize_record
from ingestion.utils import is_sha256_hex


def test_checksum_is_a_sha256_hex_digest(raw_record):
    assert is_sha256_hex(normalize_record(raw_record)["checksum"])


def test_same_record_always_produces_the_same_checksum(raw_record):
    first = normalize_record(dict(raw_record))
    second = normalize_record(dict(raw_record))
    assert first["checksum"] == second["checksum"]


def test_checksum_is_independent_of_tag_order(raw_record):
    unsorted_tags = normalize_record(dict(raw_record, tags=["b", "a"]))
    sorted_tags = normalize_record(dict(raw_record, tags=["a", "b"]))
    assert unsorted_tags["checksum"] == sorted_tags["checksum"]


def test_changing_an_attribute_changes_the_checksum(raw_record):
    original = normalize_record(dict(raw_record))
    larger = normalize_record(dict(raw_record, size_value=999))
    assert original["checksum"] != larger["checksum"]


def test_same_asset_under_two_ids_is_detected_as_duplicate(raw_record):
    first = normalize_record(dict(raw_record, asset_id="A-1"))
    second = normalize_record(dict(raw_record, asset_id="A-2"))
    assert first["checksum"] == second["checksum"]

    unique, duplicates = deduplicate([first, second])
    assert len(unique) == 1
    assert len(duplicates) == 1
    assert duplicates[0]["asset_id"] == "A-2"
    assert duplicates[0]["is_duplicate"] is True
    assert duplicates[0]["duplicate_of"] == "A-1"


def test_first_occurrence_wins_and_is_not_flagged(raw_record):
    records = [normalize_record(dict(raw_record, asset_id=f"A-{i}")) for i in range(3)]
    unique, duplicates = deduplicate(records)
    assert unique[0]["is_duplicate"] is False
    assert unique[0]["duplicate_of"] is None
    assert len(duplicates) == 2


def test_distinct_assets_are_not_duplicates(raw_record):
    first = normalize_record(dict(raw_record, asset_id="A-1"))
    second = normalize_record(dict(raw_record, asset_id="A-2", size_value=42))
    unique, duplicates = deduplicate([first, second])
    assert len(unique) == 2
    assert duplicates == []


def test_fingerprint_ignores_asset_id_and_source_type(raw_record):
    record = normalize_record(raw_record)
    variant = dict(record, asset_id="totally-different", source_type="csv")
    assert build_fingerprint(record) == build_fingerprint(variant)


def test_empty_input(raw_record):
    assert deduplicate([]) == ([], [])
