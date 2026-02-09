import subprocess
import time


class RouterTracker:
    def __init__(self, bng_id: str, event_dispatcher):
        self.bng_id = bng_id
        self.event_dispatcher = event_dispatcher
        self.routers = {}  # {router_name: {"giaddr": str, "first_seen": float, "last_seen": float, "is_alive": bool}}

    def _extract_router_name(self, circuit_id: str) -> str | None:
        if not circuit_id:
            return None
        parts = circuit_id.split("|")
        return parts[0] if parts[0] else None

    def on_dhcp_event(self, event: dict):
        circuit_id = event.get("circuit_id")
        giaddr = event.get("giaddr")
        if not circuit_id or not giaddr or giaddr == "0.0.0.0":
            return

        name = self._extract_router_name(circuit_id)
        if not name:
            return

        now = time.time()
        if name not in self.routers:
            self.routers[name] = {
                "giaddr": giaddr,
                "first_seen": now,
                "last_seen": now,
                "is_alive": True,
            }
            self._dispatch(name, self.routers[name])
        else:
            self.routers[name]["last_seen"] = now
            self.routers[name]["giaddr"] = giaddr

    def _dispatch(self, name: str, info: dict):
        self.event_dispatcher.dispatch_router_update(
            router_name=name,
            giaddr=info["giaddr"],
            is_alive=info["is_alive"],
            first_seen=info["first_seen"],
            last_seen=info["last_seen"],
        )

    def ping_all(self):
        for name, info in self.routers.items():
            alive = self._ping(info["giaddr"])
            info["is_alive"] = alive
            self._dispatch(name, info)

    def _ping(self, ip: str) -> bool:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except Exception:
            return False
