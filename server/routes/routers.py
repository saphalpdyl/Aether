"""Access router routes."""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from db import query_oss, execute_oss
from models import RouterCreate, RouterUpdate


router = APIRouter(prefix="/api/routers", tags=["routers"])


@router.get("")
def list_routers(bng_id: Optional[str] = Query(None)):
    """List all access routers, optionally filtered by BNG ID."""
    if bng_id:
        rows = query_oss(
            """
            SELECT router_name, giaddr, bng_id,
                   is_alive, last_seen, last_ping,
                   active_subscribers, created_at, updated_at
            FROM access_routers
            WHERE bng_id = %(bng_id)s
            ORDER BY router_name
            """,
            {"bng_id": bng_id},
        )
    else:
        rows = query_oss(
            """
            SELECT router_name, giaddr, bng_id,
                   is_alive, last_seen, last_ping,
                   active_subscribers, created_at, updated_at
            FROM access_routers
            ORDER BY router_name
            """
        )
    return {"data": rows, "count": len(rows)}


@router.post("", status_code=201)
def create_router(body: RouterCreate):
    """Register a new access router."""
    existing = query_oss(
        "SELECT router_name FROM access_routers WHERE router_name = %(name)s",
        {"name": body.router_name},
    )
    if existing:
        raise HTTPException(status_code=409, detail="Router already exists")
    execute_oss(
        """
        INSERT INTO access_routers (router_name, giaddr, bng_id)
        VALUES (%(router_name)s, %(giaddr)s::inet, %(bng_id)s)
        """,
        {"router_name": body.router_name, "giaddr": body.giaddr, "bng_id": body.bng_id},
    )
    rows = query_oss(
        "SELECT * FROM access_routers WHERE router_name = %(name)s",
        {"name": body.router_name},
    )
    return {"data": rows[0]}


@router.put("/{router_name}")
def update_router(router_name: str, body: RouterUpdate):
    """Update an access router."""
    existing = query_oss(
        "SELECT router_name FROM access_routers WHERE router_name = %(name)s",
        {"name": router_name},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Router not found")

    sets = ["updated_at = now()"]
    params: dict = {"name": router_name}
    if body.giaddr is not None:
        sets.append("giaddr = %(giaddr)s::inet")
        params["giaddr"] = body.giaddr
    if body.bng_id is not None:
        sets.append("bng_id = %(bng_id)s")
        params["bng_id"] = body.bng_id

    execute_oss(
        f"UPDATE access_routers SET {', '.join(sets)} WHERE router_name = %(name)s",
        params,
    )
    rows = query_oss(
        "SELECT * FROM access_routers WHERE router_name = %(name)s",
        {"name": router_name},
    )
    return {"data": rows[0]}


@router.delete("/{router_name}")
def delete_router(router_name: str):
    """Delete an access router."""
    rowcount = execute_oss(
        "DELETE FROM access_routers WHERE router_name = %(name)s",
        {"name": router_name},
    )
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Router not found")
    return {"ok": True}
