import time
import random
from typing import List

from config import log, SIMULATOR_CONFIG

# Load traffic simulation config — hashmap keyed by name; expand into list for weighted sampling
# Skip commands with disable_in_automated_simulation = true
TRAFFIC_COMMANDS = [
    {"name": name, **data}
    for name, data in SIMULATOR_CONFIG["traffic_commands"].items()
    if not data.get("disable_in_automated_simulation", False)
]

DHCP_MAX_RETRIES = 5
DHCP_RETRY_INTERVAL = 2

# Session lifecycle timing (seconds)
ACTIVE_RANGE = [60, 180]   # how long a subscriber stays online generating traffic
OFFLINE_RANGE = [20, 90]   # how long a subscriber stays offline after releasing


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


def dhcp_release(container) -> bool:
    """Release DHCP lease on eth1. Returns True on success."""
    result = container.exec_run(["sh", "-c", "dhclient -v -r -d eth1"])
    if result.exit_code == 0:
        log.info("DHCP lease released", host=container.name)
        return True
    log.warning("DHCP release failed", host=container.name, exit_code=result.exit_code,
                 output=result.output.decode(errors="replace")[:200])
    return False


def dhcp_acquire_all(host_containers) -> List:
    """Run DHCP on all host containers. Returns list of containers that got a lease."""
    leased = []
    for container in host_containers:
        if dhcp_acquire(container):
            leased.append(container)
    return leased


def _run_traffic_for_duration(container, duration: float):
    """Run random traffic commands on a container for approximately `duration` seconds."""
    weights = [group["weight"] for group in TRAFFIC_COMMANDS]
    end_time = time.time() + duration
    while time.time() < end_time:
        try:
            group = random.choices(TRAFFIC_COMMANDS, weights=weights, k=1)[0]
            cmd = random.choice(group["commands"])
            result = container.exec_run(["sh", "-c", cmd["command"]])
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


def traffic_loop(container):
    """Session lifecycle: generate traffic → release DHCP → go offline → re-acquire → repeat."""
    while True:
        active_duration = random.uniform(*ACTIVE_RANGE)
        log.info("session_active", host=container.name, duration_s=round(active_duration))
        _run_traffic_for_duration(container, active_duration)

        dhcp_release(container)

        offline_duration = random.uniform(*OFFLINE_RANGE)
        log.info("session_offline", host=container.name, duration_s=round(offline_duration))
        time.sleep(offline_duration)

        if not dhcp_acquire(container):
            log.error("DHCP re-acquire failed, stopping session lifecycle", host=container.name)
            return
