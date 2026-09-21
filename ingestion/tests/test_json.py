"""Tests for the JSON Lines telemetry parser."""

import pytest

from ingestion.parsers.json_parser import parse_json_file, parse_payload
try:
    from ingestion.tests.conftest import make_json_line
except ImportError:
    from tests.conftest import make_json_line


def test_parses_all_lines(json_file):
    records, errors = parse_json_file(json_file)
    assert len(records) == 2
    assert errors == []


def test_maps_payload_fields(json_file):
    records, _ = parse_json_file(json_file)
    first = records[0]
    assert first["asset_id"] == "TS-20260821-00001"
    assert first["source_type"] == "json"
    assert first["size_value"] == 1734713
    assert first["size_unit"] == "B"
    assert first["owner_dept"] == "Finance"
    assert first["policy_id"] == "POL-ANL-1Y"
    assert first["tags"] == ["log"]


def test_derives_file_name_and_extension(json_file):
    records, _ = parse_json_file(json_file)
    assert records[0]["file_name"] == "app_1.log"
    assert records[0]["file_extension"] == ".log"


def test_event_decides_which_timestamp_is_used(json_file):
    created, modified = parse_json_file(json_file)[0]
    assert created["created_ts"] == "2024-03-06T08:04:23Z"
    assert created["modified_ts"] is None
    assert modified["modified_ts"] == "2024-11-13T11:17:20Z"
    assert modified["created_ts"] is None


def test_malformed_line_is_reported_not_dropped_silently(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(make_json_line() + "\n{not json}\n", encoding="utf-8")

    records, errors = parse_json_file(str(path))
    assert len(records) == 1
    assert len(errors) == 1
    assert "invalid JSON" in errors[0]["error"]


def test_missing_file_id_is_an_error(tmp_path):
    path = tmp_path / "nofileid.json"
    path.write_text('{"event": "file_created", "payload": {"size_bytes": 1}}\n', encoding="utf-8")

    records, errors = parse_json_file(str(path))
    assert records == []
    assert "asset identifier missing" in errors[0]["error"]


def test_empty_file_yields_nothing(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    records, errors = parse_json_file(str(path))
    assert records == []
    assert len(errors) == 1
    assert "empty" in errors[0]["error"].lower()


def test_payload_must_be_an_object():
    with pytest.raises(ValueError):
        parse_payload(None)
