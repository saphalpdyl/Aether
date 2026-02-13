"""Session event routes."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from db import query_oss


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: Optional[UUID] = Query(None),
    event_type: Optional[str] = Query(None),
):
    """List session events."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if session_id:
        conditions.append("session_id = %(session_id)s")
        params["session_id"] = str(session_id)
    if event_type:
        conditions.append("event_type = %(event_type)s")
        params["event_type"] = event_type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query_oss(
        f"""
        SELECT bng_id, bng_instance_id, seq, event_type, ts, session_id,
               nas_ip, circuit_id, remote_id, mac_address, ip_address, username,
               input_octets, output_octets, input_packets, output_packets,
               status, auth_state, terminate_cause
        FROM session_events
        {where}
        ORDER BY ts DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    return {"data": rows, "count": len(rows)}
