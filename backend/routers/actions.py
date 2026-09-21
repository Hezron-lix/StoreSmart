"""Actions router: DELETE and COMPRESS with governance gate.

Moved from ingestion/api.py. Governance evaluation runs before any DB
mutation. Audit rows are written to backend.audit, NOT to
ingestion.governance's copy.
"""

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from backend.audit import write_audit_record
from backend.db import (
    compress_asset,
    delete_asset,
    fetch_asset,
    insert_action,
)
from backend.governance import evaluate_action
from backend.models import ActionRequest
from backend.security import get_current_user

router = APIRouter(prefix="/actions", tags=["actions"])


@router.post(
    "/{asset_id}"
)
def execute_asset_action(
    asset_id: str,

    request: ActionRequest,

    authorization: str | None =
        Header(
            default=None
        ),
):

    # --------------------------------------------------------
    # 1. AUTHENTICATE USER
    # --------------------------------------------------------
    user = get_current_user(authorization)

    # --------------------------------------------------------
    # 2. NORMALIZE ACTION
    # --------------------------------------------------------
    action = str(request.action).strip().upper()
    if action not in {"DELETE", "COMPRESS"}:
        raise HTTPException(
            status_code=400,
            detail="Action must be DELETE or COMPRESS.",
        )

    # --------------------------------------------------------
    # 3. FETCH ASSET
    # --------------------------------------------------------
    asset = fetch_asset(asset_id)
    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found.",
        )

    policy_id = asset.get("policy_id")
    file_name = asset.get("file_name") or asset_id

    # --------------------------------------------------------
    # 4. GOVERNANCE EVALUATION (BEFORE ANY MUTATION)
    # --------------------------------------------------------
    evaluation = evaluate_action(
        asset=asset,
        action=action,
        user=user,
        bypass_approval=False,
    )

    # --------------------------------------------------------
    # 5. BLOCKED OR APPROVAL REQUIRED -> AUDIT AND STOP
    # --------------------------------------------------------
    if not evaluation["allowed"]:
        decision = evaluation["decision"]  # "BLOCKED" or "APPROVAL_REQUIRED"
        outcome = "blocked" if decision == "BLOCKED" else "approval_required"
        effective_policy_id = evaluation.get("policy_id") or policy_id or ""

        # Audit to MySQL
        try:
            insert_action(
                asset_id=asset_id,
                user_name=user["name"],
                role=user["role"],
                action_type=action,
                policy_id=effective_policy_id,
                outcome=outcome,
                reason=evaluation["reason"],
            )
        except Exception:
            pass

        # Audit to immutable CSV log
        try:
            write_audit_record(
                user=user["name"],
                role=user["role"],
                action=action,
                file=file_name,
                policy_id=effective_policy_id,
                outcome=outcome,
            )
        except Exception:
            pass

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "status": evaluation["status"],
                "decision": decision,
                "asset_id": asset_id,
                "assetId": asset_id,
                "action": action,
                "reason": evaluation["reason"],
                "policy_id": effective_policy_id,
                "risk_level": evaluation["risk_level"],
                "approval_required": evaluation["approval_required"],
                "governance": {
                    "allowed": False,
                    "policyId": effective_policy_id,
                    "rule": evaluation["rule"],
                    "reason": evaluation["reason"],
                },
                "message": evaluation["reason"],
            },
        )

    # --------------------------------------------------------
    # 6. ACTION ALLOWED -> EXECUTE DATABASE CHANGE
    # --------------------------------------------------------
    try:
        if action == "DELETE":
            deleted = delete_asset(asset_id)
            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail="Asset could not be deleted.",
                )

            # Audit to MySQL
            insert_action(
                asset_id=asset_id,
                user_name=user["name"],
                role=user["role"],
                action_type="DELETE",
                policy_id=policy_id,
                outcome="success",
                reason=evaluation["reason"],
            )

            # Audit to CSV
            write_audit_record(
                user=user["name"],
                role=user["role"],
                action="DELETE",
                file=file_name,
                policy_id=policy_id,
                outcome="success",
            )

            return {
                "success": True,
                "status": "ALLOWED",
                "decision": "ALLOWED",
                "action": "DELETE",
                "asset_id": asset_id,
                "assetId": asset_id,
                "reason": evaluation["reason"],
                "policy_id": policy_id,
                "risk_level": evaluation["risk_level"],
                "approval_required": False,
                "governance": {
                    "allowed": True,
                    "policyId": policy_id,
                    "rule": evaluation["rule"],
                    "reason": evaluation["reason"],
                },
                "message": f"{asset_id} deleted successfully. {evaluation['reason']}",
            }

        # COMPRESS
        compression = compress_asset(asset_id)
        if compression is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found for compression.",
            )

        # Audit to MySQL
        insert_action(
            asset_id=asset_id,
            user_name=user["name"],
            role=user["role"],
            action_type="COMPRESS",
            policy_id=policy_id,
            outcome="success",
            reason=f"Asset compressed. Saved {compression['saved_gb']} GB.",
        )

        # Audit to CSV
        write_audit_record(
            user=user["name"],
            role=user["role"],
            action="COMPRESS",
            file=file_name,
            policy_id=policy_id,
            outcome="success",
        )

        return {
            "success": True,
            "status": "ALLOWED",
            "decision": "ALLOWED",
            "action": "COMPRESS",
            "asset_id": asset_id,
            "assetId": asset_id,
            "compression": compression,
            "reason": evaluation["reason"],
            "policy_id": policy_id,
            "risk_level": evaluation["risk_level"],
            "approval_required": False,
            "governance": {
                "allowed": True,
                "policyId": policy_id,
                "rule": evaluation["rule"],
                "reason": evaluation["reason"],
            },
            "message": f"{asset_id} compressed successfully. Saved {compression['saved_gb']} GB.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to execute action: {exc}",
        )
