import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from uuid import UUID

import psycopg2
import psycopg2.pool
import psycopg2.extras
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import DisconnectACK, DisconnectNAK, DisconnectRequest
from pyrad.client import Timeout as PyradTimeout

PG_HOST = os.getenv("PG_HOST", "192.0.2.11")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "oss")
PG_USER = os.getenv("PG_USER", "oss")
PG_PASSWORD = os.getenv("PG_PASSWORD", "oss")
COA_PORT = int(os.getenv("COA_PORT", 3799))
COA_SECRET = os.getenv("RADIUS_SECRET", "testing123").encode()
COA_DICTIONARY = os.getenv("COA_DICTIONARY", "/opt/backend/radius/dictionary")

pool: psycopg2.pool.SimpleConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
    )
    yield
    pool.closeall()


app = FastAPI(title="OSS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    return pool.getconn()


def put_conn(conn):
    pool.putconn(conn)


def query(sql: str, params: dict | None = None) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return [_serialize_row(r) for r in rows]
    finally:
        put_conn(conn)


def execute(sql: str, params: dict | None = None) -> int:
    """Execute a non-SELECT statement. Returns rowcount."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rowcount = cur.rowcount
        conn.commit()
        return rowcount
    finally:
        put_conn(conn)


def _serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, UUID):
            out[k] = str(v)
        else:
            out[k] = str(v) if v is not None else None
    return out


def send_disconnect_request(nas_ip: str, session_id: str, username: Optional[str] = None) -> dict:
    if not os.path.exists(COA_DICTIONARY):
        raise HTTPException(status_code=500, detail=f"RADIUS dictionary not found: {COA_DICTIONARY}")

    client = Client(
        server=nas_ip,
        coaport=COA_PORT,
        secret=COA_SECRET,
        dict=Dictionary(COA_DICTIONARY),
        retries=1,
        timeout=2,
    )

    req = client.CreateCoAPacket(code=DisconnectRequest)
    req["Acct-Session-Id"] = session_id
    req["NAS-IP-Address"] = nas_ip
    if username:
        req["User-Name"] = username

    try:
        reply = client.SendPacket(req)
    except PyradTimeout:
        raise HTTPException(status_code=504, detail="CoA disconnect timeout")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"CoA disconnect send failed: {e}")

    if reply.code == DisconnectACK:
        return {"success": True, "reply_code": "Disconnect-ACK"}
    if reply.code == DisconnectNAK:
        return {"success": False, "reply_code": "Disconnect-NAK"}
    return {"success": False, "reply_code": f"Unexpected-{reply.code}"}


# --- Active Sessions ---

@app.get("/api/sessions/active")
def list_active_sessions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    rows = query(
        """
        SELECT * FROM sessions_active
        ORDER BY start_time DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"limit": limit, "offset": offset},
    )
    return {"data": rows, "count": len(rows)}


