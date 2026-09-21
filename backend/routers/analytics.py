"""Analytics router: storage forecast, compression predictions,
health score, priority score.

Moved from ingestion/api.py. Behavior is identical.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.ai_models import (
    calculate_health_score,
    calculate_priority_score,
    forecast_storage,
    generate_demo_history,
    predict_compression_savings,
)
from backend.db import (
    fetch_assets,
    fetch_compression_insights,
    fetch_storage_history,
    upsert_prediction,
)
from backend.models import (
    CompressionBatchRequest,
    CompressionRequest,
    ForecastRequest,
    HealthScoreRequest,
    PriorityScoreRequest,
)

router = APIRouter(prefix="", tags=["analytics"])


# ============================================================
# STORAGE HISTORY
# ============================================================

@router.get(
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

@router.post(
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

@router.post(
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

@router.post(
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

@router.get(
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

@router.post(
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

@router.post(
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
