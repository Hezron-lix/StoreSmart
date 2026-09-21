"""Assets router: list and detail endpoints.

Moved from ingestion/api.py. Behavior is identical: the list endpoint
joins assets with AI predictions and returns {"success","count","data"};
the detail endpoint returns {"success","data"}.

Query logic lives in backend.db (currently a shim to ingestion.database;
Phase 5 ports it in).
"""

from fastapi import APIRouter, HTTPException

from backend.db import fetch_asset, fetch_assets

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def get_assets():
    """Return all assets joined with their latest AI predictions."""
    try:
        rows = fetch_assets()
        return {
            "success": True,
            "count": len(rows),
            "data": rows,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch assets: {exc}",
        )


@router.get("/{asset_id}")
def get_asset(asset_id: str):
    """Return a single asset by its asset_id."""
    try:
        asset = fetch_asset(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found.")
        return {
            "success": True,
            "data": asset,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch asset: {exc}",
        )
