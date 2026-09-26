"""Assets router: list and detail endpoints.

Moved from ingestion/api.py. Behavior is identical: the list endpoint
joins assets with AI predictions and returns {"success","count","data"};
the detail endpoint returns {"success","data"}.

Query logic lives in backend.db (currently a shim to ingestion.database;
Phase 5 ports it in).
"""

import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.db import (
    fetch_asset,
    fetch_assets,
    fetch_asset_format_counts,
    fetch_paginated_assets,
)

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def get_assets(
    source_type: Optional[str] = Query(None, description="Optional format filter: json, csv, txt, yaml"),
    page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Items per page"),
):
    """Return assets joined with their latest AI predictions.

    If page/limit/source_type are provided, returns a paginated slice + format counts.
    Otherwise returns all assets (preserving full backward compatibility).
    """
    try:
        if page is not None or limit is not None or source_type is not None:
            p = page or 1
            l = limit or 50
            format_counts = fetch_asset_format_counts()
            clean_source = source_type.strip().lower() if source_type else None
            total = (
                format_counts.get(clean_source, 0)
                if clean_source
                else sum(format_counts.values())
            )
            rows, _ = fetch_paginated_assets(source_type=clean_source, page=p, limit=l, total=total)
            total_pages = math.ceil(total / l) if total > 0 else 1
            return {
                "success": True,
                "count": len(rows),
                "total": total,
                "total_pages": total_pages,
                "page": p,
                "limit": l,
                "format_counts": format_counts,
                "data": rows,
            }

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
