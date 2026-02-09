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

PG_HOST = os.getenv("PG_HOST", "192.0.2.11")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "oss")
PG_USER = os.getenv("PG_USER", "oss")
PG_PASSWORD = os.getenv("PG_PASSWORD", "oss")

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
