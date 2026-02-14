#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import uuid

import redis.asyncio as aioredis

from lib.services.bng import bng_event_loop

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "192.0.2.10")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


async def wait_for_redis(max_retries=30, delay=2) -> aioredis.Redis:
    """Wait for Redis to be available."""
    for i in range(max_retries):
        try:
            r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            await r.ping()
            print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return r
        except Exception:
            print(f"Waiting for Redis... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    raise RuntimeError("Could not connect to Redis")


async def run_sniffer(bng_id: str, event_queue: asyncio.PriorityQueue):
    """Start the DHCP sniffer and feed its stdout JSON lines into the priority queue."""
    # Get uplink MAC
    proc = await asyncio.create_subprocess_shell(
        "cat /sys/class/net/eth2/address",
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    bng_uplink_mac = stdout.decode().strip()

    # Kill any existing sniffer
    kill_proc = await asyncio.create_subprocess_shell(
        "pkill -f bng_dhcp_sniffer.py 2>/dev/null || true"
    )
    await kill_proc.wait()

    cmd = [
        "python3", "-u", "/opt/bng/bng_dhcp_sniffer.py",
        "--client-if", "eth1", "--uplink-if", "eth2",
        "--server-ip", "192.0.2.3", "--giaddr", "10.0.0.1",
        "--relay-id", "192.0.2.1",
        "--src-ip", "192.0.2.1", "--src-mac", bng_uplink_mac,
        "--log", "/tmp/bng_dhcp_relay.log", "--json",
        "--bng-id", bng_id,
    ]

    seq = 0
    while True:
        sniffer = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        print(f"DHCP sniffer started (pid={sniffer.pid})")

        while True:
            line = await sniffer.stdout.readline()
            if not line:
                break  # process exited
            line = line.decode().strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                seq += 1
                # Priority 1 for DHCP events; seq for FIFO ordering within same priority
                await event_queue.put((1, seq, event))
            except Exception:
                continue

        returncode = await sniffer.wait()
        print(f"DHCP sniffer exited (code={returncode}), restarting in 2s...")
        await asyncio.sleep(2)


async def async_main():
    parser = argparse.ArgumentParser(description="BNG Main Process")
    parser.add_argument("--bng-id", required=True, help="BNG identifier for distributed deployment")
    args = parser.parse_args()

    # Generate unique instance ID (changes on restart)
    bng_instance_id = str(uuid.uuid4())

    print(f"Aether-BNG starting: id={args.bng_id} instance={bng_instance_id}")

    # Wait for interfaces to exist
    for _ in range(20):
        proc = await asyncio.create_subprocess_shell(
            "ip link show eth1 >/dev/null 2>&1 && ip link show eth2 >/dev/null 2>&1"
        )
        if await proc.wait() == 0:
            break
        await asyncio.sleep(0.5)

    # Wait for IPs to be assigned (entrypoint.sh sets these)
    for _ in range(30):
        proc = await asyncio.create_subprocess_shell(
            "ip -4 addr show eth1 | grep -q '10.0.0.1' && ip -4 addr show eth2 | grep -q '192.0.2.1'"
        )
        if await proc.wait() == 0:
            break
        await asyncio.sleep(0.5)

    # Connect to Redis for session events stream
    redis_client = await wait_for_redis()

    event_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=1000)

    # Start sniffer as background task (replaces thread + tail -F)
    sniffer_task = asyncio.create_task(run_sniffer(bng_id=args.bng_id, event_queue=event_queue))

    print("Starting BNG event loop")
    await bng_event_loop(
        event_queue,
        iface="eth1",
        uplink_iface="eth2",
        nas_port_id="eth1",
        interim_interval=30,
        bng_id=args.bng_id,
        bng_instance_id=bng_instance_id,
        redis_conn=redis_client,
    )


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
