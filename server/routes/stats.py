"""Statistics routes."""
from datetime import datetime, timedelta, timezone

import psycopg2.extras
from fastapi import APIRouter, Query

from db import get_oss_conn, put_oss_conn


router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats():
    """Get overall system statistics."""
    conn = get_oss_conn()
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
        put_oss_conn(conn)


RANGE_TO_MINUTES = {
    "15m": 15,
    "1h": 60,
    "6h": 360,
    "24h": 1440,
}


@router.get("/traffic-series")
def get_traffic_series(
    range: str = Query("1h", pattern="^(15m|1h|6h|24h)$"),
    bucket_seconds: int = Query(10, ge=5, le=300),
):
    """Get aggregate active traffic series from SESSION_UPDATE deltas."""
    window_minutes = RANGE_TO_MINUTES.get(range, 60)
    now = datetime.now(timezone.utc)
    start_ts = now - timedelta(minutes=window_minutes)

    # Include look-back rows for proper delta calculation at window start.
    prefetch_start = start_ts - timedelta(minutes=window_minutes)

    conn = get_oss_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                WITH updates AS (
                    SELECT
                        ts,
                        session_id,
                        input_octets,
                        output_octets,
                        lag(input_octets) OVER (PARTITION BY session_id ORDER BY ts) AS prev_input_octets,
                        lag(output_octets) OVER (PARTITION BY session_id ORDER BY ts) AS prev_output_octets
                    FROM session_events
                    WHERE event_type = 'SESSION_UPDATE'
                      AND ts >= %(prefetch_start)s
                ),
                deltas AS (
                    SELECT
                        ts,
                        GREATEST(input_octets - COALESCE(prev_input_octets, input_octets), 0) AS delta_input,
                        GREATEST(output_octets - COALESCE(prev_output_octets, output_octets), 0) AS delta_output
                    FROM updates
                    WHERE ts >= %(start_ts)s
                ),
                buckets AS (
                    SELECT
                        to_timestamp(
                            floor(extract(epoch FROM ts) / %(bucket_seconds)s) * %(bucket_seconds)s
                        )::timestamptz AS bucket_ts,
                        COALESCE(sum(delta_input), 0) AS bytes_in,
                        COALESCE(sum(delta_output), 0) AS bytes_out
                    FROM deltas
                    GROUP BY 1
                ),
                bucket_series AS (
                    SELECT generate_series(
                        to_timestamp(
                            floor(extract(epoch FROM %(start_ts)s::timestamptz) / %(bucket_seconds)s) * %(bucket_seconds)s
                        )::timestamptz,
                        to_timestamp(
                            floor(extract(epoch FROM now()) / %(bucket_seconds)s) * %(bucket_seconds)s
                        )::timestamptz,
                        (%(bucket_seconds)s || ' seconds')::interval
                    ) AS bucket_ts
                )
                SELECT
                    s.bucket_ts,
                    COALESCE(b.bytes_in, 0) AS bytes_in,
                    COALESCE(b.bytes_out, 0) AS bytes_out,
                    round((COALESCE(b.bytes_in, 0) * 8.0) / %(bucket_seconds)s, 2) AS bps_in,
                    round((COALESCE(b.bytes_out, 0) * 8.0) / %(bucket_seconds)s, 2) AS bps_out,
                    round(((COALESCE(b.bytes_in, 0) + COALESCE(b.bytes_out, 0)) * 8.0) / %(bucket_seconds)s, 2) AS bps_total
                FROM bucket_series s
                LEFT JOIN buckets b ON b.bucket_ts = s.bucket_ts
                ORDER BY s.bucket_ts ASC
                """,
                {
                    "prefetch_start": prefetch_start,
                    "start_ts": start_ts,
                    "bucket_seconds": bucket_seconds,
                },
            )
            rows = cur.fetchall()

        conn.commit()
        data = [
            {
                "ts": row["bucket_ts"].isoformat(),
                "bytes_in": int(row["bytes_in"]),
                "bytes_out": int(row["bytes_out"]),
                "bps_in": float(row["bps_in"]),
                "bps_out": float(row["bps_out"]),
                "bps_total": float(row["bps_total"]),
            }
            for row in rows
        ]
        return {
            "range": range,
            "bucket_seconds": bucket_seconds,
            "data": data,
            "count": len(data),
        }
    finally:
        put_oss_conn(conn)
