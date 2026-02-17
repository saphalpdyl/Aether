"""Service management routes."""
from typing import Optional, Literal

from fastapi import APIRouter, Query, HTTPException

from db import query_oss, execute_oss
from models import ServiceCreate, ServiceUpdate
from radius_helpers import (
    service_username,
    upsert_radius_usergroup,
    upsert_radius_usercheck,
    delete_radius_usergroup,
    delete_radius_usercheck,
    send_disconnect_request,
)


router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("")
def list_services(
    customer_id: Optional[int] = Query(None),
    plan_id: Optional[int] = Query(None),
    status: Optional[Literal["ACTIVE", "SUSPENDED", "TERMINATED"]] = Query(None),
):
    """List all services with optional filters."""
    conditions = []
    params: dict = {}

    if customer_id is not None:
        conditions.append("s.customer_id = %(customer_id)s")
        params["customer_id"] = customer_id
    if plan_id is not None:
        conditions.append("s.plan_id = %(plan_id)s")
        params["plan_id"] = plan_id
    if status is not None:
        conditions.append("s.status = %(status)s")
        params["status"] = status

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query_oss(
        f"""
        SELECT s.*, c.name AS customer_name, p.name AS plan_name
        FROM services s
        JOIN customers c ON c.id = s.customer_id
        JOIN plans p ON p.id = s.plan_id
        {where}
        ORDER BY s.id
        """,
        params,
    )
    return {"data": rows, "count": len(rows)}


