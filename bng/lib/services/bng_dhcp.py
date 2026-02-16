import ipaddress
import os
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from lib.constants import (
    DHCP_NAK_TERMINATE_COUNT_THRESHOLD,
    TOMBSTONE_EXPIRY_GRACE_SECONDS,
    TOMBSTONE_TTL_SECONDS,
)
from lib.dhcp.lease_service import KeaClient, KeaLeaseService
from lib.dhcp.utils import format_mac
from lib.nftables.helpers import nft_delete_rule_by_handle, nft_list_chain_rules, nft_remove_ip
from lib.radius.session import DHCPSession
from lib.secrets import __KEA_CTRL_AGENT_PASSWORD, __RADIUS_SECRET
from lib.services.bng_session import (
    SessionMap,
    SessionsByIPMap,
    SessionsBySessionIDMap,
    Tombstone,
    TombstoneMap,
    authorize_session,
    decode_bytes,
    get_counters_for_session,
    install_rules_and_baseline,
    terminate_session,
)
from lib.services.event_dispatcher import BNGEventDispatcher
from lib.services.traffic_shaper import BNGTrafficShaper


@dataclass
class DHCPRuntimeState:
    reconcile_handler: Callable[[], Awaitable[None]]
    sessions: SessionMap
    sessions_by_ip: SessionsByIPMap
    sessions_by_session_id: SessionsBySessionIDMap
    tombstones: TombstoneMap
    handle_dhcp_event: Callable[[dict], Awaitable[None]]


