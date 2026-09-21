"""StorageWise AI - Governance Rule Engine.

Evaluates declarative governance policies before actions are executed:
1. RBAC Check (Viewer read-only vs Super-Admin)
2. SHA-256 Checksum Integrity Check
3. Rule 1: Retention Policy (Blocks deletion before retention period expires)
4. Rule 2: Priority Protection (Blocks compression of legal/protected archives)
5. Rule 3: Policy-over-AI Conflict Override
6. High-Risk Deletion Dual Approval Guardrail
"""

from __future__ import annotations

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ============================================================
# DETERMINISTIC POLICY MATRIX FALLBACK
# ============================================================
DETERMINISTIC_POLICIES = {
    "POL-FIN-7Y": {
        "retention_days": 2555,
        "description": "Financial records – keep 7 years",
        "category": "financial",
    },
    "POL-HR-5Y": {
        "retention_days": 1825,
        "description": "HR personnel files – keep 5 years",
        "category": "hr",
    },
    "POL-ENG-3Y": {
        "retention_days": 1095,
        "description": "Engineering CAD – keep 3 years",
        "category": "engineering",
    },
    "POL-OPS-2Y": {
        "retention_days": 730,
        "description": "Operations logs – keep 2 years",
        "category": "operations",
    },
    "POL-MKT-3Y": {
        "retention_days": 1095,
        "description": "Marketing assets – keep 3 years",
        "category": "marketing",
    },
    "POL-IT-5Y": {
        "retention_days": 1825,
        "description": "IT backups – keep 5 years",
        "category": "it",
    },
    "POL-LGL-7Y": {
        "retention_days": 2555,
        "description": "Legal documents – keep 7 years",
        "category": "legal",
    },
    "POL-ANL-1Y": {
        "retention_days": 365,
        "description": "Analytics raw events – keep 1 year",
        "category": "analytics",
    },
    "POL-SAL-2Y": {
        "retention_days": 730,
        "description": "Sales records – keep 2 years",
        "category": "sales",
    },
    "POL-SUP-1Y": {
        "retention_days": 365,
        "description": "Support tickets – keep 1 year",
        "category": "support",
    },
}

_policies_cache: Optional[Dict[str, Dict[str, Any]]] = None


