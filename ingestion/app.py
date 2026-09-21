"""StorageWise AI - ingestion pipeline entry point.

    python -m ingestion.app
    python -m ingestion.app --data-dir data --output-dir output

Pipeline: load -> parse (json/txt/csv/yaml) -> normalize -> fingerprint ->
validate -> deduplicate -> write canonical + handoff output.

This module does not touch MySQL, ML, dashboards, governance or actions.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

from ingestion.normalize import (
    deduplicate,
    normalize_records,
    to_canonical,
    to_handoff,
    validate_records,
)
from ingestion.parsers import (
    parse_csv_file,
    parse_json_file,
    parse_txt_file,
    parse_yaml_file,
)
from ingestion.utils import get_logger

logger = get_logger(__name__)

# file extension -> (source_type, parser function)
PARSERS = {
    ".json": ("json", parse_json_file),
    ".jsonl": ("json", parse_json_file),
    ".txt": ("txt", parse_txt_file),
    ".csv": ("csv", parse_csv_file),
    ".yaml": ("yaml", parse_yaml_file),
    ".yml": ("yaml", parse_yaml_file),
}

CANONICAL_OUTPUT = "canonical_records.json"
HANDOFF_OUTPUT = "handoff_records.json"
DUPLICATES_OUTPUT = "duplicate_records.json"
INVALID_OUTPUT = "invalid_records.json"
SUMMARY_OUTPUT = "ingestion_summary.json"


def discover_files(data_dir: str) -> List[Tuple[str, str, Any]]:
    """Return [(source_type, path, parser)] for every supported file in data_dir."""
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"data directory not found: {data_dir}")

    found: List[Tuple[str, str, Any]] = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        extension = os.path.splitext(name)[1].lower()
        if extension in PARSERS:
            source_type, parser = PARSERS[extension]
            found.append((source_type, path, parser))
        else:
            logger.debug("skipping unsupported file: %s", name)
    return found


def parse_all(data_dir: str) -> Tuple[List[Dict], List[Dict], Dict[str, int]]:
    """Parse every supported file. Returns (raw_records, errors, counts_by_source)."""
    raw_records: List[Dict] = []
    errors: List[Dict] = []
    counts: Dict[str, int] = {"json": 0, "txt": 0, "csv": 0, "yaml": 0}

    files = discover_files(data_dir)
    if not files:
        logger.warning("no supported input files found in %s", data_dir)

    for source_type, path, parser in files:
        logger.info("parsing %s (%s)", path, source_type)
        try:
            records, file_errors = parser(path)
        except OSError as exc:
            errors.append(
                {
                    "stage": "read",
                    "source_type": source_type,
                    "location": path,
                    "error": str(exc),
                }
            )
            logger.error("could not read %s: %s", path, exc)
            continue

        counts[source_type] += len(records)
        raw_records.extend(records)
        errors.extend(file_errors)

    return raw_records, errors, counts


def write_json(path: str, payload: Any) -> None:
    """Write `payload` as pretty-printed UTF-8 JSON."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    logger.info("wrote %s", path)


def format_summary(counts: Dict[str, int], stats: Dict[str, int], output_path: str) -> str:
    """Build the concise console summary block."""
    return "\n".join(
        [
            "",
            "StorageWise AI Ingestion",
            "------------------------",
            f"JSON records:   {counts['json']:>7}",
            f"TXT records:    {counts['txt']:>7}",
            f"CSV records:    {counts['csv']:>7}",
            f"YAML records:   {counts['yaml']:>7}",
            "",
            f"Total parsed:   {stats['total_parsed']:>7}",
            f"Valid:          {stats['valid']:>7}",
            f"Invalid:        {stats['invalid']:>7}",
            f"Duplicates:     {stats['duplicates']:>7}",
            f"Parse errors:   {stats['errors']:>7}",
            "",
            "Canonical output:",
            output_path,
            "",
        ]
    )


def run(data_dir: str, output_dir: str, include_duplicates: bool = False) -> Dict[str, Any]:
    """Run the full ingestion pipeline. Returns the summary dictionary."""
    raw_records, errors, counts = parse_all(data_dir)

    records, normalize_errors = normalize_records(raw_records)
    errors.extend(normalize_errors)

    valid, invalid = validate_records(records)
    unique, duplicates = deduplicate(valid)

    canonical_source = valid if include_duplicates else unique
    canonical = [to_canonical(record) for record in canonical_source]
    handoff = [to_handoff(record) for record in valid]

    stats = {
        "total_parsed": len(raw_records),
        "valid": len(valid),
        "invalid": len(invalid),
        "duplicates": len(duplicates),
        "errors": len(errors),
        "canonical_written": len(canonical),
    }

    canonical_path = os.path.join(output_dir, CANONICAL_OUTPUT)
    write_json(canonical_path, canonical)
    write_json(os.path.join(output_dir, HANDOFF_OUTPUT), handoff)
    write_json(
        os.path.join(output_dir, DUPLICATES_OUTPUT),
        [to_handoff(record) for record in duplicates],
    )
    write_json(os.path.join(output_dir, INVALID_OUTPUT), {"invalid": invalid, "errors": errors})

    summary = {
        "records_by_source": counts,
        "stats": stats,
        "duplicates_included_in_canonical": include_duplicates,
        "outputs": {
            "canonical": canonical_path,
            "handoff": os.path.join(output_dir, HANDOFF_OUTPUT),
            "duplicates": os.path.join(output_dir, DUPLICATES_OUTPUT),
            "invalid": os.path.join(output_dir, INVALID_OUTPUT),
        },
    }
    write_json(os.path.join(output_dir, SUMMARY_OUTPUT), summary)

    print(format_summary(counts, stats, canonical_path))
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.app",
        description="StorageWise AI ingestion layer (parse/normalize/validate/dedupe).",
    )
    parser.add_argument("--data-dir", default=os.getenv("STORAGEWISE_DATA_DIR", "data"))
    parser.add_argument("--output-dir", default=os.getenv("STORAGEWISE_OUTPUT_DIR", "output"))
    parser.add_argument(
        "--include-duplicates",
        action="store_true",
        help="keep duplicate records in canonical_records.json (they are flagged either way)",
    )
    parser.add_argument("--log-level", default=os.getenv("STORAGEWISE_LOG_LEVEL", "INFO"))
    return parser


def main() -> int:
    load_dotenv()
    args = build_arg_parser().parse_args()
    get_logger("ingestion", args.log_level)
    for name in ("ingestion.app", "ingestion.normalize", "ingestion.utils"):
        get_logger(name, args.log_level)

    try:
        run(args.data_dir, args.output_dir, args.include_duplicates)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