@app.get("/api/sessions/active/{session_id}")
def get_active_session(session_id: UUID):
    rows = query(
        "SELECT * FROM sessions_active WHERE session_id = %(sid)s",
        {"sid": str(session_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"data": rows[0]}


@app.post("/api/sessions/active/{session_id}/disconnect")
def disconnect_active_session(session_id: UUID):
    rows = query(
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


# --- Session History ---

@app.get("/api/sessions/history")
def list_session_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_after: Optional[str] = Query(None, description="ISO timestamp filter: start_time >="),
    start_before: Optional[str] = Query(None, description="ISO timestamp filter: start_time <="),
):
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if start_after:
        conditions.append("start_time >= %(start_after)s")
        params["start_after"] = start_after
    if start_before:
        conditions.append("start_time <= %(start_before)s")
        params["start_before"] = start_before

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query(
        f"""
        SELECT * FROM sessions_history
        {where}
        ORDER BY session_end DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    return {"data": rows, "count": len(rows)}


@app.get("/api/sessions/history/{session_id}")
def get_session_history(session_id: UUID):
    rows = query(
        "SELECT * FROM sessions_history WHERE session_id = %(sid)s",
        {"sid": str(session_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"data": rows[0]}


# --- Session Events ---

@app.get("/api/events")
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: Optional[UUID] = Query(None),
    event_type: Optional[str] = Query(None),
):
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if session_id:
        conditions.append("session_id = %(session_id)s")
        params["session_id"] = str(session_id)
    if event_type:
        conditions.append("event_type = %(event_type)s")
        params["event_type"] = event_type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query(
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


# --- Access Routers ---


class RouterCreate(BaseModel):
    router_name: str
    giaddr: str
    bng_id: str | None = None


class RouterUpdate(BaseModel):
    giaddr: str | None = None
    bng_id: str | None = None


@app.get("/api/routers")
def list_routers(bng_id: Optional[str] = Query(None)):
    if bng_id:
        rows = query(
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
        rows = query(
            """
            SELECT router_name, giaddr, bng_id,
                   is_alive, last_seen, last_ping,
                   active_subscribers, created_at, updated_at
            FROM access_routers
            ORDER BY router_name
            """
        )
    return {"data": rows, "count": len(rows)}


@app.post("/api/routers", status_code=201)
def create_router(body: RouterCreate):
    existing = query(
        "SELECT router_name FROM access_routers WHERE router_name = %(name)s",
        {"name": body.router_name},
    )
    if existing:
        raise HTTPException(status_code=409, detail="Router already exists")
    execute(
        """
        INSERT INTO access_routers (router_name, giaddr, bng_id)
        VALUES (%(router_name)s, %(giaddr)s::inet, %(bng_id)s)
        """,
        {"router_name": body.router_name, "giaddr": body.giaddr, "bng_id": body.bng_id},
    )
    rows = query(
        "SELECT * FROM access_routers WHERE router_name = %(name)s",
        {"name": body.router_name},
    )
    return {"data": rows[0]}


@app.put("/api/routers/{router_name}")
def update_router(router_name: str, body: RouterUpdate):
    existing = query(
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

    execute(
        f"UPDATE access_routers SET {', '.join(sets)} WHERE router_name = %(name)s",
        params,
    )
    rows = query(
        "SELECT * FROM access_routers WHERE router_name = %(name)s",
        {"name": router_name},
    )
    return {"data": rows[0]}


@app.delete("/api/routers/{router_name}")
def delete_router(router_name: str):
    rowcount = execute(
        "DELETE FROM access_routers WHERE router_name = %(name)s",
        {"name": router_name},
    )
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Router not found")
    return {"ok": True}


# --- BNG Registry & Health ---

@app.get("/api/bngs")
def list_bngs():
    rows = query(
        """
        SELECT bng_id, bng_instance_id, first_seen, last_seen, is_alive,
               cpu_usage, mem_usage, mem_max
        FROM bng_registry
        ORDER BY bng_id
        """
    )
    return {"data": rows, "count": len(rows)}


@app.get("/api/bngs/{bng_id}")
def get_bng(bng_id: str):
    rows = query(
        "SELECT * FROM bng_registry WHERE bng_id = %(bng_id)s",
        {"bng_id": bng_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="BNG not found")
    return {"data": rows[0]}


@app.get("/api/bngs/{bng_id}/health/{bng_instance_id}")
def get_bng_health(
    bng_id: str,
    bng_instance_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
):
    rows = query(
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


# --- Stats ---

@app.get("/api/stats")
def get_stats():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT count(*) as count FROM sessions_active")
            active_count = cur.fetchone()["count"]

            cur.execute("SELECT count(*) as count FROM sessions_history")
            history_count = cur.fetchone()["count"]

            cur.execute("SELECT count(*) as count FROM session_events")
            events_count = cur.fetchone()["count"]

            cur.execute("""
                SELECT coalesce(sum(input_octets), 0) as total_input_octets,
                       coalesce(sum(output_octets), 0) as total_output_octets,
                       coalesce(sum(input_packets), 0) as total_input_packets,
                       coalesce(sum(output_packets), 0) as total_output_packets
                FROM sessions_active
            """)
            traffic = cur.fetchone()

        conn.commit()
        return {
            "active_sessions": active_count,
            "history_sessions": history_count,
            "total_events": events_count,
            "active_traffic": {
                "input_octets": traffic["total_input_octets"],
                "output_octets": traffic["total_output_octets"],
                "input_packets": traffic["total_input_packets"],
                "output_packets": traffic["total_output_packets"],
            },
        }
    finally:
        put_conn(conn)
