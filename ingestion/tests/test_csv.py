"""Tests for the cloud metadata CSV parser."""

from ingestion.parsers.csv_parser import MAX_ASSET_ID_LENGTH, build_asset_id, parse_csv_file


def test_parses_rows(csv_file):
    records, errors = parse_csv_file(csv_file)
    assert len(records) == 2
    assert errors == []


def test_maps_fields(csv_file):
    record = parse_csv_file(csv_file)[0][0]
    assert record["source_type"] == "csv"
    assert record["size_value"] == "14041136697"
    assert record["size_unit"] == "B"
    assert record["owner_dept"] == "Sales"
    assert record["policy_id"] == "POL-SUP-1Y"
    assert record["created_ts"] == "2022-07-21T01:27:25Z"
    assert record["modified_ts"] is None


def test_asset_id_is_deterministic_and_derived_from_bucket_key(csv_file):
    record = parse_csv_file(csv_file)[0][0]
    assert record["asset_id"] == "finance-bucket/hr-bucket/files/employee_1.docx"
    assert build_asset_id("a", "b") == build_asset_id("a", "b")


def test_very_long_keys_fold_into_a_short_deterministic_id():
    long_key = "x" * 300
    asset_id = build_asset_id("bucket", long_key)
    assert len(asset_id) <= MAX_ASSET_ID_LENGTH
    assert asset_id.startswith("csv-")
    assert asset_id == build_asset_id("bucket", long_key)


def test_file_name_and_extension_from_key(csv_file):
    record = parse_csv_file(csv_file)[0][0]
    assert record["file_name"] == "employee_1.docx"
    assert record["file_extension"] == ".docx"


def test_missing_key_is_reported(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "bucket,key,size_bytes,created,owner,policy_id\n"
        "finance-bucket,,100,2022-07-21T01:27:25Z,Sales,POL-SUP-1Y\n",
        encoding="utf-8",
    )
    records, errors = parse_csv_file(str(path))
    assert records == []
    assert len(errors) == 1


def test_missing_header_columns_are_reported(tmp_path):
    path = tmp_path / "wrong_header.csv"
    path.write_text("bucket,key\nfinance-bucket,a/b.txt\n", encoding="utf-8")
    records, errors = parse_csv_file(str(path))
    assert records == []
    assert "missing columns" in errors[0]["error"]


def test_empty_file_is_reported(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    records, errors = parse_csv_file(str(path))
    assert records == []
    assert len(errors) == 1
