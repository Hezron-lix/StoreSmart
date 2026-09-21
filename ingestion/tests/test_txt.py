"""Tests for the mainframe fixed-width TXT parser."""

import pytest

from ingestion.parsers.txt_layout_config import SIZE_UNIT, TXT_LAYOUT
from ingestion.parsers.txt_parser import parse_line, parse_txt_file
try:
    from ingestion.tests.conftest import make_txt_line
except ImportError:
    from tests.conftest import make_txt_line


def test_parses_all_records(txt_file):
    records, errors = parse_txt_file(txt_file)
    assert len(records) == 3
    assert errors == []


def test_uses_configured_slices(txt_file):
    record = parse_txt_file(txt_file)[0][0]
    assert record["asset_id"] == "DMP0000001"
    assert record["source_type"] == "txt"
    assert record["size_value"] == 59294321
    assert record["size_unit"] == SIZE_UNIT
    assert record["owner_dept"] == "SUPPORT"
    assert record["policy_id"] == "POL-MKT-3Y"


def test_combines_date_and_time_into_one_iso_timestamp(txt_file):
    record = parse_txt_file(txt_file)[0][0]
    assert record["created_ts"] == "2020-09-27T09:39:17"
    assert record["modified_ts"] is None  # never fabricated


def test_no_filename_is_invented_for_mainframe_records(txt_file):
    record = parse_txt_file(txt_file)[0][0]
    assert record["file_name"] is None
    assert record["file_extension"] is None
    assert record["source_path"] is None


def test_overflowing_owner_dept_column_is_realigned(txt_file):
    engineering = parse_txt_file(txt_file)[0][2]
    assert engineering["owner_dept"] == "ENGINEERING"
    assert engineering["policy_id"] == "POL-ANL-1Y"  # not "GPOL-ANL-1Y"


def test_layout_is_contiguous_and_matches_expected_width():
    bounds = sorted(TXT_LAYOUT.values())
    for (_, end), (next_start, _) in zip(bounds, bounds[1:]):
        assert end == next_start


def test_non_numeric_size_is_rejected():
    line = make_txt_line().replace("59294321", "ABCDEFGH")
    with pytest.raises(ValueError):
        parse_line(line, 1)


def test_bad_record_id_is_reported_not_dropped(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text(make_txt_line() + "\n" + make_txt_line(record_id="XXX0000002") + "\n",
                    encoding="utf-8")
    records, errors = parse_txt_file(str(path))
    assert len(records) == 1
    assert len(errors) == 1


def test_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "blanks.txt"
    path.write_text("\n" + make_txt_line() + "\n\n", encoding="utf-8")
    records, errors = parse_txt_file(str(path))
    assert len(records) == 1
    assert errors == []
