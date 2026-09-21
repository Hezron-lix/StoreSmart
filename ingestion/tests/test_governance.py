"""
Tests for governance rules, RBAC, retention enforcement, priority protection,
checksum validation, and audit recording.
"""
from datetime import datetime, timezone, timedelta
import pytest

from ingestion.governance import (
    load_retention_policies,
    evaluate_action,
    write_audit_record,
    get_audit_csv_content,
    DETERMINISTIC_POLICIES,
)


def test_matrix_loading():
    """Verify Retention_Policy_Matrix is loaded with standard policies."""
    policies = load_retention_policies()
    assert "POL-FIN-7Y" in policies
    assert policies["POL-FIN-7Y"]["retention_days"] == 2555
    assert "POL-LGL-7Y" in policies
    assert policies["POL-LGL-7Y"]["retention_days"] == 2555
    assert policies["POL-ENG-3Y"]["retention_days"] == 1095


def test_scenario_a_viewer_blocked_by_rbac():
    """Scenario A: Viewer attempts DELETE -> BLOCKED by RBAC."""
    asset = {
        "file_id": "file_test_1",
        "file_name": "test_doc.csv",
        "department": "Finance",
        "size_gb": 1.5,
        "policy_id": "POL-FIN-7Y",
        "checksum": "a" * 64,
        "created_ts": (datetime.now(timezone.utc) - timedelta(days=3000)).isoformat(),
    }
    user = {"name": "viewer_user", "role": "Viewer"}
    decision = evaluate_action(asset, "DELETE", user=user)

    assert decision["decision"] == "BLOCKED"
    assert decision["policy_id"] == "RBAC"
    assert "Super-Admin" in decision["reason"]


def test_scenario_b_super_admin_retention_blocked():
    """Scenario B: Super-Admin attempts DELETE on file under retention -> BLOCKED by RETENTION."""
    # File created 100 days ago, retention is 7 years (2555 days)
    asset = {
        "file_id": "file_test_2",
        "file_name": "quarterly_finances.xlsx",
        "department": "Finance",
        "size_gb": 2.0,
        "policy_id": "POL-FIN-7Y",
        "checksum": "b" * 64,
        "created_ts": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
    }
    user = {"name": "admin_user", "role": "Super-Admin"}
    decision = evaluate_action(asset, "DELETE", user=user)

    assert decision["decision"] == "BLOCKED"
    assert decision["policy_id"] == "POL-FIN-7Y"
    assert "Retention active" in decision["reason"]
    assert "overrides AI" in decision["reason"]


def test_scenario_c_super_admin_legal_compression_blocked():
    """Scenario C: Super-Admin attempts COMPRESS on legal/protected file -> BLOCKED by PRIORITY/PROTECTION."""
    asset = {
        "file_id": "file_test_3",
        "file_name": "litigation_hold.pdf",
        "department": "Legal",
        "size_gb": 0.5,
        "policy_id": "POL-LGL-7Y",
        "checksum": "c" * 64,
        "created_ts": (datetime.now(timezone.utc) - timedelta(days=500)).isoformat(),
    }
    user = {"name": "admin_user", "role": "Super-Admin"}
    decision = evaluate_action(asset, "COMPRESS", user=user)

    assert decision["decision"] == "BLOCKED"
    assert decision["policy_id"] == "POL-LGL-7Y"
    assert "Priority rule" in decision["reason"]
    assert "protected from compression" in decision["reason"]


def test_scenario_d_super_admin_permitted_compress():
    """Scenario D: Super-Admin attempts permitted COMPRESS -> ALLOWED."""
    asset = {
        "file_id": "file_test_4",
        "file_name": "build_artifact.log",
        "department": "Engineering",
        "size_gb": 4.5,
        "policy_id": "POL-ENG-3Y",
        "checksum": "d" * 64,
        "created_ts": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
    }
    user = {"name": "admin_user", "role": "Super-Admin"}
    decision = evaluate_action(asset, "COMPRESS", user=user)

    assert decision["decision"] == "ALLOWED"
    assert decision["approval_required"] is False
    assert decision["risk_level"] == "LOW"


def test_scenario_e_high_risk_delete_requires_approval():
    """Scenario E: High-risk DELETE (>10GB or critical dept) -> APPROVAL_REQUIRED."""
    # File age past retention (4000 days > 3 years), but size is 15 GB
    asset = {
        "file_id": "file_test_5",
        "file_name": "huge_db_dump.sql",
        "department": "Engineering",
        "size_gb": 15.0,
        "policy_id": "POL-ENG-3Y",
        "checksum": "e" * 64,
        "created_ts": (datetime.now(timezone.utc) - timedelta(days=4000)).isoformat(),
    }
    user = {"name": "admin_user", "role": "Super-Admin"}
    decision = evaluate_action(asset, "DELETE", user=user, bypass_approval=False)

    assert decision["decision"] == "APPROVAL_REQUIRED"
    assert decision["approval_required"] is True
    assert decision["risk_level"] == "HIGH"
    assert "dual approval" in decision["reason"].lower()


def test_integrity_guardrail_corrupted_checksum():
    """Corrupted checksum (< 64 hex chars or invalid) -> BLOCKED by CHECKSUM."""
    asset = {
        "file_id": "file_test_corrupt",
        "file_name": "corrupt.csv",
        "department": "Engineering",
        "size_gb": 1.0,
        "policy_id": "POL-ENG-3Y",
        "checksum": "corrupted_short_hash",
        "created_ts": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
    }
    user = {"name": "admin_user", "role": "Super-Admin"}
    decision = evaluate_action(asset, "COMPRESS", user=user)

    assert decision["decision"] == "BLOCKED"
    assert decision["policy_id"] == "CHECKSUM-INTEGRITY"


def test_audit_recording():
    """Verify audit record writing and retrieval."""
    write_audit_record(
        asset_id="test_asset_audit_1",
        action="DELETE",
        user_id="admin_user",
        user_role="Super-Admin",
        decision="BLOCKED",
        reason="Test blocked reason",
        policy_id="POL-TEST",
        risk_level="HIGH",
    )
    content = get_audit_csv_content()
    assert "test_asset_audit_1" in content
    assert "Super-Admin" in content
    assert "BLOCKED" in content
