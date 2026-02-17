import json
import time
import random
from typing import List

from config import log

# Load traffic simulation config
with open("simulator.config.json") as f:
    SIMULATOR_CONFIG = json.load(f)
TRAFFIC_COMMANDS = SIMULATOR_CONFIG["traffic_commands"]

DHCP_MAX_RETRIES = 5
DHCP_RETRY_INTERVAL = 2

def dhcp_acquire(container) -> bool:
    """Run dhclient on a host container with retries. Returns True if lease obtained."""
    for attempt in range(1, DHCP_MAX_RETRIES + 1):
        result = container.exec_run(["sh", "-c", "dhclient -v eth1"])
        if result.exit_code == 0:
            log.info("DHCP lease acquired", host=container.name, attempt=attempt)
            return True
        log.warning("DHCP attempt failed", host=container.name, attempt=attempt, exit_code=result.exit_code,
                     output=result.output.decode(errors="replace")[:200])
        if attempt < DHCP_MAX_RETRIES:
            time.sleep(DHCP_RETRY_INTERVAL)
    log.error("DHCP lease acquisition failed after all retries", host=container.name)
    return False

def dhcp_acquire_all(host_containers) -> List:
    """Run DHCP on all host containers. Returns list of containers that got a lease."""
    leased = []
    for container in host_containers:
        if dhcp_acquire(container):
            leased.append(container)
    return leased

def traffic_loop(container):
    """Continuously run random traffic commands on a host container."""
    weights = [group["weight"] for group in TRAFFIC_COMMANDS]
    while True:
        try:
            group = random.choices(TRAFFIC_COMMANDS, weights=weights, k=1)[0]
            cmd = random.choice(group["commands"])
            result = container.exec_run(["sh", "-c", cmd])
            stdout_snippet = result.output.decode(errors="replace")[:200]
            log.info("traffic_cmd",
                     host=container.name,
                     cmd_group=group["name"],
                     exit_code=result.exit_code,
                     output=stdout_snippet)
        except Exception as e:
            log.error("traffic_cmd_error", host=container.name, error=str(e))
        sleep_time = random.uniform(*group["sleep_range"])
        time.sleep(sleep_time)
