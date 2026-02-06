#!/usr/bin/env python3
import argparse
import json
import threading
import subprocess
import time
import uuid
from queue import Queue

from lib.services.bng import bng_event_loop


def start_sniffer(
    bng_id: str
) -> None:
    subprocess.run("pkill -f bng_dhcp_sniffer.py 2>/dev/null || true", shell=True)
    subprocess.run("rm -f /tmp/bng_dhcp_events.json /tmp/bng_dhcp_sniffer.stderr", shell=True)

    bng_uplink_mac = subprocess.check_output("cat /sys/class/net/eth2/address", shell=True, text=True).strip()

    cmd = (
        "nohup python3 /opt/bng/bng_dhcp_sniffer.py "
        "--client-if eth1 --uplink-if eth2 "
        "--server-ip 192.0.2.3 --giaddr 10.0.0.1 --relay-id 192.0.2.1 "
        "--src-ip 192.0.2.1 --src-mac {src_mac} "
        f"--log /tmp/bng_dhcp_relay.log --json --bng-id {bng_id} "
        "> /tmp/bng_dhcp_events.json 2> /tmp/bng_dhcp_sniffer.stderr &"
    ).format(src_mac=bng_uplink_mac)
    subprocess.run(cmd, shell=True)


def tail_events(q: Queue):
    proc = subprocess.Popen(
        ["tail", "-F", "/tmp/bng_dhcp_events.json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if not proc.stdout:
        return
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            q.put(event)
        except Exception:
            continue


def main():
    parser = argparse.ArgumentParser(description="BNG Main Process")
    parser.add_argument("--bng-id", required=True, help="BNG identifier for distributed deployment")
    args = parser.parse_args()

    # Generate unique instance ID (changes on restart)
    bng_instance_id = str(uuid.uuid4())

    print(f"Aether-BNG starting: id={args.bng_id} instance={bng_instance_id}")

    # Wait for interfaces to exist
    for _ in range(20):
        if subprocess.call("ip link show eth1 >/dev/null 2>&1 && ip link show eth2 >/dev/null 2>&1", shell=True) == 0:
            break
        time.sleep(0.5)

    # Wait for IPs to be assigned (entrypoint.sh sets these)
    for _ in range(30):
        result = subprocess.run(
            "ip -4 addr show eth1 | grep -q '10.0.0.1' && ip -4 addr show eth2 | grep -q '192.0.2.1'",
            shell=True
        )
        if result.returncode == 0:
            break
        time.sleep(0.5)

    start_sniffer(bng_id=args.bng_id)

    q: Queue = Queue(maxsize=1000)
    stop_event = threading.Event()
    t = threading.Thread(target=tail_events, args=(q,), daemon=True)
    t.start()

    print("Starting BNG event loop")
    bng_event_loop(stop_event, q, "eth1", 30, bng_id=args.bng_id, bng_instance_id=bng_instance_id)


if __name__ == "__main__":
    main()
