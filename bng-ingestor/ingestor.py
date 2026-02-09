#!/usr/bin/env python3
"""
BNG Session Events Ingestor

Consumes session events from Redis Streams and stores them in PostgreSQL.
Events: SESSION_START, SESSION_UPDATE, SESSION_STOP, POLICY_APPLY
"""

import json
import os
import time
from datetime import datetime
import redis
import psycopg2
from psycopg2.extras import Json

# Configuration from environment
REDIS_HOST = os.getenv("REDIS_HOST", "192.0.2.10")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_STREAM = os.getenv("REDIS_STREAM", "bng_events")

REDIS_CONSUMER_GROUP = os.getenv("REDIS_CONSUMER_GROUP", "bng_ingestors")
REDIS_CONSUMER_NAME = os.getenv("REDIS_CONSUMER_NAME", "bng-ingestor-1")

PG_HOST = os.getenv("PG_HOST", "192.0.2.11")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "oss")
PG_USER = os.getenv("PG_USER", "oss")
PG_PASSWORD = os.getenv("PG_PASSWORD", "oss")


def wait_for_redis(max_retries=30, delay=2):
    """Wait for Redis to be available."""
    for i in range(max_retries):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            r.ping()
            print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return r
        except redis.ConnectionError:
            print(f"Waiting for Redis... ({i+1}/{max_retries})")
            time.sleep(delay)
    raise RuntimeError("Could not connect to Redis")


def wait_for_postgres(max_retries=30, delay=2):
    """Wait for PostgreSQL to be available."""
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=PG_DB,
                user=PG_USER,
                password=PG_PASSWORD,
            )
            print(f"Connected to PostgreSQL at {PG_HOST}:{PG_PORT}/{PG_DB}")
            return conn
        except psycopg2.OperationalError:
            print(f"Waiting for PostgreSQL... ({i+1}/{max_retries})")
            time.sleep(delay)
    raise RuntimeError("Could not connect to PostgreSQL")


def ensure_consumer_group(r: redis.Redis):
    """Create consumer group if it doesn't exist."""
    try:
        r.xgroup_create(REDIS_STREAM, REDIS_CONSUMER_GROUP, id="0", mkstream=True)
        print(f"Created consumer group: {REDIS_CONSUMER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group already exists: {REDIS_CONSUMER_GROUP}")
        else:
            raise


def parse_event(event_data: dict) -> dict:
    """Parse and decode event data from Redis."""
    decoded = {}
    for k, v in event_data.items():
        key = k.decode() if isinstance(k, bytes) else k
        val = v.decode() if isinstance(v, bytes) else v
        decoded[key] = val
    return decoded


def ts_to_datetime(ts_str: str) -> datetime:
    """Convert unix timestamp string to datetime."""
    try:
        return datetime.fromtimestamp(float(ts_str))
    except (ValueError, TypeError):
        return datetime.now()


def insert_session_event(conn, event: dict) -> bool:
    """Insert session event into PostgreSQL. Returns False if duplicate."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO session_events (
                    bng_id, bng_instance_id, seq,
                    event_type, ts, session_id,
                    nas_ip, circuit_id, remote_id,
                    mac_address, ip_address, username,
                    input_octets, output_octets, input_packets, output_packets,
                    status, auth_state, raw_data, terminate_cause, session_start, session_last_update, session_end
                ) VALUES (
                    %(bng_id)s, %(bng_instance_id)s::uuid, %(seq)s,
                    %(event_type)s, %(ts)s, %(session_id)s::uuid,
                    %(nas_ip)s::inet, %(circuit_id)s, %(remote_id)s,
                    %(mac_address)s::macaddr, %(ip_address)s::inet, %(username)s,
                    %(input_octets)s, %(output_octets)s, %(input_packets)s, %(output_packets)s,
                    %(status)s, %(auth_state)s, %(raw_data)s, %(terminate_cause)s, %(ts)s, %(ts)s, %(session_end)s
                )
                ON CONFLICT (bng_id, bng_instance_id, seq) DO NOTHING
                """,
                {
                    "bng_id": event.get("bng_id"),
                    "bng_instance_id": event.get("bng_instance_id"),
                    "seq": int(event.get("seq", 0)),
                    "event_type": event.get("event_type"),
                    "ts": ts_to_datetime(event.get("ts")),
                    "session_id": event.get("session_id"),
                    "nas_ip": event.get("nas_ip"),
                    "circuit_id": event.get("circuit_id"),
                    "remote_id": event.get("remote_id"),
                    "mac_address": event.get("mac_address"),
                    "ip_address": event.get("ip_address") or None,
                    "username": event.get("username"),
                    "input_octets": int(event.get("input_octets", 0) or 0),
                    "output_octets": int(event.get("output_octets", 0) or 0),
                    "input_packets": int(event.get("input_packets", 0) or 0),
                    "output_packets": int(event.get("output_packets", 0) or 0),
                    "status": event.get("status"),
                    "auth_state": event.get("auth_state"),
                    "raw_data": Json(event),
                    "terminate_cause": event.get("terminate_cause", ""),
                    "session_end": ts_to_datetime(event.get("ts")) if event.get("event_type") == "SESSION_STOP" else None,
                },
            )
            inserted = cur.rowcount > 0
        conn.commit()
        return inserted
    except Exception as e:
        conn.rollback()
        print(f"Error inserting session event: {e}")
        return False