def dhcp_lease_handler(
    bng_id: str,
    bng_instance_id: str,
    event_dispatcher: BNGEventDispatcher,
    traffic_shaper: BNGTrafficShaper,
    iface: str = "eth0",
    radius_server_ip: str = "198.18.0.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str = "198.18.0.1",
    nas_port_id: str = "eth0",
    kea_ctrl_agent_auth_key: str = __KEA_CTRL_AGENT_PASSWORD,
) -> DHCPRuntimeState:
    _ = bng_instance_id
    sessions: SessionMap = {}
    sessions_by_ip: SessionsByIPMap = {}
    sessions_by_session_id: SessionsBySessionIDMap = {}
    tombstones: TombstoneMap = {}

    kea_ctrl_url = os.getenv("BNG_KEA_CTRL_URL", "http://198.18.0.3:6772")
    kea_client = KeaClient(base_url=kea_ctrl_url, auth_key=kea_ctrl_agent_auth_key)
    kea_lease_service = KeaLeaseService(kea_client, bng_relay_id=bng_id)

    async def handle_dhcp_request(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        _ = event
        key = (bng_id, circuit_id, remote_id)
        existing_sess = sessions.get(key)
        now = time.time()
        try:
            if chaddr is None or not isinstance(chaddr, str):
                raise RuntimeError("DHCP ACK missing chaddr")

            if existing_sess is None:
                s = DHCPSession(
                    mac=format_mac(chaddr),
                    ip=None,
                    first_seen=now,
                    last_seen=now,
                    expiry=None,
                    iface=iface,
                    hostname=None,
                    last_interim=None,
                    nft_up_handle=None,
                    nft_down_handle=None,
                    base_up_bytes=0,
                    base_down_bytes=0,
                    base_up_pkts=0,
                    base_down_pkts=0,
                    auth_state="PENDING_AUTH",
                    status="PENDING",
                    last_status_change_ts=now,
                    relay_id=bng_id,
                    remote_id=remote_id,
                    circuit_id=circuit_id,
                )
                sessions[key] = s
                sessions_by_session_id[s.session_id] = s
                print(f"Created temp DHCP session for mac={chaddr} circuit: {circuit_id}")
        except Exception as e:
            print(f"Failed to create temp DHCP session for mac={chaddr} circuit: {circuit_id}: {e}")

    async def handle_dhcp_discover(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        ...

    async def handle_dhcp_ack(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (bng_id, circuit_id, remote_id)
        now = time.time()

        try:
            leased_ip: str | None = event.get("ip")
            expiry: int | None = event.get("expiry")

            if expiry is None or expiry <= 0:
                raise RuntimeError("DHCP ACK missing valid expiry")

            if leased_ip is None or not isinstance(leased_ip, str):
                raise RuntimeError("DHCP ACK missing leased IP")

            if chaddr is None or not isinstance(chaddr, str):
                raise RuntimeError("DHCP ACK missing chaddr")

            s = sessions.get(key)
            if s:
                tombstones.pop(key, None)
                s.last_seen = now
                s.expiry = expiry
                s.dhcp_nak_count = 0
                s.mac = format_mac(chaddr)

                if leased_ip == "0.0.0.0":
                    s.ip = None
                    s.status = "PENDING"
                    s.last_status_change_ts = now
                    return

                if leased_ip == s.ip:
                    s.expiry = expiry
                    s.last_seen = now
                    s.status = "ACTIVE"
                    s.last_status_change_ts = now
                    s.last_idle_ts = None
                    s.last_traffic_seen_ts = None
                    return

                if s.ip is not None and s.auth_state == "AUTHORIZED":
                    if s.nft_up_handle is not None:
                        await nft_delete_rule_by_handle(s.nft_up_handle)
                    if s.nft_down_handle is not None:
                        await nft_delete_rule_by_handle(s.nft_down_handle)

                    await terminate_session(
                        s,
                        cause="IP-change",
                        radius_server_ip=radius_server_ip,
                        radius_secret=radius_secret,
                        nas_ip=nas_ip,
                        nas_port_id=nas_port_id,
                        event_dispatcher=event_dispatcher,
                        traffic_shaper=traffic_shaper,
                    )
                    s.nft_up_handle = None
                    s.nft_down_handle = None
                    s.auth_state = "PENDING_AUTH"

                if not leased_ip and (not isinstance(leased_ip, str) or leased_ip == "\x00"):
                    raise RuntimeError(f"DHCP ACK with invalid leased IP: {leased_ip!r}")

                s.ip = leased_ip
                s.first_seen = now
                s.status = "ACTIVE"
                s.last_status_change_ts = now
                sessions_by_ip[s.ip] = s
                await event_dispatcher.dispatch_session_start(s)

                print(f"DHCP SESSION START mac={s.mac} ip={s.ip} iface={iface} hostname={s.hostname}")

                try:
                    result = await authorize_session(
                        s,
                        leased_ip,
                        s.mac,
                        iface,
                        radius_server_ip,
                        radius_secret,
                        nas_ip,
                        nas_port_id,
                        ensure_rules=True,
                        traffic_shaper=traffic_shaper,
                    )
                    if result == "REJECTED":
                        print(f"RADIUS Access-Reject received for mac={s.mac} ip={s.ip}")
                    elif result == "AUTHORIZED":
                        print(f"RADIUS Access-Accept received for mac={s.mac} ip={s.ip}")
                    await event_dispatcher.dispatch_policy_apply(s)
                except Exception as e:
                    print(f"RADIUS Acct-Start failed for mac={s.mac} ip={s.ip}: {e}")
            else:
                print("Found DHCP ACK for unknown session")
        except Exception as e:
            print(f"Failed to handle DHCP ACK for mac={chaddr} circuit: {circuit_id}: {e}")

    async def handle_dhcp_nak(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (bng_id, circuit_id, remote_id)
        s = sessions.get(key)
        if s is not None:
            s.status = "PENDING"
            if s.dhcp_nak_count >= DHCP_NAK_TERMINATE_COUNT_THRESHOLD and s.ip is None:
                ...
            s.dhcp_nak_count += 1

    async def handle_dhcp_release(ip: str):
        now = time.time()
        nftables_snapshot = await nft_list_chain_rules()

        s = sessions_by_ip.pop(ip, None)
        if s is None:
            print(f"DHCP RELEASE for unknown IP: {ip}")
            return

        sessions.pop((bng_id, s.circuit_id, s.remote_id), None)
        sessions_by_session_id.pop(s.session_id, None)
        tombstones[(bng_id, s.circuit_id, s.remote_id)] = Tombstone(
            ip_at_stop=s.ip or "",
            latest_state_update_ts_at_stop=s.expiry or int(time.time()),
            stopped_at=time.time(),
            reason="User-Request",
            missing_seen=False,
        )

        dur = int(now - s.first_seen)
        print(f"DHCP SESSION END mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} duration={dur}s")

        if s.auth_state == "AUTHORIZED":
            if await terminate_session(
                s,
                cause="User-Request",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                nftables_snapshot=nftables_snapshot,
                event_dispatcher=event_dispatcher,
                traffic_shaper=traffic_shaper,
            ):
                print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")

    dhcp_events = {
        1: handle_dhcp_discover,
        3: handle_dhcp_request,
        5: handle_dhcp_ack,
        6: handle_dhcp_nak,
        7: handle_dhcp_release,
    }

    async def handle_dhcp_event(event: dict):
        msg_type = event.get("msg_type")
        if msg_type is None:
            print(f"DHCP event missing message type: {event}")
            return
        event_handler = dhcp_events.get(msg_type)

        circuit_id = decode_bytes(event.get("circuit_id"))
        remote_id = decode_bytes(event.get("remote_id"))
        chaddr = decode_bytes(event.get("chaddr"))
        ip = decode_bytes(event.get("ip"))

        if msg_type == 7:
            if ip is not None:
                print(f"Handling DHCP RELEASE event: {event}")
                await handle_dhcp_release(ip)
            else:
                print(f"Dropped DHCP RELEASE without IP: {event}")
            return

        if event_handler is not None:
            if circuit_id and remote_id and chaddr:
                print(f"Handling DHCP event {event_handler.__name__} event: {event}")
                await event_handler(circuit_id, remote_id, chaddr, event)
            else:
                print(
                    f"Dropped DHCP event missing required fields: msg_type={msg_type} "
                    f"circuit_id={circuit_id} remote_id={remote_id} chaddr={chaddr}"
                )
        else:
            print(
                f"Dropped unsupported DHCP event: {event} msg_type={msg_type} "
                f"circuit_id={circuit_id} remote_id={remote_id} chaddr={chaddr}"
            )

    async def reconcile_handler():
        now = time.time()
        leases = await kea_lease_service.get_all_leases()
        current = {(bng_id, l.circuit_id, l.remote_id): l for l in leases}

        for key, t in list(tombstones.items()):
            expired_by_lease = (
                t.latest_state_update_ts_at_stop
                and now >= (t.latest_state_update_ts_at_stop + TOMBSTONE_EXPIRY_GRACE_SECONDS)
            )
            expired_by_ttl = now - t.stopped_at >= TOMBSTONE_TTL_SECONDS
            if expired_by_lease or expired_by_ttl:
                tombstones.pop(key, None)

        for key, l in current.items():
            tombstone = tombstones.get(key)
            if tombstone is not None:
                lease_changed = l.last_state_update_ts > tombstone.latest_state_update_ts_at_stop
                if not lease_changed:
                    continue
                tombstones.pop(key, None)

            if key not in sessions and l._kea_state == 0:
                try:
                    s = DHCPSession(
                        mac=l.mac,
                        ip=l.ip,
                        first_seen=now,
                        last_seen=now,
                        expiry=l.expiry,
                        iface=iface,
                        hostname=l.hostname,
                        last_interim=now,
                        relay_id=l.relay_id,
                        remote_id=l.remote_id,
                        circuit_id=l.circuit_id,
                        status="ACTIVE",
                    )
                    sessions[key] = s
                    sessions_by_ip[l.ip] = s
                    sessions_by_session_id[s.session_id] = s

                    await install_rules_and_baseline(s, l.ip, l.mac, iface)
                    await event_dispatcher.dispatch_session_start(s)
                    print(f"Reconciler: DHCP SESSION START mac={l.mac} ip={l.ip} iface={iface} hostname={l.hostname}")

                    try:
                        result = await authorize_session(
                            s,
                            l.ip,
                            l.mac,
                            iface,
                            radius_server_ip,
                            radius_secret,
                            nas_ip,
                            nas_port_id,
                            ensure_rules=True,
                            traffic_shaper=traffic_shaper,
                        )
                        if result == "REJECTED":
                            print(f"RADIUS Access-Reject received for mac={l.mac} ip={l.ip}")
                        elif result == "AUTHORIZED":
                            print(f"RADIUS Access-Accept received for mac={l.mac} ip={l.ip}")
                        await event_dispatcher.dispatch_policy_apply(s)
                    except Exception as e:
                        print(f"Reconciler: RADIUS Acct-Start failed for mac={l.mac} ip={l.ip}: {e}")
                except Exception as e:
                    print(f"Reconciler: Failed to create DHCP session for mac={l.mac} ip={l.ip}: {e}")
            else:
                s = sessions[key]

                if s.status == "PENDING" and s.ip is None and now - s.first_seen > 8:
                    s.last_seen = now
                    s.expiry = l.expiry
                    s.dhcp_nak_count = 0

                    if l.ip == s.ip:
                        continue

                    s.ip = l.ip
                    s.first_seen = now
                    s.status = "ACTIVE"
                    s.last_status_change_ts = now

                    await install_rules_and_baseline(s, s.ip, s.mac, iface)
                    await event_dispatcher.dispatch_session_start(s)
                    print(f"DHCP SESSION START mac={s.mac} ip={s.ip} iface={iface} hostname={s.hostname}")

                    try:
                        result = await authorize_session(
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
                        if result == "REJECTED":
                            print(f"RADIUS Access-Reject received for mac={s.mac} ip={s.ip}")
                        elif result == "AUTHORIZED":
                            print(f"RADIUS Access-Accept received for mac={s.mac} ip={s.ip}")
                    except Exception as e:
                        print(f"RADIUS Acct-Start failed for mac={s.mac} ip={s.ip}: {e}")

                    await event_dispatcher.dispatch_policy_apply(s)
                    continue

                if s.expiry is not None and s.expiry != l.expiry:
                    s.expiry = l.expiry

                s.last_seen = now

                if s.ip != l.ip:
                    old_ip, old_expiry, old_session_id = s.ip, s.expiry, s.session_id
                    s.ip, s.expiry, s.hostname = l.ip, l.expiry, l.hostname
                    s.last_idle_ts = None
                    s.status = "ACTIVE"
                    s.last_traffic_seen_ts = None
                    s.last_up_bytes = None
                    s.last_down_bytes = None

                    print(
                        f"DHCP SESSION RENEW mac={l.mac} old_ip={old_ip} new_ip={s.ip} "
                        f"old_expiry={old_expiry} new_expiry={s.expiry} iface={iface} hostname={l.hostname}"
                    )

                    if old_ip:
                        sessions_by_ip.pop(old_ip, None)

                    sessions_by_session_id.pop(old_session_id, None)
                    s.session_id = str(uuid.uuid4())
                    sessions_by_session_id[s.session_id] = s

                    if old_ip:
                        old_session = DHCPSession(
                            session_id=old_session_id,
                            mac=s.mac,
                            ip=old_ip,
                            first_seen=s.first_seen,
                            last_seen=s.last_seen,
                            expiry=old_expiry,
                            iface=s.iface,
                            hostname=s.hostname,
                            last_interim=s.last_interim,
                            relay_id=s.relay_id,
                            remote_id=s.remote_id,
                            circuit_id=s.circuit_id,
                            status=s.status,
                            auth_state=s.auth_state,
                            last_up_bytes=s.last_up_bytes,
                            last_down_bytes=s.last_down_bytes,
                            last_traffic_seen_ts=s.last_traffic_seen_ts,
                        )

                        nftables_snapshot = await nft_list_chain_rules()
                        old_in, old_out, old_in_pkts, old_out_pkts = await get_counters_for_session(
                            old_session, nftables_snapshot
                        )
                        await event_dispatcher.dispatch_session_stop(
                            old_session,
                            input_octets=old_out,
                            output_octets=old_in,
                            input_packets=old_out_pkts,
                            output_packets=old_in_pkts,
                            terminate_cause="IP-change",
                        )

                        ip_clean = str(old_ip).replace("\x00", "")
                        ipaddress.ip_address(ip_clean)
                        await nft_remove_ip(ip_clean)

                        if await terminate_session(
                            old_session,
                            cause="IP-change",
                            radius_server_ip=radius_server_ip,
                            radius_secret=radius_secret,
                            nas_ip=nas_ip,
                            nas_port_id=nas_port_id,
                            nftables_snapshot=nftables_snapshot,
                            event_dispatcher=event_dispatcher,
                            traffic_shaper=traffic_shaper,
                        ):
                            print(f"RADIUS Acct-Stop sent for mac={s.mac} old_ip={old_ip}")

                    sessions_by_ip[s.ip] = s
                    await event_dispatcher.dispatch_session_start(s)

                    reauth_result = await authorize_session(
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

                    if reauth_result == "REJECTED":
                        print(f"RADIUS Access-Reject received for mac={s.mac} new_ip={s.ip}")
                    elif reauth_result == "AUTHORIZED":
                        print(f"RADIUS Access-Accept received for mac={s.mac} new_ip={s.ip}")
                    await event_dispatcher.dispatch_policy_apply(s)

        ended = []
        for key, s in list(sessions.items()):
            l = current.get(key)
            if l is None:
                if s.expiry is not None and now >= s.expiry:
                    ended.append(key)
            elif l._kea_state != 0:
                ended.append(key)

        nftables_snapshot = None
        if ended:
            try:
                nftables_snapshot = await nft_list_chain_rules()
            except Exception as e:
                print(f"Failed to get nftables snapshot for Acct-Stop: {e}")

        for key in ended:
            s = sessions.pop(key)
            if s.ip:
                sessions_by_ip.pop(s.ip, None)
            sessions_by_session_id.pop(s.session_id, None)

            dur = int(now - s.first_seen)
            print(f"Reconciler: DHCP SESSION END mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} duration={dur}s")

            if await terminate_session(
                s,
                cause="Reconcile-Timeout",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                nftables_snapshot=nftables_snapshot,
                event_dispatcher=event_dispatcher,
                traffic_shaper=traffic_shaper,
            ):
                print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")

    return DHCPRuntimeState(
        reconcile_handler=reconcile_handler,
        sessions=sessions,
        sessions_by_ip=sessions_by_ip,
        sessions_by_session_id=sessions_by_session_id,
        tombstones=tombstones,
        handle_dhcp_event=handle_dhcp_event,
    )
