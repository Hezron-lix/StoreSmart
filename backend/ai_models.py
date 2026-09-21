"""AI model shim.

Re-exports forecasting and scoring helpers from the legacy
`ingestion.ai_models` module. Phase 5 ports the implementations; routers
do not need to change then.
"""

from ingestion.ai_models import (  # TODO(phase5): port impl
    calculate_health_score,
    calculate_priority_score,
    forecast_storage,
    generate_demo_history,
    predict_compression_savings,
)

__all__ = [
    "generate_demo_history",
    "forecast_storage",
    "predict_compression_savings",
    "calculate_health_score",
    "calculate_priority_score",
]
