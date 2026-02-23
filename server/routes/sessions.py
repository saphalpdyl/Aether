"""Session-related routes: active sessions, history, and events."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException

from db import query_oss
from radius_helpers import send_disconnect_request


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/active")
def list_active_sessions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List active IPoE sessions."""
    rows = query_oss(
        """
        SELECT * FROM sessions_active
        ORDER BY start_time DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"limit": limit, "offset": offset},
    )
    return {"data": rows, "count": len(rows)}


@router.get("/active/{session_id}")
def get_active_session(session_id: UUID):
    """Get details of an active session."""
    rows = query_oss(
        "SELECT * FROM sessions_active WHERE session_id = %(sid)s",
        {"sid": str(session_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"data": rows[0]}


@router.post("/active/{session_id}/disconnect")
def disconnect_active_session(session_id: UUID):
    """Send CoA Disconnect to an active session."""
    rows = query_oss(
        "SELECT session_id, nas_ip, username FROM sessions_active WHERE session_id = %(sid)s",
        {"sid": str(session_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")

    row = rows[0]
    return send_disconnect_request(
        nas_ip=row["nas_ip"],
        session_id=row["session_id"],
        username=row.get("username"),
    )


@router.get("/history")
def list_session_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_after: Optional[str] = Query(None, description="ISO timestamp filter: start_time >="),
    start_before: Optional[str] = Query(None, description="ISO timestamp filter: start_time <="),
):
    """List historical session records."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if start_after:
        conditions.append("start_time >= %(start_after)s")
        params["start_after"] = start_after
    if start_before:
        conditions.append("start_time <= %(start_before)s")
        params["start_before"] = start_before

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query_oss(
        f"""
        SELECT * FROM sessions_history
        {where}
        ORDER BY session_end DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    return {"data": rows, "count": len(rows)}


@router.get("/history/{session_id}")
def get_session_history(session_id: UUID):
    """Get details of a historical session."""
    rows = query_oss(
        "SELECT * FROM sessions_history WHERE session_id = %(sid)s",
        {"sid": str(session_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"data": rows[0]}
