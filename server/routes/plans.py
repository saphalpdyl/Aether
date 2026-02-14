"""Plan management routes."""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from db import query_oss, execute_oss, execute_radius
from models import PlanCreate, PlanUpdate
from radius_helpers import sync_radius_group_for_plan, delete_radius_group_for_plan


router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("")
def list_plans(is_active: Optional[bool] = Query(None)):
    """List all plans, optionally filtered by active status."""
    if is_active is None:
        rows = query_oss("SELECT * FROM plans ORDER BY id")
    else:
        rows = query_oss(
            "SELECT * FROM plans WHERE is_active = %(is_active)s ORDER BY id",
            {"is_active": is_active},
        )
    return {"data": rows, "count": len(rows)}


@router.get("/{plan_id}")
def get_plan(plan_id: int):
    """Get a specific plan."""
    rows = query_oss("SELECT * FROM plans WHERE id = %(id)s", {"id": plan_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"data": rows[0]}


@router.post("", status_code=201)
def create_plan(body: PlanCreate):
    """Create a new plan."""
    existing = query_oss("SELECT id FROM plans WHERE name = %(name)s", {"name": body.name})
    if existing:
        raise HTTPException(status_code=409, detail="Plan already exists")

    try:
        sync_radius_group_for_plan(
            body.name,
            body.download_speed,
            body.upload_speed,
            body.download_burst,
            body.upload_burst,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to sync plan to RADIUS: {e}")

    execute_oss(
        """
        INSERT INTO plans (name, download_speed, upload_speed, download_burst, upload_burst, price, is_active)
        VALUES (%(name)s, %(download_speed)s, %(upload_speed)s, %(download_burst)s, %(upload_burst)s, %(price)s, %(is_active)s)
        """,
        {
            "name": body.name,
            "download_speed": body.download_speed,
            "upload_speed": body.upload_speed,
            "download_burst": body.download_burst,
            "upload_burst": body.upload_burst,
            "price": body.price,
            "is_active": body.is_active,
        },
    )
    rows = query_oss("SELECT * FROM plans WHERE name = %(name)s", {"name": body.name})
    return {"data": rows[0]}


@router.put("/{plan_id}")
def update_plan(plan_id: int, body: PlanUpdate):
    """Update an existing plan."""
    rows = query_oss("SELECT * FROM plans WHERE id = %(id)s", {"id": plan_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Plan not found")

    current = rows[0]
    new_name = body.name if body.name is not None else current["name"]
    new_download_speed = body.download_speed if body.download_speed is not None else int(current["download_speed"])
    new_upload_speed = body.upload_speed if body.upload_speed is not None else int(current["upload_speed"])
    new_download_burst = body.download_burst if body.download_burst is not None else int(current["download_burst"])
    new_upload_burst = body.upload_burst if body.upload_burst is not None else int(current["upload_burst"])

    if body.name is not None:
        name_conflict = query_oss(
            "SELECT id FROM plans WHERE name = %(name)s AND id <> %(id)s",
            {"name": body.name, "id": plan_id},
        )
        if name_conflict:
            raise HTTPException(status_code=409, detail="Plan name already exists")

    sets = ["updated_at = now()"]
    params: dict = {"id": plan_id}
    if body.name is not None:
        sets.append("name = %(name)s")
        params["name"] = body.name
    if body.download_speed is not None:
        sets.append("download_speed = %(download_speed)s")
        params["download_speed"] = body.download_speed
    if body.upload_speed is not None:
        sets.append("upload_speed = %(upload_speed)s")
        params["upload_speed"] = body.upload_speed
    if body.download_burst is not None:
        sets.append("download_burst = %(download_burst)s")
        params["download_burst"] = body.download_burst
    if body.upload_burst is not None:
        sets.append("upload_burst = %(upload_burst)s")
        params["upload_burst"] = body.upload_burst
    if body.price is not None:
        sets.append("price = %(price)s")
        params["price"] = body.price
    if body.is_active is not None:
        sets.append("is_active = %(is_active)s")
        params["is_active"] = body.is_active

    try:
        if current["name"] != new_name:
            execute_radius(
                "UPDATE radusergroup SET groupname = %(new_name)s WHERE groupname = %(old_name)s",
                {"new_name": new_name, "old_name": current["name"]},
            )
            execute_radius(
                "UPDATE radgroupreply SET groupname = %(new_name)s WHERE groupname = %(old_name)s",
                {"new_name": new_name, "old_name": current["name"]},
            )
            # Backward-compat rename for prior versions that wrote speeds into groupcheck.
            execute_radius(
                "UPDATE radgroupcheck SET groupname = %(new_name)s WHERE groupname = %(old_name)s",
                {"new_name": new_name, "old_name": current["name"]},
            )

        sync_radius_group_for_plan(
            new_name,
            new_download_speed,
            new_upload_speed,
            new_download_burst,
            new_upload_burst,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to sync plan to RADIUS: {e}")

    execute_oss(f"UPDATE plans SET {', '.join(sets)} WHERE id = %(id)s", params)

    updated = query_oss("SELECT * FROM plans WHERE id = %(id)s", {"id": plan_id})
    return {"data": updated[0]}


@router.delete("/{plan_id}")
def delete_plan(plan_id: int):
    """Delete a plan."""
    rows = query_oss("SELECT id, name FROM plans WHERE id = %(id)s", {"id": plan_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Plan not found")

    linked_services = query_oss(
        "SELECT count(*)::int AS count FROM services WHERE plan_id = %(id)s",
        {"id": plan_id},
    )
    if int(linked_services[0]["count"]) > 0:
        raise HTTPException(
            status_code=409,
            detail="Plan cannot be deleted while services are attached",
        )

    try:
        delete_radius_group_for_plan(rows[0]["name"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to delete plan from RADIUS: {e}")

    deleted = execute_oss("DELETE FROM plans WHERE id = %(id)s", {"id": plan_id})
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"ok": True}
