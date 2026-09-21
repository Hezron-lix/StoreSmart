"""Format-specific parsers. Each returns (raw_records, errors)."""

from ingestion.parsers.csv_parser import parse_csv_file
from ingestion.parsers.json_parser import parse_json_file
from ingestion.parsers.txt_parser import parse_txt_file
from ingestion.parsers.yaml_parser import parse_yaml_file

__all__ = [
    "parse_csv_file",
    "parse_json_file",
    "parse_txt_file",
    "parse_yaml_file",
]