def handle_session_start(conn, event: dict):
    """Handle SESSION_START: Insert or update active session."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sessions_active (
                session_id, bng_id, bng_instance_id,
                nas_ip, circuit_id, remote_id,
                mac_address, ip_address, username,
                start_time, last_update,
                input_octets, output_octets, input_packets, output_packets,
                status, auth_state
            ) VALUES (
                %(session_id)s::uuid, %(bng_id)s, %(bng_instance_id)s::uuid,
                %(nas_ip)s::inet, %(circuit_id)s, %(remote_id)s,
                %(mac_address)s::macaddr, %(ip_address)s::inet, %(username)s,
                %(ts)s, %(ts)s,
                0, 0, 0, 0,
                %(status)s, %(auth_state)s
            )
            ON CONFLICT (session_id) DO UPDATE SET
                ip_address = EXCLUDED.ip_address,
                last_update = EXCLUDED.last_update
            """,
            {
                "session_id": event.get("session_id"),
                "bng_id": event.get("bng_id"),
                "bng_instance_id": event.get("bng_instance_id"),
                "nas_ip": event.get("nas_ip"),
                "circuit_id": event.get("circuit_id"),
                "remote_id": event.get("remote_id"),
                "mac_address": event.get("mac_address"),
                "ip_address": event.get("ip_address") or None,
                "username": event.get("username"),
                "ts": ts_to_datetime(event.get("ts")),
                "status": event.get("status", "ACTIVE"),
                "auth_state": event.get("auth_state", "PENDING_AUTH"),
            },
        )
    conn.commit()


def handle_session_update(conn, event: dict):
    """Handle SESSION_UPDATE: Update counters on active session."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions_active SET
                input_octets = %(input_octets)s,
                output_octets = %(output_octets)s,
                input_packets = %(input_packets)s,
                output_packets = %(output_packets)s,
                status = %(status)s,
                auth_state = %(auth_state)s,
                last_update = %(ts)s
            WHERE session_id = %(session_id)s::uuid
            """,
            {
                "session_id": event.get("session_id"),
                "input_octets": int(event.get("input_octets", 0) or 0),
                "output_octets": int(event.get("output_octets", 0) or 0),
                "input_packets": int(event.get("input_packets", 0) or 0),
                "output_packets": int(event.get("output_packets", 0) or 0),
                "status": event.get("status", "ACTIVE"),
                "auth_state": event.get("auth_state", "PENDING_AUTH"),
                "ts": ts_to_datetime(event.get("ts")),
            },
        )
    conn.commit()


def handle_session_stop(conn, event: dict):
    session_id = event["session_id"]
    session_end = event.get("ts")
    terminate_cause = event.get("terminate_cause")
    terminate_source = event.get("terminate_source")

    with conn.cursor() as cur:
        # 1. Update active session with final counters from the STOP event
        cur.execute(
            """
            UPDATE sessions_active SET
                input_octets = %(input_octets)s,
                output_octets = %(output_octets)s,
                input_packets = %(input_packets)s,
                output_packets = %(output_packets)s,
                status = 'STOPPED',
                last_update = %(ts)s
            WHERE session_id = %(session_id)s::uuid
            """,
            {
                "session_id": session_id,
                "input_octets": int(event.get("input_octets", 0) or 0),
                "output_octets": int(event.get("output_octets", 0) or 0),
                "input_packets": int(event.get("input_packets", 0) or 0),
                "output_packets": int(event.get("output_packets", 0) or 0),
                "ts": ts_to_datetime(session_end),
            },
        )

        # 2. Move updated row from sessions_active to sessions_history
        cur.execute(
            """
            WITH moved AS (
              DELETE FROM sessions_active
              WHERE session_id = %(session_id)s::uuid
              RETURNING
                session_id, bng_id, bng_instance_id,
                nas_ip, circuit_id, remote_id,
                mac_address, ip_address, username,
                start_time, last_update,
                input_octets, output_octets, input_packets, output_packets,
                status, auth_state
            )
            INSERT INTO sessions_history (
              session_id, bng_id, bng_instance_id,
              nas_ip, circuit_id, remote_id,
              mac_address, ip_address, username,
              start_time, last_update,
              input_octets, output_octets, input_packets, output_packets,
              status, auth_state,
              session_end, terminate_cause, terminate_source
            )
            SELECT
              session_id, bng_id, bng_instance_id,
              nas_ip, circuit_id, remote_id,
              mac_address, ip_address, username,
              start_time, last_update,
              input_octets, output_octets, input_packets, output_packets,
              status, auth_state,
              %(session_end)s::timestamptz,
              %(terminate_cause)s::text,
              %(terminate_source)s::text
            FROM moved;
            """,
            {
                "session_id": session_id,
                "session_end": ts_to_datetime(session_end),
                "terminate_cause": terminate_cause,
                "terminate_source": terminate_source,
            },
        )
    conn.commit()


