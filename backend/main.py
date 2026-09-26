"""StoreSmart FastAPI entrypoint.

Registers all routers. Business logic lives inside each router module.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import actions, analytics, assets, audit, auth, ingest

app = FastAPI(
    title="StoreSmart",
    version="0.1.0",
    description="Storage governance, AI forecasting, and policy enforcement.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, ingest, assets, analytics, actions, audit):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "storesmart"}
