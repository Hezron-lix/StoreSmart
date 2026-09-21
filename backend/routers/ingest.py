"""Ingest router: multi-format upload endpoint.

Moved from ingestion/api.py. Accepts JSON / CSV / TXT / YAML file uploads
in one request, parses them with backend.parsers, normalizes and dedupes
via backend.normalize, and persists to MySQL via backend.db.import_assets.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.db import import_assets
from backend.normalize import (
    deduplicate,
    normalize_records,
    to_canonical,
    validate_records,
)
from backend.parsers import (
    parse_csv_file,
    parse_json_file,
    parse_txt_file,
    parse_yaml_file,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


PARSERS = {
    ".json": (
        "json",
        parse_json_file,
    ),
    ".jsonl": (
        "json",
        parse_json_file,
    ),
    ".csv": (
        "csv",
        parse_csv_file,
    ),
    ".txt": (
        "txt",
        parse_txt_file,
    ),
    ".yaml": (
        "yaml",
        parse_yaml_file,
    ),
    ".yml": (
        "yaml",
        parse_yaml_file,
    ),
}


@router.post(
    "",
    response_model=None,
)
async def ingest(
    json_file: UploadFile | None = File(default=None),
    csv_file: UploadFile | None = File(default=None),
    txt_file: UploadFile | None = File(default=None),
    yaml_file: UploadFile | None = File(default=None),
):
    # --------------------------------------------------------
    # COLLECT UPLOADED FILES
    # --------------------------------------------------------
    uploaded_files = [
        file
        for file in [
            json_file,
            csv_file,
            txt_file,
            yaml_file,
        ]
        if (
            file is not None
            and file.filename
        )
    ]

    if not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail=(
                "Upload at least one "
                "JSON, CSV, TXT, "
                "or YAML file."
            ),
        )

    # ========================================================
    # INITIALIZE
    # ========================================================
    raw_records = []
    parse_errors = []
    counts = {
        "json": 0,
        "txt": 0,
        "csv": 0,
        "yaml": 0,
    }

    # ========================================================
    # PARSE
    # ========================================================
    for uploaded_file in uploaded_files:
        filename = (
            uploaded_file.filename
            or "uploaded_file"
        )

        extension = (
            Path(filename)
            .suffix
            .lower()
        )

        if extension not in PARSERS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file format: {filename}"
                ),
            )

        source_type, parser = PARSERS[extension]
        temp_path = None

        try:
            # ------------------------------------------------
            # READ FILE
            # ------------------------------------------------
            content = await uploaded_file.read()

            if not content:
                parse_errors.append(
                    {
                        "stage": "upload",
                        "source_type": source_type,
                        "filename": filename,
                        "error": "Uploaded file is empty.",
                    }
                )
                continue

            # ------------------------------------------------
            # WRITE TEMP FILE
            # ------------------------------------------------
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                suffix=extension,
            ) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            # ------------------------------------------------
            # PARSE
            # ------------------------------------------------
            records, errors = parser(temp_path)

            counts[source_type] += len(records)
            raw_records.extend(records)
            parse_errors.extend(errors)

        except Exception as exc:
            parse_errors.append(
                {
                    "stage": "parse",
                    "source_type": source_type,
                    "filename": filename,
                    "error": str(exc),
                }
            )

        finally:
            # ------------------------------------------------
            # CLEAN TEMP FILE
            # ------------------------------------------------
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # ========================================================
    # NORMALIZE
    # ========================================================
    normalized_records = []
    normalize_errors = []

    if raw_records:
        try:
            (
                normalized_records,
                normalize_errors,
            ) = normalize_records(raw_records)
        except Exception as exc:
            normalize_errors.append(
                {
                    "stage": "normalize",
                    "error": str(exc),
                }
            )

    all_errors = parse_errors + normalize_errors

    # ========================================================
    # VALIDATE
    # ========================================================
    valid_records = []
    invalid_records = []

    if normalized_records:
        try:
            (
                valid_records,
                invalid_records,
            ) = validate_records(normalized_records)
        except Exception as exc:
            all_errors.append(
                {
                    "stage": "validate",
                    "error": str(exc),
                }
            )

    # ========================================================
    # DEDUPLICATE
    # ========================================================
    unique_records = []
    duplicate_records = []

    if valid_records:
        try:
            (
                unique_records,
                duplicate_records,
            ) = deduplicate(valid_records)
        except Exception as exc:
            all_errors.append(
                {
                    "stage": "deduplicate",
                    "error": str(exc),
                }
            )

    # ========================================================
    # CANONICAL OUTPUT
    # ========================================================
    canonical_records = []

    for record in unique_records:
        try:
            canonical_records.append(
                to_canonical(record)
            )
        except Exception as exc:
            all_errors.append(
                {
                    "stage": "canonical",
                    "asset_id": record.get("asset_id"),
                    "error": str(exc),
                }
            )

    # ========================================================
    # MYSQL IMPORT
    # ========================================================
    database_import = None

    if canonical_records:
        try:
            database_import = import_assets(canonical_records)
        except Exception as exc:
            all_errors.append(
                {
                    "stage": "database_import",
                    "error": str(exc),
                }
            )
            database_import = {
                "success": False,
                "error": str(exc),
            }

    # ========================================================
    # SUMMARY
    # ========================================================
    summary = {
        "records_by_source": counts,
        "stats": {
            "total_parsed": len(raw_records),
            "normalized": len(normalized_records),
            "valid": len(valid_records),
            "invalid": len(invalid_records),
            "duplicates": len(duplicate_records),
            "errors": len(all_errors),
            "canonical_records": len(canonical_records),
        },
    }

    # ========================================================
    # RESPONSE
    # ========================================================
    return {
        "success": True,
        "message": "Ingestion completed successfully.",
        "summary": summary,
        "database_import": database_import,
        "records_preview": canonical_records[:10],
        "invalid_records_preview": invalid_records[:10],
        "errors_preview": all_errors[:10],
    }
