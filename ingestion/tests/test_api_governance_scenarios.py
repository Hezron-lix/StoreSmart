"""
Integration tests for FastAPI /actions/{asset_id} endpoint and governance verification.
Tests Scenarios A through E and verifies asset non-mutation on blocked/approval actions.
"""
from datetime import datetime, timezone, timedelta
import jwt
from fastapi.testclient import TestClient
import pytest

from ingestion.api import app, JWT_SECRET
from ingestion.database import fetch_asset, get_connection

client = TestClient(app)

def _make_token(username: str, role: str) -> str:
    payload = {
        "id": 999,
        "username": username,
        "role": role,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="module", autouse=True)
def setup_test_assets():
    """Ensure standard test assets exist in database for the test suite."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Asset under retention (Finance, 7 years retention, created 30 days ago)
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    # 2. Legal protected asset
    legal_ts = (datetime.now(timezone.utc) - timedelta(days=500)).strftime("%Y-%m-%d %H:%M:%S")
    # 3. Compressible engineering asset
    eng_ts = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    # 4. High-risk large asset past retention (Engineering, 3 years = 1095 days, created 1500 days ago, 25 GB)
    large_ts = (datetime.now(timezone.utc) - timedelta(days=1500)).strftime("%Y-%m-%d %H:%M:%S")

    test_records = [
        ("demo_test_retention", "fin_report.csv", "Finance", 2.5, "POL-FIN-7Y", "a" * 64, recent_ts, "csv", ".csv"),
        ("demo_test_legal", "legal_contract.txt", "Legal", 1.0, "POL-LGL-7Y", "b" * 64, legal_ts, "txt", ".txt"),
        ("demo_test_compress", "log_archive.json", "Engineering", 5.0, "POL-ENG-3Y", "c" * 64, eng_ts, "json", ".json"),
        ("demo_test_highrisk", "big_data.yaml", "Engineering", 25.0, "POL-ENG-3Y", "d" * 64, large_ts, "yaml", ".yaml"),
    ]

    for rec in test_records:
        cursor.execute(
            """
            INSERT INTO assets (asset_id, file_name, owner_dept, size_gb, policy_id, checksum, created_ts, source_type, file_extension)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                file_name = VALUES(file_name),
                owner_dept = VALUES(owner_dept),
                size_gb = VALUES(size_gb),
                policy_id = VALUES(policy_id),
                checksum = VALUES(checksum),
                created_ts = VALUES(created_ts),
                source_type = VALUES(source_type),
                file_extension = VALUES(file_extension)
            """,
            rec,
        )
    conn.commit()
    cursor.close()
    conn.close()


def test_scenario_a_viewer_blocked_by_rbac():
    """Scenario A: Viewer attempts DELETE -> BLOCKED by RBAC."""
    token = _make_token("demo_viewer", "Viewer")
    resp = client.post(
        "/actions/demo_test_retention",
        json={"action": "DELETE"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["decision"] == "BLOCKED"
    assert data["governance"]["rule"] == "RBAC"
    assert "Viewer" in data["reason"]

    # Verify asset is NOT modified or deleted
    asset = fetch_asset("demo_test_retention")
    assert asset is not None
    assert asset["asset_id"] == "demo_test_retention"


def test_scenario_b_super_admin_delete_under_retention_blocked():
    """Scenario B: Super-Admin attempts DELETE on file under retention -> BLOCKED by RETENTION."""
    token = _make_token("demo_admin", "Super-Admin")
    resp = client.post(
        "/actions/demo_test_retention",
        json={"action": "DELETE"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["decision"] == "BLOCKED"
    assert data["governance"]["policyId"] == "POL-FIN-7Y"
    assert "Retention active" in data["reason"]
    assert "overrides AI" in data["reason"]

    # Verify asset is NOT deleted
    asset = fetch_asset("demo_test_retention")
    assert asset is not None


def test_scenario_c_super_admin_compress_legal_blocked():
    """Scenario C: Super-Admin attempts COMPRESS on legal/protected file -> BLOCKED by PRIORITY."""
    token = _make_token("demo_admin", "Super-Admin")
    resp = client.post(
        "/actions/demo_test_legal",
        json={"action": "COMPRESS"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["decision"] == "BLOCKED"
    assert data["governance"]["rule"] == "PRIORITY"
    assert "protected from compression" in data["reason"]

    # Verify asset size unchanged
    asset = fetch_asset("demo_test_legal")
    assert float(asset["size_gb"]) == 1.0


def test_scenario_d_super_admin_permitted_compress():
    """Scenario D: Super-Admin attempts permitted COMPRESS -> ALLOWED and audited."""
    token = _make_token("demo_admin", "Super-Admin")
    resp = client.post(
        "/actions/demo_test_compress",
        json={"action": "COMPRESS"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALLOWED"
    assert data["decision"] == "ALLOWED"
    assert "compressed successfully" in data["message"]
    assert "compression" in data

    # Verify audit endpoint exposes this action
    audit_resp = client.get("/audit")
    assert audit_resp.status_code == 200
    assert "log_archive.json" in audit_resp.text
    assert "COMPRESS" in audit_resp.text


def test_scenario_e_high_risk_delete_requires_approval():
    """Scenario E: High-risk DELETE (>10 GB) -> APPROVAL_REQUIRED."""
    token = _make_token("demo_admin", "Super-Admin")
    resp = client.post(
        "/actions/demo_test_highrisk",
        json={"action": "DELETE"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["status"] == "APPROVAL_REQUIRED"
    assert data["decision"] == "APPROVAL_REQUIRED"
    assert data["approval_required"] is True
    assert "dual approval" in data["reason"].lower()

    # Verify high-risk asset is NOT deleted
    asset = fetch_asset("demo_test_highrisk")
    assert asset is not None
    assert float(asset["size_gb"]) == 25.0