def load_retention_policies() -> Dict[str, Dict[str, Any]]:
    """Load retention policies from Retention_Policy_Matrix.xlsx or fallback."""
    global _policies_cache
    if _policies_cache is not None:
        return _policies_cache

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidate_paths = [
        os.path.join(base_dir, "reference", "Retention_Policy_Matrix.xlsx"),
        os.path.join(base_dir, "data", "Retention_Policy_Matrix.xlsx"),
        os.path.join(base_dir, "BackEnd", "data", "Retention_Policy_Matrix.xlsx"),
        r"C:\Users\admin\Downloads\UC 6 data4d2c67a\Sampledata1\Sampledata1\reference\Retention_Policy_Matrix.xlsx",
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            try:
                policies = _parse_xlsx_policies(path)
                if policies:
                    _policies_cache = policies
                    return _policies_cache
            except Exception:
                pass

    # Deterministic fallback
    _policies_cache = dict(DETERMINISTIC_POLICIES)
    return _policies_cache


def _parse_xlsx_policies(file_path: str) -> Dict[str, Dict[str, Any]]:
    """Parse Retention_Policy_Matrix.xlsx using python stdlib (zipfile + xml)."""
    with zipfile.ZipFile(file_path, "r") as z:
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss_tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared_strings = [
                elem.text or ""
                for elem in ss_tree.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
            ]

        sheet_tree = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows = []
        for r in sheet_tree.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
            cells = []
            for c in r.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                t = c.get("t")
                v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                txt = v.text if v is not None else ""
                if t == "s" and txt and txt.isdigit():
                    idx = int(txt)
                    if idx < len(shared_strings):
                        txt = shared_strings[idx]
                cells.append(txt.strip())
            if cells:
                rows.append(cells)

    if not rows or len(rows) < 2:
        return {}

    header = [h.lower().replace(" ", "_") for h in rows[0]]
    policy_id_idx = 0
    days_idx = 1
    desc_idx = 2

    for i, col in enumerate(header):
        if "policy" in col:
            policy_id_idx = i
        elif "retention" in col or "day" in col or "period" in col:
            days_idx = i
        elif "desc" in col:
            desc_idx = i

    parsed = {}
    for row in rows[1:]:
        if len(row) <= policy_id_idx:
            continue
        pid = row[policy_id_idx]
        if not pid or not pid.startswith("POL-"):
            continue

        retention_days = 365
        if len(row) > days_idx:
            try:
                retention_days = int(float(row[days_idx]))
            except ValueError:
                retention_days = 365

        desc = row[desc_idx] if len(row) > desc_idx else ""
        parsed[pid] = {
            "retention_days": retention_days,
            "description": desc,
            "category": pid.split("-")[1].lower() if "-" in pid else "general",
        }

    return parsed if parsed else dict(DETERMINISTIC_POLICIES)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def parse_datetime(value: Any) -> Optional[datetime]:
    """Parse various timestamp shapes into UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    val_str = str(value).strip()
    # Normalize ISO format
    if val_str.endswith("Z"):
        val_str = val_str[:-1] + "+00:00"

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val_str[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(val_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def calculate_file_age_days(created_ts: Any) -> float:
    """Calculate age of file in fractional days."""
    created_dt = parse_datetime(created_ts)
    if not created_dt:
        return 0.0
    now = datetime.now(timezone.utc)
    delta = now - created_dt
    return max(0.0, delta.total_seconds() / 86400.0)


def is_valid_sha256(checksum: Any) -> bool:
    """Check if string is a valid 64-character hex SHA-256 string."""
    if not checksum or not isinstance(checksum, str):
        return False
    return bool(re.match(r"^[0-9a-fA-F]{64}$", checksum.strip()))


def is_legal_or_protected(asset: Dict[str, Any]) -> bool:
    """Check whether an asset has legal or protected status."""
    tags = asset.get("tags") or []
    if isinstance(tags, str):
        import json
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    if not isinstance(tags, list):
        tags = []

    normalized_tags = [str(t).strip().lower() for t in tags]
    if "legal" in normalized_tags or "protected" in normalized_tags or "confidential" in normalized_tags:
        return True

    policy_id = str(asset.get("policy_id") or "").upper()
    if "LGL" in policy_id or "LEGAL" in policy_id:
        return True

    dept = str(asset.get("owner_dept") or "").strip().lower()
    if dept == "legal":
        return True

    return False


# ============================================================
# GOVERNANCE EVALUATION ENGINE
# ============================================================

def evaluate_action(
    asset: Dict[str, Any],
    action: str,
    user: Dict[str, Any],
    bypass_approval: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate all governance rules before executing an action.

    Returns dict with:
      allowed: bool
      status: "ALLOWED" | "BLOCKED" | "APPROVAL_REQUIRED"
      decision: "ALLOWED" | "BLOCKED" | "APPROVAL_REQUIRED"
      rule: str
      policy_id: str | None
      reason: str
      risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
      approval_required: bool
    """
    action_norm = str(action or "").strip().upper()
    role = str(user.get("role") or "").strip()
    is_super_admin = role.lower() == "super-admin"
    policy_id = asset.get("policy_id")
    policies = load_retention_policies()
    policy_meta = policies.get(policy_id, {})

    # ------------------------------------------------------------
    # 1. RBAC CHECK
    # ------------------------------------------------------------
    if not is_super_admin:
        return {
            "allowed": False,
            "status": "BLOCKED",
            "decision": "BLOCKED",
            "rule": "RBAC",
            "policy_id": "RBAC",
            "reason": "Permission denied: Viewer role is read-only. Only Super-Admin can execute actions.",
            "risk_level": "HIGH",
            "approval_required": False,
        }

    # ------------------------------------------------------------
    # 2. INTEGRITY / CHECKSUM GUARDRAIL
    # ------------------------------------------------------------
    checksum = asset.get("checksum") or asset.get("checksum_sha256")
    if not is_valid_sha256(checksum):
        return {
            "allowed": False,
            "status": "BLOCKED",
            "decision": "BLOCKED",
            "rule": "CHECKSUM_INTEGRITY",
            "policy_id": "CHECKSUM-INTEGRITY",
            "reason": "Action blocked: checksum/integrity validation failed.",
            "risk_level": "CRITICAL",
            "approval_required": False,
        }

    # ------------------------------------------------------------
    # 3. RULE 2: PRIORITY PROTECTION (LEGAL FILES CANNOT BE COMPRESSED)
    # ------------------------------------------------------------
    if action_norm == "COMPRESS":
        if is_legal_or_protected(asset):
            return {
                "allowed": False,
                "status": "BLOCKED",
                "decision": "BLOCKED",
                "rule": "PRIORITY",
                "policy_id": policy_id or "POL-LGL-7Y",
                "reason": "Priority rule: Legal files are protected from compression.",
                "risk_level": "HIGH",
                "approval_required": False,
            }

    # ------------------------------------------------------------
    # 4. RULE 1 & RULE 3: RETENTION & AI-CONFLICT OVERRIDE (DELETE)
    # ------------------------------------------------------------
    if action_norm == "DELETE":
        # Check if asset is protected legal document (cannot be deleted without legal clearance)
        if is_legal_or_protected(asset):
            return {
                "allowed": False,
                "status": "BLOCKED",
                "decision": "BLOCKED",
                "rule": "PRIORITY",
                "policy_id": policy_id or "POL-LGL-7Y",
                "reason": "Priority rule: Legal archives are protected from deletion.",
                "risk_level": "HIGH",
                "approval_required": False,
            }

        retention_days = policy_meta.get("retention_days", 0)
        age_days = calculate_file_age_days(asset.get("created_ts"))
        age_years = age_days / 365.25
        required_years = retention_days / 365.25

        if retention_days > 0 and age_days < retention_days:
            # Policy overrides any AI recommendation to delete
            reason = (
                f"Retention active: File is {age_years:.1f} years old. "
                f"Retention requires {round(required_years)} years ({retention_days} days). "
                f"Policy {policy_id} overrides AI delete recommendation."
            )
            return {
                "allowed": False,
                "status": "BLOCKED",
                "decision": "BLOCKED",
                "rule": "RETENTION",
                "policy_id": policy_id,
                "reason": reason,
                "risk_level": "HIGH",
                "approval_required": False,
            }

        # --------------------------------------------------------
        # 5. HIGH-RISK DELETION DUAL-APPROVAL GUARDRAIL
        # --------------------------------------------------------
        size_gb = float(asset.get("size_gb") or 0.0)
        dept = str(asset.get("owner_dept") or "").strip().lower()
        tags = [str(t).lower() for t in (asset.get("tags") or [])]

        is_high_risk = (
            size_gb >= 10.0
            or dept in ["executive", "infrastructure"]
            or "critical" in tags
            or "core" in tags
            or asset.get("high_risk") is True
        )

        if is_high_risk and not bypass_approval:
            return {
                "allowed": False,
                "status": "APPROVAL_REQUIRED",
                "decision": "APPROVAL_REQUIRED",
                "rule": "HIGH_RISK_APPROVAL",
                "policy_id": policy_id or "POL-DUAL-APPROVAL",
                "reason": f"High-risk deletion requires dual approval (size {size_gb:.2f} GB >= 10.0 GB threshold).",
                "risk_level": "HIGH",
                "approval_required": True,
            }

    # ------------------------------------------------------------
    # 6. ALL GOVERNANCE CHECKS PASSED -> ALLOWED
    # ------------------------------------------------------------
    return {
        "allowed": True,
        "status": "ALLOWED",
        "decision": "ALLOWED",
        "rule": "GOVERNANCE_PASSED",
        "policy_id": policy_id,
        "reason": f"Action permitted: {action_norm} approved by policy.",
        "risk_level": "LOW",
        "approval_required": False,
    }


# ============================================================
# AUDIT LOGGING (CSV & INTEGRATION)
# ============================================================

def _get_audit_log_path() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "audit.csv")


