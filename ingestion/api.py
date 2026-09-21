from __future__ import annotations

import os
import tempfile
from pathlib import Path

import bcrypt
import jwt

from fastapi import (
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.responses import (
    JSONResponse,
    PlainTextResponse,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from pydantic import (
    BaseModel,
    Field,
)

from ingestion.ai_models import (
    calculate_health_score,
    calculate_priority_score,
    forecast_storage,
    generate_demo_history,
    predict_compression_savings,
)

from ingestion.database import (
    compress_asset,
    delete_asset,
    fetch_asset,
    fetch_assets,
    fetch_compression_insights,
    fetch_storage_history,
    get_connection,
    import_assets,
    insert_action,
    upsert_prediction,
)

from ingestion.governance import (
    evaluate_action,
    get_audit_csv_content,
    write_audit_record,
)

from ingestion.normalize import (
    deduplicate,
    normalize_records,
    to_canonical,
    validate_records,
)

from ingestion.parsers import (
    parse_csv_file,
    parse_json_file,
    parse_txt_file,
    parse_yaml_file,
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="StorageWise AI - FastAPI Backend",
    version="2.2.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# INGESTION PARSERS
# ============================================================

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


# ============================================================
# REQUEST MODELS
# ============================================================

class ForecastRequest(
    BaseModel
):
    history: list[dict] = Field(
        default_factory=list
    )


class HealthScoreRequest(
    BaseModel
):
    usedStorage: float

    totalStorage: float

    averageCompressionPercent: float

    daysToFull: float


class PriorityScoreRequest(
    BaseModel
):
    risk: float

    savings: float


class CompressionRequest(
    BaseModel
):
    entropy_score: float

    file_extension: str

    size_gb: float


class CompressionBatchRequest(
    BaseModel
):
    limit: int = 100

    source_type: str | None = None


class ActionRequest(
    BaseModel
):
    action: str


# ============================================================
# RBAC / JWT
# ============================================================

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "storagewise_dev_secret_key_2026_minimum_32_bytes_token",
)


class SignupRequest(BaseModel):
    username: str
    password: str
    role: str = "Viewer"


class LoginRequest(BaseModel):
    username: str
    password: str


def get_current_user(authorization: str | None) -> dict:
    """Extract authenticated user and role from Bearer token."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header.",
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Login session expired.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid login token.",
        )

    nested_user = payload.get("user") or {}
    role = payload.get("role") or nested_user.get("role") or "Viewer"
    username = (
        payload.get("username")
        or payload.get("name")
        or nested_user.get("username")
        or nested_user.get("name")
        or "user"
    )

    return {
        "name": username,
        "role": role,
    }


def get_super_admin(authorization: str | None) -> dict:
    """Backwards-compatible helper requiring Super-Admin."""
    user = get_current_user(authorization)
    if str(user.get("role") or "").strip().lower() != "super-admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super-Admin can execute actions.",
        )
    return user


# ============================================================
# AUTHENTICATION ENDPOINTS
# ============================================================

@app.post("/auth/signup")
@app.post("/api/auth/signup")
def auth_signup(req: SignupRequest):
    username = req.username.strip()
    role = req.role.strip()
    if not username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password required")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="User already exists")

        pw_hash = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, pw_hash, role),
        )
        conn.commit()
        user_id = cursor.lastrowid
        user_obj = {"id": user_id, "username": username, "role": role}
        token = jwt.encode(user_obj, JWT_SECRET, algorithm="HS256")
        return {"message": "Account created", "user": user_obj, "token": token}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Signup failed: {exc}")
    finally:
        if conn:
            conn.close()


@app.post("/auth/login")
@app.post("/api/auth/login")
def auth_login(req: LoginRequest):
    username = req.username.strip()
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        stored_hash = str(row["password_hash"]).encode("utf-8")
        if not bcrypt.checkpw(req.password.encode("utf-8"), stored_hash):
            raise HTTPException(status_code=401, detail="Incorrect password")

        user_obj = {"id": row["id"], "username": row["username"], "role": row["role"]}
        token = jwt.encode(user_obj, JWT_SECRET, algorithm="HS256")
        return {"message": "Login successful", "user": user_obj, "token": token}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}")
    finally:
        if conn:
            conn.close()



# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health"
)
def health():

    return {
        "success":
            True,

        "service":
            "StorageWise FastAPI Backend",

        "status":
            "running",

        "aiModels": [
            "Prophet",
            "Linear Regression",
        ],
    }


# ============================================================
# GET ALL ASSETS
# ============================================================

@app.get(
    "/assets"
)
def get_assets():

    try:

        rows = (
            fetch_assets()
        )


        return {
            "success":
                True,

            "count":
                len(
                    rows
                ),

            "data":
                rows,
        }


    except Exception as exc:

        raise HTTPException(
            status_code=500,

            detail=(
                "Unable to fetch assets: "
                f"{exc}"
            ),
        )


# ============================================================
# GET SINGLE ASSET
# ============================================================

@app.get(
    "/assets/{asset_id}"
)
def get_asset(
    asset_id: str,
):

    try:

        asset = fetch_asset(
            asset_id
        )


        if not asset:

            raise HTTPException(
                status_code=404,

                detail=(
                    "Asset not found."
                ),
            )


        return {
            "success":
                True,

            "data":
                asset,
        }


    except HTTPException:
        raise


    except Exception as exc:

        raise HTTPException(
            status_code=500,

            detail=(
                "Unable to fetch asset: "
                f"{exc}"
            ),
        )


# ============================================================
# STORAGE HISTORY
# ============================================================

@app.get(
    "/storage-history"
)
def get_storage_history():

    try:

        rows = (
            fetch_storage_history()
        )


        # ----------------------------------------------------
        # USE MYSQL DATA
        # ----------------------------------------------------

        if rows:

            return {
                "success":
                    True,

                "source":
                    "database",

                "data":
                    rows,
            }


        # ----------------------------------------------------
        # FALLBACK DEMO HISTORY
        # ----------------------------------------------------

        demo_history = (
            generate_demo_history(
                days=
                    90,

                capacity_gb=
                    1000.0,
            )
        )


        data = [

            {
                "usage_date":
                    row[
                        "date"
                    ],

                "total_used_gb":
                    row[
                        "usedGb"
                    ],

                "total_capacity_gb":
                    row[
                        "capacityGb"
                    ],
            }

            for row
            in demo_history
        ]


        return {
            "success":
                True,

            "source":
                "simulated",

            "data":
                data,
        }


    except Exception as exc:

        raise HTTPException(
            status_code=500,

            detail=(
                "Unable to fetch "
                "storage history: "
                f"{exc}"
            ),
        )


# ============================================================
# MODEL 1 — PROPHET STORAGE FORECAST
# ============================================================

@app.post(
    "/forecast-storage"
)
def get_storage_forecast(
    request: ForecastRequest,
):

    try:

        history = (
            request.history
        )


        if not history:

            history = (
                generate_demo_history(
                    days=
                        90,

                    capacity_gb=
                        1000.0,
                )
            )


        normalized_history = []


        for row in history:

            date_value = (
                row.get(
                    "date"
                )

                or row.get(
                    "usage_date"
                )
            )


            used_value = (
                row.get(
                    "usedGb"
                )

                or row.get(
                    "total_used_gb"
                )
            )


            if (
                date_value is None
                or used_value is None
            ):
                continue


            normalized_history.append(
                {
                    "date":
                        str(
                            date_value
                        ),

                    "usedGb":
                        float(
                            used_value
                        ),
                }
            )


        # ----------------------------------------------------
        # FALLBACK IF INPUT HISTORY INVALID
        # ----------------------------------------------------

        if (
            len(
                normalized_history
            )
            < 2
        ):

            normalized_history = (
                generate_demo_history(
                    days=
                        90,

                    capacity_gb=
                        1000.0,
                )
            )


        result = (
            forecast_storage(
                history=
                    normalized_history,

                capacity_gb=
                    1000.0,

                future_days=
                    90,
            )
        )


        return {
            "success":
                True,

            "forecast":
                result,
        }


    except Exception as exc:

        raise HTTPException(
            status_code=500,

            detail=(
                "Forecast failed: "
                f"{exc}"
            ),
        )


# ============================================================
# MODEL 2 — SINGLE LINEAR REGRESSION PREDICTION
# ============================================================

@app.post(
    "/predict-compression"
)
def predict_compression(
    request: CompressionRequest,
):

    try:

        prediction = (
            predict_compression_savings(
                entropy_score=
                    request.entropy_score,

                file_extension=
                    request.file_extension,

                size_gb=
                    request.size_gb,
            )
        )


        return {
            "success":
                True,

            "prediction":
                prediction,
        }


    except Exception as exc:

        raise HTTPException(
            status_code=400,

            detail=(
                "Compression prediction "
                "failed: "
                f"{exc}"
            ),
        )


# ============================================================
# MODEL 2 — BATCH RUN + STORE PREDICTIONS
# ============================================================

@app.post(
    "/run-compression-ai"
)
def run_compression_ai(
    request: CompressionBatchRequest,
):

    try:

        # ----------------------------------------------------
        # FETCH ALL ASSETS
        # ----------------------------------------------------

        assets = (
            fetch_assets()
        )


        # ----------------------------------------------------
        # OPTIONAL SOURCE FILTER
        # ----------------------------------------------------

        if request.source_type:

            requested_source = (
                request.source_type
                .strip()
                .lower()
            )


            allowed_sources = {
                "json",
                "csv",
                "txt",
                "yaml",
            }


            if (
                requested_source
                not in allowed_sources
            ):

                raise HTTPException(
                    status_code=400,

                    detail=(
                        "source_type must be "
                        "one of: json, csv, "
                        "txt, yaml"
                    ),
                )


            assets = [

                asset

                for asset
                in assets

                if (
                    str(
                        asset.get(
                            "source_type"
                        )
                        or ""
                    )
                    .lower()
                    == requested_source
                )
            ]


        # ----------------------------------------------------
        # LIMIT
        # ----------------------------------------------------

        limit = max(
            1,

            min(
                int(
                    request.limit
                ),

                12000,
            ),
        )


        selected_assets = (
            assets[
                :limit
            ]
        )


        # ----------------------------------------------------
        # EMPTY RESULT
        # ----------------------------------------------------

        if not selected_assets:

            return {
                "success":
                    True,

                "model":
                    "Linear Regression",

                "sourceType":
                    request.source_type,

                "processed":
                    0,

                "riskScore":
                    0,

                "averageSavingsPercent":
                    0,

                "potentialSavingsGb":
                    0,

                "topPredictions":
                    [],
            }


        # ----------------------------------------------------
        # STORAGE RISK
        # ----------------------------------------------------

        history = (
            fetch_storage_history()
        )


        if history:

            latest = (
                history[
                    -1
                ]
            )


            used = float(
                latest.get(
                    "total_used_gb"
                )
                or 0
            )


            capacity = float(
                latest.get(
                    "total_capacity_gb"
                )
                or 1000
            )


        else:

            demo_history = (
                generate_demo_history(
                    days=
                        90,

                    capacity_gb=
                        1000.0,
                )
            )


            latest = (
                demo_history[
                    -1
                ]
            )


            used = float(
                latest[
                    "usedGb"
                ]
            )


            capacity = float(
                latest[
                    "capacityGb"
                ]
            )


        if capacity <= 0:

            capacity = (
                1000.0
            )


        risk = min(
            100.0,

            max(
                0.0,

                (
                    used
                    / capacity
                )
                * 100,
            ),
        )


        # ----------------------------------------------------
        # RUN MODEL
        # ----------------------------------------------------

        results = []


        for asset in selected_assets:

            asset_id = (
                asset.get(
                    "asset_id"
                )
            )


            if not asset_id:
                continue


            # ------------------------------------------------
            # SIZE
            # ------------------------------------------------

            size_gb = float(
                asset.get(
                    "size_gb"
                )
                or 0
            )


            # ------------------------------------------------
            # EXTENSION
            # ------------------------------------------------

            extension = (
                asset.get(
                    "file_extension"
                )
            )


            if not extension:

                file_name = (
                    asset.get(
                        "file_name"
                    )
                )


                if file_name:

                    extension = (
                        Path(
                            file_name
                        )
                        .suffix
                        .lower()
                    )


            if not extension:

                source_type = (
                    asset.get(
                        "source_type"
                    )
                    or ""
                )


                if source_type:

                    extension = (
                        "."
                        + source_type
                    )


            if not extension:

                extension = (
                    ".unknown"
                )


            # ------------------------------------------------
            # ENTROPY
            # ------------------------------------------------

            stored_entropy = (
                asset.get(
                    "entropy_score"
                )
            )


            if (
                stored_entropy
                is None
            ):

                entropy = (
                    0.45
                )

                entropy_source = (
                    "demo-fallback"
                )


            else:

                entropy = float(
                    stored_entropy
                )

                entropy_source = (
                    "asset"
                )


            # ------------------------------------------------
            # PREDICT
            # ------------------------------------------------

            prediction = (
                predict_compression_savings(
                    entropy_score=
                        entropy,

                    file_extension=
                        extension,

                    size_gb=
                        size_gb,
                )
            )


            savings_percent = float(
                prediction[
                    "savings_percent"
                ]
            )


            savings_gb = float(
                prediction[
                    "savings_gb"
                ]
            )


            # ------------------------------------------------
            # PRIORITY
            # ------------------------------------------------

            priority_score = (
                calculate_priority_score(
                    risk=
                        risk,

                    savings=
                        savings_percent,
                )
            )


            # ------------------------------------------------
            # SAVE MYSQL PREDICTION
            # ------------------------------------------------

            upsert_prediction(
                asset_id=
                    asset_id,

                savings_percent=
                    savings_percent,

                savings_gb=
                    savings_gb,

                priority_score=
                    priority_score,
            )


            results.append(
                {
                    "asset_id":
                        asset_id,

                    "source_type":
                        asset.get(
                            "source_type"
                        ),

                    "file_extension":
                        extension,

                    "entropy_score":
                        entropy,

                    "entropy_source":
                        entropy_source,

                    "size_gb":
                        size_gb,

                    "savings_percent":
                        savings_percent,

                    "savings_gb":
                        savings_gb,

                    "risk_score":
                        round(
                            risk,
                            2,
                        ),

                    "priority_score":
                        priority_score,
                }
            )


        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        results.sort(
            key=lambda item:
                item[
                    "savings_percent"
                ],

            reverse=True,
        )


        # ----------------------------------------------------
        # AVERAGE SAVINGS
        # ----------------------------------------------------

        if results:

            average_savings = round(
                sum(
                    item[
                        "savings_percent"
                    ]

                    for item
                    in results
                )
                / len(
                    results
                ),

                2,
            )


        else:

            average_savings = (
                0.0
            )


        # ----------------------------------------------------
        # TOTAL SAVINGS
        # ----------------------------------------------------

        potential_savings_gb = round(

            sum(
                item[
                    "savings_gb"
                ]

                for item
                in results
            ),

            4,
        )


        return {
            "success":
                True,

            "model":
                "Linear Regression",

            "sourceType":
                request.source_type
                or "all",

            "processed":
                len(
                    results
                ),

            "riskScore":
                round(
                    risk,
                    2,
                ),

            "averageSavingsPercent":
                average_savings,

            "potentialSavingsGb":
                potential_savings_gb,

            "topPredictions":
                results[
                    :10
                ],
        }


    except HTTPException:
        raise


    except Exception as exc:

        raise HTTPException(
            status_code=500,

            detail=(
                "Compression AI failed: "
                f"{exc}"
            ),
        )


# ============================================================
# MODEL 2 — STORED INSIGHTS
# ============================================================

@app.get(
    "/compression-insights"
)
def get_compression_insights():

    try:

        insights = (
            fetch_compression_insights(
                limit=
                    10
            )
        )


        return {
            "success":
                True,

            "model":
                "Linear Regression",

            "predictionCount":
                insights[
                    "prediction_count"
                ],

            "averageSavingsPercent":
                round(
                    insights[
                        "average_savings_percent"
                    ],

                    2,
                ),

            "potentialSavingsGb":
                round(
                    insights[
                        "total_savings_gb"
                    ],

                    4,
                ),

            "topPredictions":
                insights[
                    "top_predictions"
                ],
        }


    except Exception as exc:

        raise HTTPException(
            status_code=500,

            detail=(
                "Unable to load "
                "compression insights: "
                f"{exc}"
            ),
        )


# ============================================================
# EXECUTIVE HEALTH SCORE
# ============================================================

@app.post(
    "/health-score"
)
def get_health_score(
    request: HealthScoreRequest,
):

    try:

        result = (
            calculate_health_score(
                used_storage=
                    request.usedStorage,

                total_storage=
                    request.totalStorage,

                average_compression_percent=
                    request.averageCompressionPercent,

                days_to_full=
                    request.daysToFull,
            )
        )


        return result


    except Exception as exc:

        raise HTTPException(
            status_code=400,

            detail=(
                "Health score failed: "
                f"{exc}"
            ),
        )


# ============================================================
# PRIORITY SCORE
# ============================================================

@app.post(
    "/priority-score"
)
def get_priority_score(
    request: PriorityScoreRequest,
):

    try:

        priority_score = (
            calculate_priority_score(
                risk=
                    request.risk,

                savings=
                    request.savings,
            )
        )


        return {
            "success":
                True,

            "risk":
                request.risk,

            "savings":
                request.savings,

            "priorityScore":
                priority_score,
        }


    except Exception as exc:

        raise HTTPException(
            status_code=400,

            detail=(
                "Priority score failed: "
                f"{exc}"
            ),
        )


# ============================================================
# ACTION CENTER — REAL DELETE / COMPRESS
# ============================================================

@app.post(
    "/actions/{asset_id}"
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


# ============================================================
# AUDIT LOG ENDPOINT
# ============================================================

@app.get("/audit", response_class=PlainTextResponse)
def get_audit_log_endpoint():
    return get_audit_csv_content()



# ============================================================
# INGESTION
# ============================================================

@app.post(
    "/ingest",
    response_model=None,
)
async def ingest(

    json_file:
        UploadFile | None =
        File(
            default=None
        ),

    csv_file:
        UploadFile | None =
        File(
            default=None
        ),

    txt_file:
        UploadFile | None =
        File(
            default=None
        ),

    yaml_file:
        UploadFile | None =
        File(
            default=None
        ),
):

    # --------------------------------------------------------
    # COLLECT UPLOADED FILES
    # --------------------------------------------------------

    uploaded_files = [

        file

        for file
        in [
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
        "json":
            0,

        "txt":
            0,

        "csv":
            0,

        "yaml":
            0,
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
            Path(
                filename
            )
            .suffix
            .lower()
        )


        if (
            extension
            not in PARSERS
        ):

            raise HTTPException(
                status_code=400,

                detail=(
                    "Unsupported file "
                    f"format: {filename}"
                ),
            )


        source_type, parser = (
            PARSERS[
                extension
            ]
        )


        temp_path = None


        try:

            # ------------------------------------------------
            # READ FILE
            # ------------------------------------------------

            content = (
                await uploaded_file.read()
            )


            if not content:

                parse_errors.append(
                    {
                        "stage":
                            "upload",

                        "source_type":
                            source_type,

                        "filename":
                            filename,

                        "error":
                            "Uploaded file is empty.",
                    }
                )

                continue


            # ------------------------------------------------
            # WRITE TEMP FILE
            # ------------------------------------------------

            with tempfile.NamedTemporaryFile(
                mode=
                    "wb",

                delete=
                    False,

                suffix=
                    extension,
            ) as temp_file:

                temp_file.write(
                    content
                )


                temp_path = (
                    temp_file.name
                )


            # ------------------------------------------------
            # PARSE
            # ------------------------------------------------

            records, errors = (
                parser(
                    temp_path
                )
            )


            counts[
                source_type
            ] += len(
                records
            )


            raw_records.extend(
                records
            )


            parse_errors.extend(
                errors
            )


        except Exception as exc:

            parse_errors.append(
                {
                    "stage":
                        "parse",

                    "source_type":
                        source_type,

                    "filename":
                        filename,

                    "error":
                        str(
                            exc
                        ),
                }
            )


        finally:

            # ------------------------------------------------
            # CLEAN TEMP FILE
            # ------------------------------------------------

            if (
                temp_path
                and os.path.exists(
                    temp_path
                )
            ):

                try:

                    os.remove(
                        temp_path
                    )


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
            ) = (
                normalize_records(
                    raw_records
                )
            )


        except Exception as exc:

            normalize_errors.append(
                {
                    "stage":
                        "normalize",

                    "error":
                        str(
                            exc
                        ),
                }
            )


    all_errors = (
        parse_errors
        + normalize_errors
    )


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
            ) = (
                validate_records(
                    normalized_records
                )
            )


        except Exception as exc:

            all_errors.append(
                {
                    "stage":
                        "validate",

                    "error":
                        str(
                            exc
                        ),
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
            ) = (
                deduplicate(
                    valid_records
                )
            )


        except Exception as exc:

            all_errors.append(
                {
                    "stage":
                        "deduplicate",

                    "error":
                        str(
                            exc
                        ),
                }
            )


    # ========================================================
    # CANONICAL OUTPUT
    # ========================================================

    canonical_records = []


    for record in unique_records:

        try:

            canonical_records.append(
                to_canonical(
                    record
                )
            )


        except Exception as exc:

            all_errors.append(
                {
                    "stage":
                        "canonical",

                    "asset_id":
                        record.get(
                            "asset_id"
                        ),

                    "error":
                        str(
                            exc
                        ),
                }
            )


    # ========================================================
    # MYSQL IMPORT
    # ========================================================

    database_import = None


    if canonical_records:

        try:

            database_import = (
                import_assets(
                    canonical_records
                )
            )


        except Exception as exc:

            all_errors.append(
                {
                    "stage":
                        "database_import",

                    "error":
                        str(
                            exc
                        ),
                }
            )


            database_import = {
                "success":
                    False,

                "error":
                    str(
                        exc
                    ),
            }


    # ========================================================
    # SUMMARY
    # ========================================================

    summary = {
        "records_by_source":
            counts,

        "stats": {

            "total_parsed":
                len(
                    raw_records
                ),

            "normalized":
                len(
                    normalized_records
                ),

            "valid":
                len(
                    valid_records
                ),

            "invalid":
                len(
                    invalid_records
                ),

            "duplicates":
                len(
                    duplicate_records
                ),

            "errors":
                len(
                    all_errors
                ),

            "canonical_records":
                len(
                    canonical_records
                ),
        },
    }


    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "success":
            True,

        "message":
            "Ingestion completed successfully.",

        "summary":
            summary,

        "database_import":
            database_import,

        "records_preview":
            canonical_records[
                :10
            ],

        "invalid_records_preview":
            invalid_records[
                :10
            ],

        "errors_preview":
            all_errors[
                :10
            ],
    }