"""Database connection pooling and query utilities."""
import os
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import psycopg2
import psycopg2.pool
import psycopg2.extras


PG_HOST = os.getenv("PG_HOST", "192.0.2.11")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "oss")
PG_USER = os.getenv("PG_USER", "oss")
PG_PASSWORD = os.getenv("PG_PASSWORD", "oss")

RADIUS_PG_HOST = os.getenv("RADIUS_PG_HOST", "192.0.2.6")
RADIUS_PG_PORT = int(os.getenv("RADIUS_PG_PORT", 5432))
RADIUS_PG_DB = os.getenv("RADIUS_PG_DB", "radius")
RADIUS_PG_USER = os.getenv("RADIUS_PG_USER", "radius")
RADIUS_PG_PASSWORD = os.getenv("RADIUS_PG_PASSWORD", "test")

oss_pool: psycopg2.pool.SimpleConnectionPool | None = None
radius_pool: psycopg2.pool.SimpleConnectionPool | None = None


def init_pools():
    """Initialize database connection pools."""
    global oss_pool, radius_pool
    oss_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
    )
    radius_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        host=RADIUS_PG_HOST, port=RADIUS_PG_PORT,
        dbname=RADIUS_PG_DB, user=RADIUS_PG_USER, password=RADIUS_PG_PASSWORD,
    )


def close_pools():
    """Close all database connection pools."""
    if oss_pool:
        oss_pool.closeall()
    if radius_pool:
        radius_pool.closeall()


def get_oss_conn():
    """Get a connection from the OSS pool."""
    return oss_pool.getconn()


def put_oss_conn(conn):
    """Return a connection to the OSS pool."""
    oss_pool.putconn(conn)


def get_radius_conn():
    """Get a connection from the RADIUS pool."""
    return radius_pool.getconn()


def put_radius_conn(conn):
    """Return a connection to the RADIUS pool."""
    radius_pool.putconn(conn)


def _serialize_row(row: dict) -> dict:
    """Serialize a database row to JSON-compatible format."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = str(v) if v is not None else None
    return out


def query_oss(sql: str, params: dict | None = None) -> list[dict]:
    """Execute a SELECT query on the OSS database."""
    conn = get_oss_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return [_serialize_row(r) for r in rows]
    finally:
        put_oss_conn(conn)


def query_radius(sql: str, params: dict | None = None) -> list[dict]:
    """Execute a SELECT query on the RADIUS database."""
    conn = get_radius_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return [_serialize_row(r) for r in rows]
    finally:
        put_radius_conn(conn)


def execute_oss(sql: str, params: dict | None = None) -> int:
    """Execute a non-SELECT statement on the OSS database. Returns rowcount."""
    conn = get_oss_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rowcount = cur.rowcount
        conn.commit()
        return rowcount
    finally:
        put_oss_conn(conn)


def execute_radius(sql: str, params: dict | None = None) -> int:
    """Execute a non-SELECT statement on the RADIUS database. Returns rowcount."""
    conn = get_radius_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rowcount = cur.rowcount
        conn.commit()
        return rowcount
    finally:
        put_radius_conn(conn)
