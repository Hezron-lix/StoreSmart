"""Shared pytest fixtures and builders for the ingestion tests."""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from backend.parsers.txt_layout_config import EXPECTED_LINE_LENGTH


def make_txt_line(
    record_id: str = "DMP0000001",
    date: str = "20200927",
    time: str = "093917",
    size: int = 59294321,
    owner_dept: str = "SUPPORT",
    policy_id: str = "POL-MKT-3Y",
) -> str:
    """Build a fixed-width mainframe line matching the configured layout."""
    line = (
        f"{record_id:<10}"
        f"{date:<8}"
        f"{time:<6}"
        f"{size:08d}"
        f"{owner_dept:<10}"
        f"{policy_id:<10}"
    )
    assert len(line) >= EXPECTED_LINE_LENGTH
    return line


def make_json_line(**overrides: Any) -> str:
    """Build one JSON Lines telemetry event."""
    payload: Dict[str, Any] = {
        "file_id": "TS-20260821-00001",
        "path": "/telemetry/logs/2026/03/14/app_1.log",
        "size_bytes": 1734713,
        "owner_dept": "Finance",
        "timestamp": "2024-03-06T08:04:23Z",
        "policy_id": "POL-ANL-1Y",
        "tags": ["log"],
    }
    event = overrides.pop("event", "file_created")
    payload.update(overrides)
    return json.dumps({"event": event, "payload": payload})


@pytest.fixture
def json_file(tmp_path):
    path = tmp_path / "sample_telemetry_ws.json"
    path.write_text(
        "\n".join(
            [
                make_json_line(),
                make_json_line(
                    file_id="TS-20260821-00002",
                    event="file_modified",
                    path="/telemetry/logs/2026/05/20/app_57.log",
                    size_bytes=31429991,
                    owner_dept="Marketing",
                    timestamp="2024-11-13T11:17:20Z",
                    tags=["metric", "log"],
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "sample_cloud_metadata.csv"
    path.write_text(
        "bucket,key,size_bytes,created,owner,policy_id\n"
        "finance-bucket,hr-bucket/files/employee_1.docx,14041136697,"
        "2022-07-21T01:27:25Z,Sales,POL-SUP-1Y\n"
        "data-lake-bucket,analytics-bucket/raw/events_3.parquet,12454290491,"
        "2020-09-12T23:56:44Z,Support,POL-HR-5Y\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def txt_file(tmp_path):
    path = tmp_path / "sample_mainframe_fixed.txt"
    path.write_text(
        "\n".join(
            [
                make_txt_line(),
                make_txt_line(
                    record_id="DMP0000002",
                    date="20230703",
                    time="230939",
                    size=7994133,
                    owner_dept="OPERATIONS",
                    policy_id="POL-SAL-2Y",
                ),
                # 53-character line: the known ENGINEERING overflow defect.
                "DMP00000092022090707384109482944ENGINEERINGPOL-ANL-1Y",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def yaml_file(tmp_path):
    path = tmp_path / "sample_vm_config.yaml"
    path.write_text(
        "# StorageWise AI - VM Configuration Data\n"
        "department: Support\n"
        "disk:\n"
        "  size_gb: 200\n"
        "  snapshots:\n"
        "  - created: '2023-06-10T04:35:08Z'\n"
        "    name: vm1-snap-1\n"
        "  - created: '2024-10-21T09:44:43Z'\n"
        "    name: vm1-snap-2\n"
        "owner: IT\n"
        "policy_id: POL-LGL-7Y\n"
        "tags:\n"
        "- staging\n"
        "- prod\n"
        "vm_id: vm-1000\n"
        "---\n"
        "department: IT\n"
        "disk:\n"
        "  size_gb: 100\n"
        "owner: Finance\n"
        "policy_id: POL-FIN-7Y\n"
        "tags:\n"
        "- prod\n"
        "vm_id: vm-1001\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def raw_record():
    """A minimal, valid raw record as produced by a parser."""
    return {
        "asset_id": "TS-0001",
        "source_type": "json",
        "size_value": 1_073_741_824,
        "size_unit": "B",
        "created_ts": "2024-03-06T08:04:23Z",
        "modified_ts": None,
        "owner_dept": "Finance",
        "tags": ["log"],
        "policy_id": "POL-ANL-1Y",
        "source_path": "/telemetry/logs/app_1.log",
        "file_name": "app_1.log",
        "file_extension": ".log",
        "source_event": "file_created",
    }
