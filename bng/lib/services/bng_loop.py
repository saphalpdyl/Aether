import asyncio
import contextlib
import os
import time
from typing import Any

import redis.asyncio as aioredis

from lib.constants import ENABLE_IDLE_DISCONNECT, MARK_DISCONNECT_GRACE_SECONDS
from lib.nftables.helpers import nft_list_chain_rules
from lib.radius.handlers import radius_handle_interim_updates
from lib.secrets import __RADIUS_SECRET
from lib.services.bng_coad import handle_coad_connection
from lib.services.bng_dhcp import dhcp_lease_handler
from lib.services.bng_health_tracker import BNGHealthTracker
from lib.services.bng_session import (
    Tombstone,
    authorize_session,
    remove_session_from_maps,
    terminate_session,
)
from lib.services.event_dispatcher import BNGEventDispatcher, BNGEventDispatcherConfig
from lib.services.traffic_shaper import BNGTrafficShaper, BNGTrafficShaperConfig
from lib.services.router_tracker import RouterTracker

COA_IPC_SOCKET = os.getenv("COA_IPC_SOCKET", "/tmp/coad.sock")

# Remove OSS API URL. BNG should not be calling OSS.
OSS_API_URL = os.getenv("OSS_API_URL", "http://192.0.2.21:8000")


