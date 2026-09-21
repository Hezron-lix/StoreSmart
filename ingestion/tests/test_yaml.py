"""Tests for the multi-document VM configuration YAML parser."""

import pytest

from ingestion.parsers.yaml_parser import parse_document, parse_yaml_file


def test_each_document_becomes_its_own_asset(yaml_file):
    records, errors = parse_yaml_file(yaml_file)
    assert len(records) == 2
    assert errors == []
    assert [record["asset_id"] for record in records] == ["vm-1000", "vm-1001"]


def test_disk_size_is_already_gb(yaml_file):
    record = parse_yaml_file(yaml_file)[0][0]
    assert record["size_value"] == 200
    assert record["size_unit"] == "GB"


def test_department_is_used_as_owner_dept(yaml_file):
    record = parse_yaml_file(yaml_file)[0][0]
    assert record["owner_dept"] == "Support"


def test_latest_snapshot_becomes_modified_ts_and_created_stays_null(yaml_file):
    record = parse_yaml_file(yaml_file)[0][0]
    assert record["modified_ts"] == "2024-10-21T09:44:43Z"
    assert record["created_ts"] is None


def test_no_snapshots_means_no_timestamps(yaml_file):
    record = parse_yaml_file(yaml_file)[0][1]
    assert record["created_ts"] is None
    assert record["modified_ts"] is None


def test_no_filename_is_invented_for_vm_disks(yaml_file):
    record = parse_yaml_file(yaml_file)[0][0]
    assert record["file_name"] is None
    assert record["file_extension"] is None


def test_missing_vm_id_raises():
    with pytest.raises(ValueError):
        parse_document({"department": "IT", "disk": {"size_gb": 10}})


def test_malformed_yaml_is_reported(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("vm_id: vm-1\n\tbad: indent\n", encoding="utf-8")
    records, errors = parse_yaml_file(str(path))
    assert records == []
    assert len(errors) == 1


def test_empty_file_yields_nothing(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert parse_yaml_file(str(path)) == ([], [])
