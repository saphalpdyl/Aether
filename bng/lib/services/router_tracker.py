import asyncio
import json
import time
import urllib.request
import urllib.error


class RouterTracker:
    def __init__(self, bng_id: str, event_dispatcher, oss_api_url: str, ping_interval: int = 30):
        self.bng_id = bng_id
        self.event_dispatcher = event_dispatcher
        self.oss_api_url = oss_api_url.rstrip("/")
        self.ping_interval = ping_interval
        # {router_name: {"giaddr": str, "last_seen": float, "is_alive": bool, "next_ping": float}}
        self.routers = {}

    def load_routers(self):
        """Fetch pre-configured routers assigned to this BNG from the OSS API."""
        url = f"{self.oss_api_url}/api/routers?bng_id={self.bng_id}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            print(f"RouterTracker: failed to load routers from {url}: {e}")
            return

        api_routers = {r["router_name"]: r for r in body.get("data", [])}

        # Add new routers from API
        now = time.time()
        for name, r in api_routers.items():
            if name not in self.routers:
                self.routers[name] = {
                    "giaddr": r["giaddr"],
                    "last_seen": 0,
                    "is_alive": False,
                    "next_ping": now,
                }
                print(f"RouterTracker: loaded router {name} ({r['giaddr']})")
            else:
                # Update giaddr in case it changed
                self.routers[name]["giaddr"] = r["giaddr"]

        # Remove routers no longer assigned to this BNG
        removed = [name for name in self.routers if name not in api_routers]
        for name in removed:
            del self.routers[name]
            print(f"RouterTracker: removed router {name} (no longer assigned)")

        print(f"RouterTracker: {len(self.routers)} routers loaded for bng_id={self.bng_id}")

    async def on_dhcp_event(self, event: dict):
        circuit_id = event.get("circuit_id")
        remote_id = event.get("remote_id")
        if not circuit_id and not remote_id:
            return

        name = None
        # New format: remote_id is the access router name.
        if remote_id in self.routers:
            name = remote_id
        # Legacy format: circuit_id starts with "<router>|..."
        elif circuit_id and "|" in circuit_id:
            parts = circuit_id.split("|")
            name = parts[0] if parts[0] else None

        if not name:
            return

        if name not in self.routers:
            return

        r = self.routers[name]
        r["last_seen"] = time.time()
        if not r["is_alive"]:
            r["is_alive"] = True
            await self._dispatch(name, r)
        r["next_ping"] = time.time() + self.ping_interval

    async def _dispatch(self, name: str, info: dict):
        await self.event_dispatcher.dispatch_router_update(
            router_name=name,
            is_alive=info["is_alive"],
            last_seen=info["last_seen"],
        )

    async def check_routers(self):
        """Ping only routers that are overdue for a check."""
        now = time.time()
        for name, info in self.routers.items():
            if now < info["next_ping"]:
                continue
            alive = await self._ping(info["giaddr"])
            info["is_alive"] = alive
            info["next_ping"] = now + self.ping_interval
            await self._dispatch(name, info)

    async def _ping(self, ip: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1", ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await proc.wait()
            return returncode == 0
        except Exception:
            return False
