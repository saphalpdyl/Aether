"""Statistics routes."""
import psycopg2.extras
from fastapi import APIRouter

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
