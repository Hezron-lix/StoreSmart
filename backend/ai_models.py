from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from prophet import Prophet

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# ============================================================
# MODEL 1 — DEMO STORAGE HISTORY
# ============================================================

def generate_demo_history(
    days: int = 90,
    capacity_gb: float = 1000.0,
):
    start_date = (
        datetime.now()
        - timedelta(days=days - 1)
    )

    used = 500.0
    history = []

    for i in range(days):
        daily_growth = (
            3.1
            + ((i % 7) * 0.12)
        )

        used += daily_growth

        history.append(
            {
                "date": (
                    start_date
                    + timedelta(days=i)
                ).strftime("%Y-%m-%d"),

                "usedGb": round(used, 2),

                "capacityGb": capacity_gb,
            }
        )

    return history


# ============================================================
# MODEL 1 — PROPHET STORAGE FORECAST
# ============================================================

def forecast_storage(
    history: list[dict],
    capacity_gb: float = 1000.0,
    future_days: int = 90,
):
    if not history:
        history = generate_demo_history(
            days=90,
            capacity_gb=capacity_gb,
        )

    rows = []

    for record in history:
        date_value = (
            record.get("date")
            or record.get("usage_date")
        )

        used_value = (
            record.get("usedGb")
            or record.get("total_used_gb")
        )

        if (
            date_value is None
            or used_value is None
        ):
            continue

        rows.append(
            {
                "ds": pd.to_datetime(
                    date_value
                ),

                "y": float(
                    used_value
                ),
            }
        )

    if len(rows) < 2:
        raise ValueError(
            "At least two historical storage records are required."
        )

    dataframe = (
        pd.DataFrame(rows)
        .drop_duplicates(
            subset=["ds"]
        )
        .sort_values("ds")
    )

    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
        seasonality_mode="additive",
    )

    model.fit(
        dataframe
    )

    future = (
        model.make_future_dataframe(
            periods=future_days,
            freq="D",
        )
    )

    predicted = (
        model.predict(
            future
        )
    )

    last_history_date = (
        dataframe["ds"].max()
    )

    future_only = (
        predicted[
            predicted["ds"]
            > last_history_date
        ]
        .copy()
    )

    forecast = []
    runway_to_zero = None

    for _, row in future_only.iterrows():
        prediction = max(
            0.0,
            float(
                row["yhat"]
            ),
        )

        date_text = (
            row["ds"]
            .strftime(
                "%Y-%m-%d"
            )
        )

        forecast.append(
            {
                "date": date_text,

                "usedGb": round(
                    prediction,
                    2,
                ),

                "predictedGb": round(
                    prediction,
                    2,
                ),

                "capacityGb":
                    capacity_gb,
            }
        )

        if (
            runway_to_zero is None
            and prediction >= capacity_gb
        ):
            runway_to_zero = (
                date_text
            )

    # --------------------------------------------------------
    # Estimate crossing if Prophet forecast window
    # does not yet reach capacity.
    # --------------------------------------------------------

    if runway_to_zero is None:
        first_y = float(
            dataframe.iloc[0]["y"]
        )

        last_y = float(
            dataframe.iloc[-1]["y"]
        )

        total_days = max(
            1,
            (
                dataframe.iloc[-1]["ds"]
                - dataframe.iloc[0]["ds"]
            ).days,
        )

        daily_growth = (
            last_y - first_y
        ) / total_days

        if daily_growth > 0:
            remaining = (
                capacity_gb
                - last_y
            )

            estimated_days = max(
                0,
                int(
                    remaining
                    / daily_growth
                ),
            )

            runway_to_zero = (
                (
                    last_history_date
                    + timedelta(
                        days=estimated_days
                    )
                )
                .strftime(
                    "%Y-%m-%d"
                )
            )

    return {
        "forecast":
            forecast,

        "capacityGb":
            capacity_gb,

        "runwayToZeroDate":
            runway_to_zero,

        "model":
            "Prophet",

        "historyPoints":
            len(dataframe),

        "forecastPoints":
            len(forecast),
    }


# ============================================================
# MODEL 2 — LINEAR REGRESSION
# COMPRESSION SAVINGS PREDICTOR
# ============================================================

_compression_model = None


