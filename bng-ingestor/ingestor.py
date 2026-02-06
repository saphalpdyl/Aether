#!/usr/bin/env python3
"""
BNG Session Events Ingestor

Consumes session events from Redis Streams and stores them in PostgreSQL.
Events: SESSION_START, SESSION_UPDATE, SESSION_END
"""

import json
import os
import time
import redis
import psycopg2
from psycopg2.extras import Json

# Configuration from environment
REDIS_HOST = os.getenv("REDIS_HOST", "192.0.2.10")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_STREAM = os.getenv("REDIS_STREAM", "bng:session_events")
REDIS_CONSUMER_GROUP = os.getenv("REDIS_CONSUMER_GROUP", "oss_ingestors")
REDIS_CONSUMER_NAME = os.getenv("REDIS_CONSUMER_NAME", "ingestor-1")

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


def insert_session_event(conn, event: dict) -> bool:
    """Insert session event into PostgreSQL. Returns False if duplicate."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO session_events (
                idempotency_key, event_type, session_id, mac_address, ip_address,
                circuit_id, remote_id, relay_id, username, nas_ip,
                input_octets, output_octets, input_packets, output_packets,
                session_time, event_timestamp, raw_data
            ) VALUES (
                %(idempotency_key)s, %(event_type)s, %(session_id)s, %(mac_address)s, %(ip_address)s,
                %(circuit_id)s, %(remote_id)s, %(relay_id)s, %(username)s, %(nas_ip)s,
                %(input_octets)s, %(output_octets)s, %(input_packets)s, %(output_packets)s,
                %(session_time)s, NOW(), %(raw_data)s
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            {
                "idempotency_key": event.get("idempotency_key"),
                "event_type": event.get("event_type"),
                "session_id": event.get("session_id"),
                "mac_address": event.get("mac_address"),
                "ip_address": event.get("ip_address"),
                "circuit_id": event.get("circuit_id"),
                "remote_id": event.get("remote_id"),
                "relay_id": event.get("relay_id"),
                "username": event.get("username"),
                "nas_ip": event.get("nas_ip"),
                "input_octets": event.get("input_octets", 0),
                "output_octets": event.get("output_octets", 0),
                "input_packets": event.get("input_packets", 0),
                "output_packets": event.get("output_packets", 0),
                "session_time": event.get("session_time", 0),
                "raw_data": Json(event),
            },
        )
        inserted = cur.rowcount > 0
    conn.commit()
    if not inserted:
        print(f"Duplicate event skipped: {event.get('idempotency_key')}")
    return inserted


def upsert_active_session(conn, event: dict):
    """Update or insert active session based on event type."""
    event_type = event.get("event_type")

    with conn.cursor() as cur:
        if event_type == "SESSION_START":
            cur.execute(
                """
                INSERT INTO active_sessions (
                    session_id, mac_address, ip_address, circuit_id, remote_id,
                    relay_id, username, nas_ip, start_time, last_update
                ) VALUES (
                    %(session_id)s, %(mac_address)s, %(ip_address)s, %(circuit_id)s,
                    %(remote_id)s, %(relay_id)s, %(username)s, %(nas_ip)s, NOW(), NOW()
                )
                ON CONFLICT (session_id) DO UPDATE SET
                    mac_address = EXCLUDED.mac_address,
                    ip_address = EXCLUDED.ip_address,
                    start_time = NOW(),
                    last_update = NOW()
                """,
                event,
            )
        elif event_type == "SESSION_UPDATE":
            cur.execute(
                """
                UPDATE active_sessions SET
                    input_octets = %(input_octets)s,
                    output_octets = %(output_octets)s,
                    input_packets = %(input_packets)s,
                    output_packets = %(output_packets)s,
                    session_time = %(session_time)s,
                    last_update = NOW()
                WHERE session_id = %(session_id)s
                """,
                event,
            )
        elif event_type == "SESSION_END":
            cur.execute(
                "DELETE FROM active_sessions WHERE session_id = %(session_id)s",
                event,
            )
    conn.commit()


def process_event(conn, event_data: dict):
    """Process a single event from Redis stream."""
    try:
        # Decode bytes to string if needed
        decoded = {}
        for k, v in event_data.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            decoded[key] = val

        # Parse JSON data field if present
        if "data" in decoded:
            event = json.loads(decoded["data"])
        else:
            event = decoded

        print(f"Processing event: {event.get('event_type')} session={event.get('session_id')}")

        # Store in events table (returns False if duplicate)
        if insert_session_event(conn, event):
            # Only update active sessions if event was new
            upsert_active_session(conn, event)

        return True
    except Exception as e:
        print(f"Error processing event: {e}")
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