async def bng_event_loop(
    event_queue: asyncio.PriorityQueue,
    *,
    redis_conn: aioredis.Redis | None = None,
    iface: str = "eth1",
    uplink_iface: str = "eth2",
    interim_interval: int = 30,
    auth_retry_interval: int = 10,
    disconnection_check_interval: int = 5,
    reconciler_interval: int = 15,
    router_ping_interval: int = 30,
    bng_health_check_interval: int = 5,
    radius_server_ip: str = "192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str = "192.0.2.1",
    nas_port_id: str = "eth1",
    bng_id: str = "bng-default",
    bng_instance_id: str = "",
) -> None:
    event_dispatcher = BNGEventDispatcher(
        config=BNGEventDispatcherConfig(
            bng_id=bng_id,
            bng_instance_id=bng_instance_id,
            nas_ip=nas_ip,
            redis_conn=redis_conn,
            print_dispatched_events=True,
        )
    )

    traffic_shaper = BNGTrafficShaper(
        config=BNGTrafficShaperConfig(
            bandwidth_limit=100000,
            bng_id=bng_id,
            bng_instance_id=bng_instance_id,
            subscriber_facing_interface=iface,
            uplink_interface=uplink_iface,
            debug_mode=True,
        )
    )

    router_tracker = RouterTracker(bng_id=bng_id, event_dispatcher=event_dispatcher, oss_api_url=OSS_API_URL)
    router_tracker.load_routers()

    bng_health_tracker = BNGHealthTracker(bng_id=bng_id, event_dispatcher=event_dispatcher)
    await bng_health_tracker.check_and_dispatch()

    dhcp_runtime = dhcp_lease_handler(
        bng_id,
        bng_instance_id,
        iface=iface,
        radius_server_ip=radius_server_ip,
        radius_secret=radius_secret,
        nas_ip=nas_ip,
        nas_port_id=nas_port_id,
        event_dispatcher=event_dispatcher,
        traffic_shaper=traffic_shaper,
    )

    socket_path = COA_IPC_SOCKET
    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        pass

    command_queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=2048)

    async def periodic_enqueue(command: str, interval: int) -> None:
        while True:
            await asyncio.sleep(interval)
            await command_queue.put((command, {}))

    async def handle_coad_request(request: dict[str, Any]) -> dict[str, Any]:
        action = request.get("action")
        session_id = request.get("session_id")

        if not session_id:
            return {"success": False, "error": "missing session_id"}

        session = dhcp_runtime.sessions_by_session_id.get(session_id)
        if session is None:
            return {"success": False, "error": f"session not found: {session_id}"}

        if action == "disconnect":
            ok = await terminate_session(
                session,
                cause="Admin-Reset",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                event_dispatcher=event_dispatcher,
                traffic_shaper=traffic_shaper,
            )
            if ok:
                remove_session_from_maps(
                    session,
                    dhcp_runtime.sessions,
                    dhcp_runtime.sessions_by_ip,
                    dhcp_runtime.sessions_by_session_id,
                    dhcp_runtime.tombstones,
                    bng_id,
                    reason="Admin-Reset",
                )
            return {"success": ok}

        if action == "policy_change":
            filter_id = request.get("filter_id", "")
            print(f"CoA policy_change received for session={session_id} filter_id={filter_id}")
            return {"success": True}

        return {"success": False, "error": f"unknown action: {action}"}

    async def handle_command(command: str, payload: dict[str, Any]) -> None:
        if command == "interim":
            try:
                await radius_handle_interim_updates(
                    dhcp_runtime.sessions,
                    radius_server_ip=radius_server_ip,
                    radius_secret=radius_secret,
                    nas_ip=nas_ip,
                    nas_port_id=nas_port_id,
                    event_dispatcher=event_dispatcher,
                )
            except Exception as e:
                print(f"BNG Interim-Update error: {e}")
            return

        if command == "reconcile":
            try:
                await dhcp_runtime.reconcile_handler()
            except Exception as e:
                print(f"BNG Reconcile error: {e}")
            return

        if command == "auth_retry":
            try:
                for s in dhcp_runtime.sessions.values():
                    if s.auth_state != "PENDING_AUTH" or s.status == "PENDING" or s.ip is None:
                        continue
                    await authorize_session(
                        s,
                        s.ip,
                        s.mac,
                        iface,
                        radius_server_ip,
                        radius_secret,
                        nas_ip,
                        nas_port_id,
                        ensure_rules=True,
                        traffic_shaper=traffic_shaper,
                    )
            except Exception as e:
                print(f"BNG Auth-Retry error: {e}")
            return

        if command == "disconnection_check":
            if not ENABLE_IDLE_DISCONNECT:
                return
            try:
                nftables_snapshot = None
                if dhcp_runtime.sessions:
                    try:
                        nftables_snapshot = await nft_list_chain_rules()
                    except Exception as e:
                        print(f"Failed to get nftables snapshot for IDLE disconnect: {e}")
                        nftables_snapshot = None

                for key, s in list(dhcp_runtime.sessions.items()):
                    if s.status == "IDLE" and s.last_idle_ts is not None:
                        idle_duration = time.time() - s.last_idle_ts
                        if idle_duration >= MARK_DISCONNECT_GRACE_SECONDS:
                            print(
                                f"DHCP IDLE SESSION DISCONNECT mac={s.mac} ip={s.ip} "
                                f"iface={s.iface} hostname={s.hostname} idle_duration={int(idle_duration)}s"
                            )
                            await terminate_session(
                                s,
                                cause="Idle-Timeout",
                                radius_server_ip=radius_server_ip,
                                radius_secret=radius_secret,
                                nas_ip=nas_ip,
                                nas_port_id=nas_port_id,
                                nftables_snapshot=nftables_snapshot,
                                event_dispatcher=event_dispatcher,
                                traffic_shaper=traffic_shaper,
                            )
                            dhcp_runtime.tombstones[key] = Tombstone(
                                ip_at_stop=s.ip or "",
                                latest_state_update_ts_at_stop=s.expiry or int(time.time()),
                                stopped_at=time.time(),
                                reason="Idle-Timeout",
                                missing_seen=False,
                            )
                            dhcp_runtime.sessions_by_session_id.pop(s.session_id, None)
                            dhcp_runtime.sessions.pop(key)
            except Exception as e:
                print(f"BNG Disconnection check error: {e}")
            return

        if command == "router_config_refresh":
            try:
                router_tracker.load_routers()
            except Exception as e:
                print(f"BNG Router-Config-Refresh error: {e}")
            return

        if command == "router_ping":
            try:
                await router_tracker.check_routers()
            except Exception as e:
                print(f"BNG Router-Ping error: {e}")
            return

        if command == "bng_health":
            try:
                await bng_health_tracker.check_and_dispatch()
            except Exception as e:
                print(f"BNG BNG-Health check error: {e}")
            return

        if command == "coad_request":
            response_future = payload.get("response_future")
            try:
                response = await handle_coad_request(payload.get("request", {}))
            except Exception as e:
                response = {"success": False, "error": str(e)}
            if response_future is not None and not response_future.done():
                response_future.set_result(response)
            return

        print(f"Unknown command received: {command}")

    coad_server = await asyncio.start_unix_server(
        lambda r, w: handle_coad_connection(r, w, command_queue=command_queue),
        path=socket_path,
    )
    print(f"Coad IPC server listening on {socket_path}")

    periodic_tasks = [
        asyncio.create_task(periodic_enqueue("interim", interim_interval)),
        asyncio.create_task(periodic_enqueue("reconcile", reconciler_interval)),
        asyncio.create_task(periodic_enqueue("auth_retry", auth_retry_interval)),
        asyncio.create_task(periodic_enqueue("disconnection_check", disconnection_check_interval)),
        asyncio.create_task(periodic_enqueue("router_config_refresh", 60)),
        asyncio.create_task(periodic_enqueue("router_ping", router_ping_interval)),
        asyncio.create_task(periodic_enqueue("bng_health", bng_health_check_interval)),
    ]

    async def process_event_item(event: tuple[Any, Any, Any]) -> None:
        _, _, event_dict = event
        if isinstance(event_dict, dict) and event_dict.get("event") == "dhcp":
            try:
                await dhcp_runtime.handle_dhcp_event(event_dict)
                await router_tracker.on_dhcp_event(event_dict)
                await command_queue.put(("reconcile", {"reason": "dhcp_event"}))
            except Exception as e:
                print(f"BNG DHCP event processing error: {e}")

    try:
        while True:
            event_get = asyncio.create_task(event_queue.get())
            command_get = asyncio.create_task(command_queue.get())

            done, pending = await asyncio.wait(
                {event_get, command_get},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            if command_get in done:
                command, payload = command_get.result()
                await handle_command(command, payload)

            if event_get in done:
                await process_event_item(event_get.result())
    finally:
        coad_server.close()
        await coad_server.wait_closed()
        for task in periodic_tasks:
            task.cancel()
        for task in periodic_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