def train_compression_model():
    """
    Hackathon demo training set.

    Features:
        entropy_score
        file_extension
        size_gb

    Target:
        predicted compression savings percentage

    This can later be replaced with a supplied/training CSV
    without changing the API contract.
    """

    global _compression_model

    training_data = pd.DataFrame(
        [
            {
                "entropy_score": 0.10,
                "file_extension": ".txt",
                "size_gb": 0.05,
                "savings_percent": 88,
            },
            {
                "entropy_score": 0.18,
                "file_extension": ".txt",
                "size_gb": 1.00,
                "savings_percent": 82,
            },
            {
                "entropy_score": 0.25,
                "file_extension": ".txt",
                "size_gb": 5.00,
                "savings_percent": 76,
            },

            {
                "entropy_score": 0.18,
                "file_extension": ".csv",
                "size_gb": 0.10,
                "savings_percent": 81,
            },
            {
                "entropy_score": 0.28,
                "file_extension": ".csv",
                "size_gb": 1.50,
                "savings_percent": 73,
            },
            {
                "entropy_score": 0.38,
                "file_extension": ".csv",
                "size_gb": 4.00,
                "savings_percent": 64,
            },

            {
                "entropy_score": 0.20,
                "file_extension": ".json",
                "size_gb": 0.10,
                "savings_percent": 79,
            },
            {
                "entropy_score": 0.30,
                "file_extension": ".json",
                "size_gb": 1.00,
                "savings_percent": 71,
            },
            {
                "entropy_score": 0.42,
                "file_extension": ".json",
                "size_gb": 5.00,
                "savings_percent": 61,
            },

            {
                "entropy_score": 0.18,
                "file_extension": ".yaml",
                "size_gb": 0.05,
                "savings_percent": 82,
            },
            {
                "entropy_score": 0.30,
                "file_extension": ".yaml",
                "size_gb": 1.00,
                "savings_percent": 72,
            },
            {
                "entropy_score": 0.40,
                "file_extension": ".yaml",
                "size_gb": 3.00,
                "savings_percent": 63,
            },

            {
                "entropy_score": 0.55,
                "file_extension": ".log",
                "size_gb": 2.00,
                "savings_percent": 48,
            },

            {
                "entropy_score": 0.65,
                "file_extension": ".pdf",
                "size_gb": 2.00,
                "savings_percent": 32,
            },

            {
                "entropy_score": 0.78,
                "file_extension": ".jpg",
                "size_gb": 3.00,
                "savings_percent": 16,
            },

            {
                "entropy_score": 0.88,
                "file_extension": ".zip",
                "size_gb": 5.00,
                "savings_percent": 7,
            },
        ]
    )

    features = training_data[
        [
            "entropy_score",
            "file_extension",
            "size_gb",
        ]
    ]

    target = training_data[
        "savings_percent"
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "extension",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
                ["file_extension"],
            ),
        ],
        remainder="passthrough",
    )

    model = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "regression",
                LinearRegression(),
            ),
        ]
    )

    model.fit(
        features,
        target,
    )

    _compression_model = model

    return model


def predict_compression_savings(
    entropy_score: float,
    file_extension: str,
    size_gb: float,
):
    global _compression_model

    if _compression_model is None:
        train_compression_model()

    entropy_score = float(
        entropy_score
    )

    size_gb = max(
        0.0,
        float(size_gb),
    )

    extension = (
        str(
            file_extension
            or ""
        )
        .lower()
        .strip()
    )

    if (
        extension
        and not extension.startswith(".")
    ):
        extension = (
            "."
            + extension
        )

    input_data = pd.DataFrame(
        [
            {
                "entropy_score":
                    entropy_score,

                "file_extension":
                    extension,

                "size_gb":
                    size_gb,
            }
        ]
    )

    prediction = float(
        _compression_model.predict(
            input_data
        )[0]
    )

    # Keep prediction physically sensible.
    prediction = max(
        0.0,
        min(
            95.0,
            prediction,
        ),
    )

    savings_percent = round(
        prediction,
        2,
    )

    savings_gb = round(
        size_gb
        * (
            savings_percent
            / 100
        ),
        4,
    )

    return {
        "model":
            "Linear Regression",

        "entropy_score":
            round(
                entropy_score,
                4,
            ),

        "file_extension":
            extension,

        "size_gb":
            round(
                size_gb,
                4,
            ),

        "savings_percent":
            savings_percent,

        "savings_gb":
            savings_gb,
    }


# ============================================================
# EXECUTIVE HEALTH SCORE
# ============================================================

def calculate_health_score(
    used_storage: float,
    total_storage: float,
    average_compression_percent: float,
    days_to_full: float,
):
    if total_storage <= 0:
        raise ValueError(
            "Total storage must be greater than zero."
        )

    capacity = (
        1
        - (
            used_storage
            / total_storage
        )
    )

    efficiency = (
        average_compression_percent
        / 100
    )

    stability = (
        1
        - (
            days_to_full
            / 365
        )
    )

    capacity = max(
        0.0,
        min(
            1.0,
            capacity,
        ),
    )

    efficiency = max(
        0.0,
        min(
            1.0,
            efficiency,
        ),
    )

    stability = max(
        0.0,
        min(
            1.0,
            stability,
        ),
    )

    score = (
        capacity * 0.4
        + efficiency * 0.3
        + stability * 0.3
    )

    if score >= 0.90:
        grade = "A"
    elif score >= 0.80:
        grade = "B"
    elif score >= 0.70:
        grade = "C"
    elif score >= 0.60:
        grade = "D"
    else:
        grade = "F"

    return {
        "score":
            round(
                score,
                3,
            ),

        "grade":
            grade,

        "components": {
            "capacity":
                round(
                    capacity,
                    3,
                ),

            "efficiency":
                round(
                    efficiency,
                    3,
                ),

            "stability":
                round(
                    stability,
                    3,
                ),
        },
    }


# ============================================================
# PRIORITY SCORE
# ============================================================

def calculate_priority_score(
    risk: float,
    savings: float,
):
    risk = max(
        0.0,
        min(
            100.0,
            float(risk),
        ),
    )

    savings = max(
        0.0,
        min(
            100.0,
            float(savings),
        ),
    )

    return round(
        (
            risk * 0.6
        )
        +
        (
            savings * 0.4
        ),
        2,
    )

__all__ = [
    "generate_demo_history",
    "forecast_storage",
    "train_compression_model",
    "predict_compression_savings",
    "calculate_health_score",
    "calculate_priority_score",
]
