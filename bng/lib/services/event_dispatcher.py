from enum import Enum
import time
import redis.asyncio as aioredis
from dataclasses import dataclass

from lib.radius.session import DHCPSession
from lib.constants import EVENT_DISPATCHER_STREAM_ID

@dataclass
class BNGEventDispatcherConfig:
    """
    Configuration for BNGEventDispatcher.
        - bng_id: Unique identifier for this BNG instance (persistent across restarts)
        - bng_instance_id: UUID for this specific run of the BNG (changes on restart)
        - redis_conn: Redis connection to use for dispatching events. Required if test_mode is False.
        - test_mode: If True, events will be printed to the console instead of being dispatched to Redis.
    """

    bng_id: str
    bng_instance_id: str
    nas_ip: str # bng_ip
    redis_conn: aioredis.Redis | None = None
    test_mode: bool = False
    print_dispatched_events: bool = False

def acct_user_name(s: DHCPSession) -> str:
    return f"{s.relay_id}/{s.remote_id}/{s.circuit_id}"

class BNGDispatcherEventType(Enum):
    SESSION_START = "SESSION_START"
    SESSION_UPDATE = "SESSION_UPDATE"
    SESSION_STOP = "SESSION_STOP"
    POLICY_APPLY = "POLICY_APPLY"
    ROUTER_UPDATE = "ROUTER_UPDATE"
    BNG_HEALTH_UPDATE = "BNG_HEALTH_UPDATE"

class BNGEventDispatcher:
    redis_conn: aioredis.Redis | None
    config: BNGEventDispatcherConfig
    seq: int # Used for idempotency and ordering gurantees in event dispatch for ingestor

    def __init__(self, config: BNGEventDispatcherConfig) -> None:
        self.config = config
        self.seq = 0

        if config.test_mode:
            print("BNGEventDispatcher initialized in test mode. Events will be printed to console.")
            return

        if self.config.redis_conn is None:
            raise ValueError("redis_conn must be provided")

        self.redis_conn = self.config.redis_conn

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    async def __dispatch_event_to_redis(self, event_type: BNGDispatcherEventType, event_data: dict) -> None:
        """Dispatch an event to Redis stream."""

        if self.config.print_dispatched_events:
            print(f"Dispatching event to Redis: {event_type.value} data={event_data}")

        assert self.redis_conn is not None

        await self.redis_conn.xadd(EVENT_DISPATCHER_STREAM_ID, event_data)

    # Prepares common event data and dispatches to either stdout or streams
    async def _dispatch_event(self, event_type: BNGDispatcherEventType, s: DHCPSession,  event_data: dict) -> None:
        event_data["bng_id"] = self.config.bng_id
        event_data["bng_instance_id"] = self.config.bng_instance_id

        event_data["seq"] = str(self._next_seq())

        event_data["event_type"] = event_type.value

        event_data["ts"] = str(time.time())
        event_data["session_last_update"] = str(time.time())

        event_data["nas_ip"] = self.config.nas_ip

        event_data["session_id"] = s.session_id
        event_data["access_key"] = s.access_key()

        # Opt 82
        event_data["remote_id"] = s.remote_id
        event_data["circuit_id"] = s.circuit_id

        # Status
        event_data["auth_state"] = s.auth_state
        event_data["status"] = s.status


        if self.config.test_mode:
            print(f"Dispatching event: {event_type.value} data={event_data}")
        else:
            await self.__dispatch_event_to_redis(event_type, event_data)

    def _username(self, s: DHCPSession) -> str:
        return acct_user_name(s)

    async def dispatch_session_start(self, s: DHCPSession) -> None:
        if not s.mac:
            raise ValueError("session mac address is required")
        if not s.ip:
            raise ValueError("session ip address is required")

        await self._dispatch_event(BNGDispatcherEventType.SESSION_START,s,  {
            "mac_address": s.mac,
            "ip_address": s.ip,
            "username": self._username(s),
            "input_octets": "0",
            "output_octets": "0",
            "input_packets": "0",
            "output_packets": "0",
            "session_start": str(time.time()),
        })

    async def dispatch_session_update(
        self,
        s: DHCPSession,
        input_octets: int,
        output_octets: int,
        input_packets: int,
        output_packets: int,
    ) -> None:
        if not s.mac:
            raise ValueError("session mac address is required")
        if not s.ip:
            raise ValueError("session ip address is required")

        await self._dispatch_event(BNGDispatcherEventType.SESSION_UPDATE, s, {
            "mac_address": s.mac,
            "ip_address": s.ip,
            "username": self._username(s),
            "input_octets": str(input_octets),
            "output_octets": str(output_octets) ,
            "input_packets": str(input_packets),
            "output_packets": str(output_packets),
        })

    async def dispatch_session_stop(
        self,
        s: DHCPSession,
        input_octets: int,
        output_octets: int,
        input_packets: int,
        output_packets: int,
        terminate_cause: str,
    ) -> None:
        if not s.mac:
            raise ValueError("session mac address is required")
        if not s.ip:
            raise ValueError("session ip address is required")

        await self._dispatch_event(BNGDispatcherEventType.SESSION_STOP, s, {
            "mac_address": s.mac,
            "ip_address": s.ip,
            "username": self._username(s),
            "input_octets": str(input_octets),
            "output_octets": str(output_octets),
            "input_packets": str(input_packets),
            "output_packets": str(output_packets),
            "terminate_cause": terminate_cause,
            "session_end": str(time.time()),
        })

    async def dispatch_router_update(self, router_name: str, is_alive: bool, last_seen: float) -> None:
        event_data = {
            "bng_id": self.config.bng_id,
            "bng_instance_id": self.config.bng_instance_id,
            "seq": str(self._next_seq()),
            "event_type": BNGDispatcherEventType.ROUTER_UPDATE.value,
            "ts": str(time.time()),
            "router_name": router_name,
            "is_alive": str(is_alive),
            "last_seen": str(last_seen),
        }

        if self.config.test_mode:
            print(f"Dispatching event: ROUTER_UPDATE data={event_data}")
        else:
            await self.__dispatch_event_to_redis(BNGDispatcherEventType.ROUTER_UPDATE, event_data)

    async def dispatch_policy_apply(self, s: DHCPSession) -> None:
        if not s.mac:
            raise ValueError("session mac address is required")

        await self._dispatch_event(BNGDispatcherEventType.POLICY_APPLY, s, {
            "mac_address": s.mac,
            "ip_address": s.ip or "",
            "username": self._username(s),
        })

    # BNG Health
    async def dispatch_bng_health_update(self, cpu_usage: float, mem_usage: float, mem_max: float, first_seen: bool = False) -> None:
        event_data = {
            "bng_id": self.config.bng_id,
            "bng_instance_id": self.config.bng_instance_id,
            "seq": str(self._next_seq()),
            "event_type": "BNG_HEALTH_UPDATE",
            "ts": str(time.time()),
            "cpu_usage": str(cpu_usage),
            "mem_usage": str(mem_usage),
            "mem_max": str(mem_max),
        }

        if first_seen:
            event_data["first_seen"] = str(time.time());

        if self.config.test_mode:
            print(f"Dispatching event: BNG_HEALTH_UPDATE data={event_data}")
        else:
            await self.__dispatch_event_to_redis(BNGDispatcherEventType.BNG_HEALTH_UPDATE, event_data)
