"""Access router routes."""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from db import query_oss, execute_oss
from models import RouterCreate, RouterUpdate


router = APIRouter(prefix="/api/routers", tags=["routers"])


def _has_total_interfaces_column() -> bool:
    rows = query_oss(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'access_routers'
          AND column_name = 'total_interfaces'
        LIMIT 1
        """
    )
    return bool(rows)


def _subscriber_ports(total_interfaces: int) -> list[str]:
    # Last interface is uplink, so subscriber-facing ports are eth1..eth(N-1)
    return [f"eth{i}" for i in range(1, max(2, int(total_interfaces)))]


def _port_to_circuit_id(port: str) -> str | None:
    if not port.startswith("eth"):
        return None
    idx = port[3:]
    if not idx.isdigit():
        return None
    return f"1/0/{int(idx)}"


def _circuit_id_to_port(circuit_id: str) -> str | None:
    parts = str(circuit_id).split("/")
    if len(parts) != 3:
        return None
    if parts[0] != "1" or parts[1] != "0" or not parts[2].isdigit():
        return None
    return f"eth{int(parts[2])}"


@router.get("")
def list_routers(bng_id: Optional[str] = Query(None)):
    """List all access routers, optionally filtered by BNG ID."""
    has_total_interfaces = _has_total_interfaces_column()
    total_interfaces_select = "total_interfaces" if has_total_interfaces else "5 AS total_interfaces"

    if bng_id:
        rows = query_oss(
            """
            SELECT router_name, giaddr, bng_id, {total_interfaces_select},
                   is_alive, last_seen, last_ping,
                   active_subscribers, created_at, updated_at
            FROM access_routers
            WHERE bng_id = %(bng_id)s
            ORDER BY router_name
            """.format(total_interfaces_select=total_interfaces_select),
            {"bng_id": bng_id},
        )
    else:
        rows = query_oss(
            """
            SELECT router_name, giaddr, bng_id, {total_interfaces_select},
                   is_alive, last_seen, last_ping,
                   active_subscribers, created_at, updated_at
            FROM access_routers
            ORDER BY router_name
            """.format(total_interfaces_select=total_interfaces_select)
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
    has_total_interfaces = _has_total_interfaces_column()
    params = {
        "router_name": body.router_name,
        "giaddr": body.giaddr,
        "bng_id": body.bng_id,
        "total_interfaces": body.total_interfaces,
    }
    if has_total_interfaces:
        execute_oss(
            """
            INSERT INTO access_routers (router_name, giaddr, bng_id, total_interfaces)
            VALUES (%(router_name)s, %(giaddr)s::inet, %(bng_id)s, %(total_interfaces)s)
            """,
            params,
        )
    else:
        execute_oss(
            """
            INSERT INTO access_routers (router_name, giaddr, bng_id)
            VALUES (%(router_name)s, %(giaddr)s::inet, %(bng_id)s)
            """,
            params,
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
    if body.total_interfaces is not None and _has_total_interfaces_column():
        sets.append("total_interfaces = %(total_interfaces)s")
        params["total_interfaces"] = body.total_interfaces

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


@router.get("/{router_name}/available-ports")
def get_router_available_ports(router_name: str, service_id: Optional[int] = Query(None, ge=1)):
    """Return available subscriber-facing ports for a router."""
    has_total_interfaces = _has_total_interfaces_column()
    total_interfaces_select = "total_interfaces" if has_total_interfaces else "5 AS total_interfaces"

    rows = query_oss(
        f"""
        SELECT router_name, {total_interfaces_select}
        FROM access_routers
        WHERE router_name = %(name)s
        """,
        {"name": router_name},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Router not found")

    total_interfaces = int(rows[0]["total_interfaces"])
    subscriber_ports = _subscriber_ports(total_interfaces)

    params: dict = {"remote_id": router_name}
    exclude_sql = ""
    if service_id is not None:
        exclude_sql = "AND id <> %(service_id)s"
        params["service_id"] = service_id

    svc_rows = query_oss(
        f"""
        SELECT circuit_id
        FROM services
        WHERE remote_id = %(remote_id)s
          AND status <> 'TERMINATED'
          {exclude_sql}
        """,
        params,
    )

    used_ports: list[str] = []
    for row in svc_rows:
        port = _circuit_id_to_port(str(row["circuit_id"]))
        if port:
            used_ports.append(port)

    used_set = set(used_ports)
    available_ports = [p for p in subscriber_ports if p not in used_set]

    return {
        "data": {
            "router_name": router_name,
            "total_interfaces": total_interfaces,
            "subscriber_ports": subscriber_ports,
            "used_ports": sorted(used_set),
            "available_ports": available_ports,
            "available_count": len(available_ports),
        }
    }
