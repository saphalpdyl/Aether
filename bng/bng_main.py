#!/usr/bin/env python3
import argparse
import asyncio
import ipaddress
import json
import os
import uuid

import redis.asyncio as aioredis

from lib.services.bng import bng_event_loop

SUBSCRIBER_IFACE = os.getenv("BNG_SUBSCRIBER_IFACE", "eth1")
UPLINK_IFACE = os.getenv("BNG_UPLINK_IFACE", "eth2")
DHCP_UPLINK_IFACE = os.getenv("BNG_DHCP_UPLINK_IFACE", "eth3")
SUBSCRIBER_IP_CIDR = os.getenv("BNG_SUBSCRIBER_IP_CIDR", "10.0.0.1/24")
UPLINK_IP_CIDR = os.getenv("BNG_UPLINK_IP_CIDR", "192.0.2.1/30")
DHCP_UPLINK_IP_CIDR = os.getenv("BNG_DHCP_UPLINK_IP_CIDR", "198.18.0.1/24")
DHCP_SERVER_IP = os.getenv("BNG_DHCP_SERVER_IP", "198.18.0.3")
RADIUS_SERVER_IP = os.getenv("BNG_RADIUS_SERVER_IP", "198.18.0.2")
NAS_IP = os.getenv("BNG_NAS_IP", "198.18.0.1")
OSS_API_URL = os.getenv("BNG_OSS_API_URL", "http://198.18.0.21:8000")

# Redis configuration
REDIS_HOST = os.getenv("BNG_REDIS_HOST", os.getenv("REDIS_HOST", "198.18.0.10"))
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


def _ip_from_cidr(cidr: str) -> str:
    return str(ipaddress.ip_interface(cidr).ip)


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
    # Get DHCP server-facing MAC (mgmt interface)
    proc = await asyncio.create_subprocess_shell(
        f"cat /sys/class/net/{DHCP_UPLINK_IFACE}/address",
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
        "--client-if", SUBSCRIBER_IFACE,
        "--uplink-if", DHCP_UPLINK_IFACE,
        "--server-ip", DHCP_SERVER_IP,
        "--giaddr", _ip_from_cidr(SUBSCRIBER_IP_CIDR),
        "--relay-id", NAS_IP,
        "--src-ip", NAS_IP,
        "--src-mac", bng_uplink_mac,
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
            f"ip link show {SUBSCRIBER_IFACE} >/dev/null 2>&1 && "
            f"ip link show {UPLINK_IFACE} >/dev/null 2>&1 && "
            f"ip link show {DHCP_UPLINK_IFACE} >/dev/null 2>&1"
        )
        if await proc.wait() == 0:
            break
        await asyncio.sleep(0.5)

    # Wait for IPs to be assigned (entrypoint.sh sets these)
    for _ in range(30):
        proc = await asyncio.create_subprocess_shell(
            f"ip -4 addr show {SUBSCRIBER_IFACE} | grep -q '{_ip_from_cidr(SUBSCRIBER_IP_CIDR)}' && "
            f"ip -4 addr show {UPLINK_IFACE} | grep -q '{_ip_from_cidr(UPLINK_IP_CIDR)}' && "
            f"ip -4 addr show {DHCP_UPLINK_IFACE} | grep -q '{_ip_from_cidr(DHCP_UPLINK_IP_CIDR)}'"
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
        iface=SUBSCRIBER_IFACE,
        uplink_iface=UPLINK_IFACE,
        radius_server_ip=RADIUS_SERVER_IP,
        nas_ip=NAS_IP,
        nas_port_id=SUBSCRIBER_IFACE,
        oss_api_url=OSS_API_URL,
        interim_interval=30,
        bng_id=args.bng_id,
        bng_instance_id=bng_instance_id,
        redis_conn=redis_client,
    )


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