def write_audit_record(
    user: str | None = None,
    role: str | None = None,
    action: str | None = None,
    file: str | None = None,
    policy_id: Optional[str] = None,
    outcome: str | None = None,
    **kwargs: Any,
) -> None:
    """Append one record to logs/audit.csv matching the canonical audit log structure."""
    csv_path = _get_audit_log_path()
    file_exists = os.path.exists(csv_path)

    # Alias support for kwargs
    user = user or kwargs.get("user_id") or kwargs.get("user_name") or "unknown"
    role = role or kwargs.get("user_role") or "Viewer"
    action = action or kwargs.get("action_type") or "UNKNOWN"
    file = file or kwargs.get("asset_id") or kwargs.get("file_name") or "unknown"
    outcome = outcome or kwargs.get("decision") or "unknown"
    policy_id = policy_id or kwargs.get("policyId") or ""

    def clean_csv(val: Any) -> str:
        if val is None:
            return ""
        s = str(val).replace('"', '""')
        return f'"{s}"'

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    row = [
        timestamp,
        user,
        role,
        action,
        file,
        policy_id,
        outcome,
    ]
    row_str = ",".join(clean_csv(item) for item in row) + "\n"

    mode = "a" if file_exists else "w"
    with open(csv_path, mode, encoding="utf-8") as f:
        if not file_exists:
            f.write("timestamp,user,role,action,file,policy_id,outcome\n")
        f.write(row_str)


def get_audit_csv_content() -> str:
    """Return raw CSV string of the audit log."""
    csv_path = _get_audit_log_path()
    if not os.path.exists(csv_path):
        header = "timestamp,user,role,action,file,policy_id,outcome\n"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(header)
        return header

    with open(csv_path, "r", encoding="utf-8") as f:
        return f.read()

