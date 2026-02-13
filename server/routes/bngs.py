"""BNG registry and health routes."""
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException

from db import query_oss


router = APIRouter(prefix="/api/bngs", tags=["bngs"])


@router.get("")
def list_bngs():
    """List all registered BNG instances."""
    rows = query_oss(
        """
        SELECT bng_id, bng_instance_id, first_seen, last_seen, is_alive,
               cpu_usage, mem_usage, mem_max
        FROM bng_registry
        ORDER BY bng_id
        """
    )
    return {"data": rows, "count": len(rows)}


@router.get("/{bng_id}")
def get_bng(bng_id: str):
    """Get BNG registry entry."""
    rows = query_oss(
        "SELECT * FROM bng_registry WHERE bng_id = %(bng_id)s",
        {"bng_id": bng_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="BNG not found")
    return {"data": rows[0]}


@router.get("/{bng_id}/health/{bng_instance_id}")
def get_bng_health(
    bng_id: str,
    bng_instance_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
):
    """Get BNG health event history."""
    rows = query_oss(
        """
        SELECT bng_id, bng_instance_id, ts, cpu_usage, mem_usage, mem_max
        FROM bng_health_events
        WHERE bng_id = %(bng_id)s AND bng_instance_id = %(bng_instance_id)s
        ORDER BY ts DESC
        LIMIT %(limit)s
        """,
        {"bng_id": bng_id, "bng_instance_id": str(bng_instance_id), "limit": limit},
    )
    return {"data": rows, "count": len(rows)}