def handle_policy_apply(conn, event: dict):
    """Handle POLICY_APPLY: Update auth_state on active session."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions_active SET
                auth_state = %(auth_state)s,
                last_update = %(ts)s
            WHERE session_id = %(session_id)s::uuid
            """,
            {
                "session_id": event.get("session_id"),
                "auth_state": event.get("auth_state", "PENDING_AUTH"),
                "ts": ts_to_datetime(event.get("ts")),
            },
        )
    conn.commit()


def handle_router_update(conn, event: dict):
    """Handle ROUTER_UPDATE: Upsert access router in registry."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO access_routers (router_name, giaddr, bng_id, first_seen, last_seen, is_alive, last_ping)
            VALUES (%(router_name)s, %(giaddr)s::inet, %(bng_id)s,
                    %(first_seen)s, %(last_seen)s, %(is_alive)s, now())
            ON CONFLICT (router_name) DO UPDATE SET
                giaddr = EXCLUDED.giaddr,
                last_seen = EXCLUDED.last_seen,
                is_alive = EXCLUDED.is_alive,
                last_ping = now()
            """,
            {
                "router_name": event.get("router_name"),
                "giaddr": event.get("giaddr"),
                "bng_id": event.get("bng_id"),
                "first_seen": ts_to_datetime(event.get("first_seen")),
                "last_seen": ts_to_datetime(event.get("last_seen")),
                "is_alive": event.get("is_alive") == "True",
            },
        )
    conn.commit()


EVENT_HANDLERS = {
    "SESSION_START": handle_session_start,
    "SESSION_UPDATE": handle_session_update,
    "SESSION_STOP": handle_session_stop,
    "POLICY_APPLY": handle_policy_apply,
    "ROUTER_UPDATE": handle_router_update,
}


def process_event(conn, event_data: dict) -> bool:
    """Process a single event from Redis stream."""
    try:
        event = parse_event(event_data)
        event_type = event.get("event_type")

        print(f"Processing event: {event_type} session={event.get('session_id')}")

        # ROUTER_UPDATE is not a session event — skip session_events table
        if event_type == "ROUTER_UPDATE":
            handle_router_update(conn, event)
            return True

        # Store in events table (returns False if duplicate)
        if not insert_session_event(conn, event):
            print(f"Duplicate event skipped: bng_id={event.get('bng_id')} seq={event.get('seq')}")
            return True  # Still acknowledge, it's a duplicate

        # Handle event-specific logic
        handler = EVENT_HANDLERS.get(event_type)
        if handler:
            handler(conn, event)
        else:
            print(f"Unknown event type: {event_type}")

        return True
    except Exception as e:
        print(f"Error processing event: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("BNG Session Events Ingestor starting...")

    # Connect to services
    r = wait_for_redis()
    conn = wait_for_postgres()

    # Setup consumer group
    ensure_consumer_group(r)

    print(f"Listening on stream: {REDIS_STREAM}")

    while True:
        try:
            # Read from stream with consumer group
            messages = r.xreadgroup(
                REDIS_CONSUMER_GROUP,
                REDIS_CONSUMER_NAME,
                {REDIS_STREAM: ">"},
                count=10,
                block=5000,
            )

            if not messages:
                continue

            for stream_name, stream_messages in messages:
                for message_id, message_data in stream_messages:
                    if process_event(conn, message_data):
                        # Acknowledge the message
                        r.xack(REDIS_STREAM, REDIS_CONSUMER_GROUP, message_id)

        except redis.ConnectionError:
            print("Lost connection to Redis, reconnecting...")
            r = wait_for_redis()
        except psycopg2.OperationalError:
            print("Lost connection to PostgreSQL, reconnecting...")
            conn = wait_for_postgres()
        except KeyboardInterrupt:
            print("Shutting down...")
            break

    conn.close()


if __name__ == "__main__":
    main()
