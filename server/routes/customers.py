"""Customer management routes."""
from fastapi import APIRouter, HTTPException

from db import query_oss, execute_oss
from models import CustomerCreate, CustomerUpdate


router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/listing")
def list_customers_listing():
    """List all customers with session statistics."""
    rows = query_oss("""
        SELECT
            c.id, c.name, c.email, c.phone,
            c.street, c.city, c.zip_code, c.state,
            c.created_at, c.updated_at,
            COALESCE(act.active_count, 0)  AS active_sessions,
            COALESCE(hist.recent_count, 0) AS recent_sessions,
            svc.service_count,
            CASE
                WHEN COALESCE(act.active_count, 0) > 0 THEN 'online'
                WHEN COALESCE(hist.recent_count, 0) > 0 THEN 'recent'
                WHEN svc.service_count = 0 THEN 'new'
                ELSE 'offline'
            END AS status
        FROM customers c
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS service_count
            FROM services s WHERE s.customer_id = c.id
        ) svc ON true
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS active_count
            FROM services s
            JOIN sessions_active sa ON 
                -- remote_id is the router name in the new identity model
                sa.username = (
                    SELECT ar.bng_id || '/' || s.remote_id || '/' || s.circuit_id
                    FROM access_routers ar
                    WHERE ar.router_name = s.remote_id
                )
            WHERE s.customer_id = c.id
        ) act ON true
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS recent_count
            FROM services s
            JOIN sessions_history sh ON 
                -- remote_id is the router name in the new identity model
                sh.username = (
                    SELECT ar.bng_id || '/' || s.remote_id || '/' || s.circuit_id
                    FROM access_routers ar
                    WHERE ar.router_name = s.remote_id
                )
            WHERE s.customer_id = c.id AND sh.session_end > now() - interval '24 hours'
        ) hist ON true
        ORDER BY c.name
    """)
    return {"data": rows, "count": len(rows)}


@router.get("/{customer_id}/sessions")
def list_customer_sessions(customer_id: int):
    """List active sessions for a customer."""
    rows = query_oss("""
        SELECT sa.*
        FROM services s
        JOIN sessions_active sa ON
            sa.username = (
                SELECT ar.bng_id || '/' || s.remote_id || '/' || s.circuit_id
                FROM access_routers ar
                WHERE ar.router_name = s.remote_id
            )
        WHERE s.customer_id = %(customer_id)s
        ORDER BY sa.start_time DESC
    """, {"customer_id": customer_id})
    return {"data": rows, "count": len(rows)}


@router.get("/{customer_id}/sessions/history")
def list_customer_sessions_history(customer_id: int):
    """List historical sessions for a customer."""
    rows = query_oss("""
        SELECT sh.*
        FROM services s
        JOIN sessions_history sh ON
            sh.username = (
                SELECT ar.bng_id || '/' || s.remote_id || '/' || s.circuit_id
                FROM access_routers ar
                WHERE ar.router_name = s.remote_id
            )
        WHERE s.customer_id = %(customer_id)s
        ORDER BY sh.session_end DESC
    """, {"customer_id": customer_id})
    return {"data": rows, "count": len(rows)}


@router.get("/{customer_id}/events")
def list_customer_events(customer_id: int):
    """List session events for a customer."""
    rows = query_oss("""
        SELECT se.*
        FROM services s
        JOIN session_events se ON
            se.username = (
                SELECT ar.bng_id || '/' || s.remote_id || '/' || s.circuit_id
                FROM access_routers ar
                WHERE ar.router_name = s.remote_id
            )
        WHERE s.customer_id = %(customer_id)s
        ORDER BY se.ts DESC
    """, {"customer_id": customer_id})
    return {"data": rows, "count": len(rows)}


@router.get("")
def list_customers():
    """List all customers."""
    rows = query_oss("SELECT * FROM customers ORDER BY id")
    return {"data": rows, "count": len(rows)}


@router.get("/{customer_id}")
def get_customer(customer_id: int):
    """Get a specific customer."""
    rows = query_oss("SELECT * FROM customers WHERE id = %(id)s", {"id": customer_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"data": rows[0]}


@router.post("", status_code=201)
def create_customer(body: CustomerCreate):
    """Create a new customer."""
    created = query_oss(
        """
        INSERT INTO customers (name, email, phone, street, city, zip_code, state)
        VALUES (%(name)s, %(email)s, %(phone)s, %(street)s, %(city)s, %(zip_code)s, %(state)s)
        RETURNING *
        """,
        {
            "name": body.name,
            "email": body.email,
            "phone": body.phone,
            "street": body.street,
            "city": body.city,
            "zip_code": body.zip_code,
            "state": body.state,
        },
    )
    return {"data": created[0]}


@router.put("/{customer_id}")
def update_customer(customer_id: int, body: CustomerUpdate):
    """Update an existing customer."""
    rows = query_oss("SELECT id FROM customers WHERE id = %(id)s", {"id": customer_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Customer not found")

    sets = ["updated_at = now()"]
    params: dict = {"id": customer_id}

    if body.name is not None:
        sets.append("name = %(name)s")
        params["name"] = body.name
    if body.email is not None:
        sets.append("email = %(email)s")
        params["email"] = body.email
    if body.phone is not None:
        sets.append("phone = %(phone)s")
        params["phone"] = body.phone
    if body.street is not None:
        sets.append("street = %(street)s")
        params["street"] = body.street
    if body.city is not None:
        sets.append("city = %(city)s")
        params["city"] = body.city
    if body.zip_code is not None:
        sets.append("zip_code = %(zip_code)s")
        params["zip_code"] = body.zip_code
    if body.state is not None:
        sets.append("state = %(state)s")
        params["state"] = body.state

    execute_oss(f"UPDATE customers SET {', '.join(sets)} WHERE id = %(id)s", params)
    updated = query_oss("SELECT * FROM customers WHERE id = %(id)s", {"id": customer_id})
    return {"data": updated[0]}


@router.delete("/{customer_id}")
def delete_customer(customer_id: int):
    """Delete a customer."""
    linked_services = query_oss(
        "SELECT count(*)::int AS count FROM services WHERE customer_id = %(id)s",
        {"id": customer_id},
    )
    if int(linked_services[0]["count"]) > 0:
        raise HTTPException(
            status_code=409,
            detail="Customer cannot be deleted while services are attached",
        )

    deleted = execute_oss("DELETE FROM customers WHERE id = %(id)s", {"id": customer_id})
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"ok": True}
