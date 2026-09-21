"""Audit log helpers: append rows to the CSV audit trail, read it back.

The audit log is a flat CSV with a fixed header. It is append-only from the
application's perspective — no function in this module edits or deletes rows.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import SETTINGS


AUDIT_HEADER = "timestamp,user,role,action,file,policy_id,outcome,reason"


def _csv_escape(value: object) -> str:
    """Escape a value for CSV: double internal quotes, wrap in quotes."""
    text = "" if value is None else str(value)
    return '"' + text.replace('"', '""') + '"'


def write_audit_record(
    user: Optional[str] = None,
    role: Optional[str] = None,
    action: Optional[str] = None,
    file: Optional[str] = None,
    policy_id: Optional[str] = None,
    outcome: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Append one audit row to the CSV log.

    Creates the file (with header) if it does not exist. Never rewrites or
    truncates existing rows.
    """
    log_path: Path = SETTINGS.log_path_abs
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    row = ",".join(
        _csv_escape(v)
        for v in (
            timestamp,
            user,
            role,
            action,
            file,
            policy_id,
            outcome,
            reason,
        )
    )

    write_header = not log_path.exists() or log_path.stat().st_size == 0

    with log_path.open("a", encoding="utf-8", newline="") as handle:
        if write_header:
            handle.write(AUDIT_HEADER + "\n")
        handle.write(row + "\n")


def get_audit_csv_content() -> str:
    """Return the full contents of the audit CSV as a single string.

    If the file does not exist yet, initialises it with just the header and
    returns that header.
    """
    log_path: Path = SETTINGS.log_path_abs
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.write_text(AUDIT_HEADER + "\n", encoding="utf-8")

    return log_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    # Smoke test — run with: python -m backend.audit
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        # Redirect SETTINGS.log_path to a temp file for the test
        original = SETTINGS.log_path
        SETTINGS.log_path = str(Path(tmp) / "audit.csv")
        try:
            write_audit_record(
                user="alice",
                role="Super-Admin",
                action="delete",
                file="invoice.pdf",
                policy_id="POL-FIN-7Y",
                outcome="BLOCKED",
                reason='File is only 3 years old, needs 7 (test: "quoted, comma")',
            )
            write_audit_record(
                user="bob",
                role="Viewer",
                action="compress",
                file="log.txt",
                policy_id=None,
                outcome="ALLOWED",
                reason="",
            )
            content = get_audit_csv_content()
            assert AUDIT_HEADER in content
            assert "alice" in content
            assert "BLOCKED" in content
            assert "ALLOWED" in content
            # Quoted-comma value survives round-trip
            assert '"File is only 3 years old, needs 7 (test: ""quoted, comma"")"' in content
        finally:
            SETTINGS.log_path = original

    print("audit.py smoke test: OK")