@router.get("/{service_id}")
def get_service(service_id: int):
    """Get a specific service."""
    rows = query_oss(
        """
        SELECT s.*, c.name AS customer_name, p.name AS plan_name
        FROM services s
        JOIN customers c ON c.id = s.customer_id
        JOIN plans p ON p.id = s.plan_id
        WHERE s.id = %(id)s
        """,
        {"id": service_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"data": rows[0]}


@router.post("", status_code=201)
def create_service(body: ServiceCreate):
    """Create a new service."""
    customer_exists = query_oss("SELECT id FROM customers WHERE id = %(id)s", {"id": body.customer_id})
    if not customer_exists:
        raise HTTPException(status_code=404, detail="Customer not found")

    plan_rows = query_oss("SELECT id, name FROM plans WHERE id = %(id)s", {"id": body.plan_id})
    if not plan_rows:
        raise HTTPException(status_code=404, detail="Plan not found")

    duplicate = query_oss(
        "SELECT id FROM services WHERE circuit_id = %(circuit_id)s AND remote_id = %(remote_id)s",
        {"circuit_id": body.circuit_id, "remote_id": body.remote_id},
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Service with this circuit_id/remote_id already exists")

    username = service_username(body.circuit_id, body.remote_id, body.relay_id)
    try:
        upsert_radius_usergroup(username, plan_rows[0]["name"])
        upsert_radius_usercheck(username)
    except Exception as e:
        print(f"Error syncing service to RADIUS: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to sync service to RADIUS: {e}")

    created = query_oss(
        """
        INSERT INTO services (customer_id, plan_id, circuit_id, remote_id, status)
        VALUES (%(customer_id)s, %(plan_id)s, %(circuit_id)s, %(remote_id)s, %(status)s)
        RETURNING id
        """,
        {
            "customer_id": body.customer_id,
            "plan_id": body.plan_id,
            "circuit_id": body.circuit_id,
            "remote_id": body.remote_id,
            "status": body.status,
        },
    )

    rows = query_oss(
        """
        SELECT s.*, c.name AS customer_name, p.name AS plan_name
        FROM services s
        JOIN customers c ON c.id = s.customer_id
        JOIN plans p ON p.id = s.plan_id
        WHERE s.id = %(id)s
        """,
        {"id": created[0]["id"]},
    )
    return {"data": rows[0]}


@router.put("/{service_id}")
def update_service(service_id: int, body: ServiceUpdate):
    """Update an existing service."""
    rows = query_oss("SELECT * FROM services WHERE id = %(id)s", {"id": service_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Service not found")

    current = rows[0]
    new_customer_id = body.customer_id if body.customer_id is not None else int(current["customer_id"])
    new_plan_id = body.plan_id if body.plan_id is not None else int(current["plan_id"])
    new_circuit_id = body.circuit_id if body.circuit_id is not None else current["circuit_id"]
    new_remote_id = body.remote_id if body.remote_id is not None else current["remote_id"]

    customer_exists = query_oss("SELECT id FROM customers WHERE id = %(id)s", {"id": new_customer_id})
    if not customer_exists:
        raise HTTPException(status_code=404, detail="Customer not found")

    plan_rows = query_oss("SELECT id, name FROM plans WHERE id = %(id)s", {"id": new_plan_id})
    if not plan_rows:
        raise HTTPException(status_code=404, detail="Plan not found")

    duplicate = query_oss(
        """
        SELECT id FROM services
        WHERE circuit_id = %(circuit_id)s
          AND remote_id = %(remote_id)s
          AND id <> %(id)s
        """,
        {"circuit_id": new_circuit_id, "remote_id": new_remote_id, "id": service_id},
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Service with this circuit_id/remote_id already exists")

    old_username = service_username(current["circuit_id"], current["remote_id"])
    new_username = service_username(new_circuit_id, new_remote_id, body.relay_id)
    new_status = body.status if body.status is not None else current["status"]

    try:
        if new_status in ("SUSPENDED", "TERMINATED"):
            # Remove RADIUS entries so the subscriber can no longer authenticate
            delete_radius_usergroup(new_username)
            delete_radius_usercheck(new_username)
            if old_username != new_username:
                delete_radius_usergroup(old_username)
                delete_radius_usercheck(old_username)
        else:
            # ACTIVE — ensure RADIUS entries exist
            if old_username != new_username:
                delete_radius_usergroup(old_username)
                delete_radius_usercheck(old_username)
            upsert_radius_usergroup(new_username, plan_rows[0]["name"])
            upsert_radius_usercheck(new_username)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to sync service to RADIUS: {e}")

    sets = ["updated_at = now()"]
    params: dict = {"id": service_id}

    if body.customer_id is not None:
        sets.append("customer_id = %(customer_id)s")
        params["customer_id"] = body.customer_id
    if body.plan_id is not None:
        sets.append("plan_id = %(plan_id)s")
        params["plan_id"] = body.plan_id
    if body.circuit_id is not None:
        sets.append("circuit_id = %(circuit_id)s")
        params["circuit_id"] = body.circuit_id
    if body.remote_id is not None:
        sets.append("remote_id = %(remote_id)s")
        params["remote_id"] = body.remote_id
    if body.status is not None:
        sets.append("status = %(status)s")
        params["status"] = body.status

    execute_oss(f"UPDATE services SET {', '.join(sets)} WHERE id = %(id)s", params)

    updated = query_oss(
        """
        SELECT s.*, c.name AS customer_name, p.name AS plan_name
        FROM services s
        JOIN customers c ON c.id = s.customer_id
        JOIN plans p ON p.id = s.plan_id
        WHERE s.id = %(id)s
        """,
        {"id": service_id},
    )
    return {"data": updated[0]}


@router.delete("/{service_id}")
def delete_service(service_id: int):
    """Delete a service."""
    rows = query_oss("SELECT id, circuit_id, remote_id FROM services WHERE id = %(id)s", {"id": service_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Service not found")

    username = service_username(rows[0]["circuit_id"], rows[0]["remote_id"])
    try:
        delete_radius_usergroup(username)
        delete_radius_usercheck(username)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to delete service from RADIUS: {e}")

    deleted = execute_oss("DELETE FROM services WHERE id = %(id)s", {"id": service_id})
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"ok": True}


@router.post("/{service_id}/disconnect")
def disconnect_service_session(service_id: int):
    """Find active session for a service and send CoA disconnect."""
    svc = query_oss("SELECT circuit_id, remote_id FROM services WHERE id = %(id)s", {"id": service_id})
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    circuit_id = svc[0]["circuit_id"]
    remote_id = svc[0]["remote_id"]

    # Backward compatibility: older rows sometimes stored full username in circuit_id
    # as bng-id/remote-id/circuit-id. Keep new "1/0/x" circuit IDs intact.
    if circuit_id.startswith("bng-") and circuit_id.count("/") >= 2:
        parts = circuit_id.split("/", 2)
        circuit_id = parts[2]
        if not remote_id:
            remote_id = parts[1]

    rows = query_oss(
        """
        SELECT session_id, nas_ip, username
        FROM sessions_active
        WHERE circuit_id = %(circuit_id)s AND remote_id = %(remote_id)s
        """,
        {"circuit_id": circuit_id, "remote_id": remote_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No active session found for this service")

    row = rows[0]
    return send_disconnect_request(
        nas_ip=row["nas_ip"],
        session_id=row["session_id"],
        username=row.get("username"),
    )
