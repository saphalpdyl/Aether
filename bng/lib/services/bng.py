from os import wait
import re
import time
import threading
from queue import Queue, Empty
from typing import Callable, Dict, Tuple, List
from dataclasses import dataclass
import uuid

import redis


from lib.services.event_dispatcher import BNGEventDispatcher, BNGEventDispatcherConfig
from lib.services.router_tracker import RouterTracker
from lib.dhcp.lease import DHCPLease
from lib.dhcp.utils import parse_dhcp_leases, format_mac
from lib.nftables.helpers import nft_add_subscriber_rules, nft_allow_ip, nft_delete_rule_by_handle, nft_get_counter_by_handle, nft_list_chain_rules, nft_remove_ip
import ipaddress
from lib.radius.packet_builders import build_access_request, build_acct_start, build_acct_stop, rad_acct_send_from_bng, rad_auth_send_from_bng
from lib.radius.session import DHCPSession
from lib.secrets import __RADIUS_SECRET, __KEA_CTRL_AGENT_PASSWORD
from lib.constants import DHCP_NAK_TERMINATE_COUNT_THRESHOLD, DHCP_LEASE_FILE_PATH, MARK_DISCONNECT_GRACE_SECONDS, ENABLE_IDLE_DISCONNECT, TOMBSTONE_TTL_SECONDS, TOMBSTONE_EXPIRY_GRACE_SECONDS
from lib.radius.handlers import radius_handle_interim_updates
from lib.dhcp.lease_service import KeaClient, KeaLeaseService

def _decode_bytes(v):
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    return str(v)

@dataclass
class Tombstone:
    ip_at_stop: str
    latest_state_update_ts_at_stop: int
    stopped_at: float
    reason: str
    missing_seen: bool = False


def _install_rules_and_baseline(s: DHCPSession, ip: str, mac: str, iface: str) -> None:
    try:

        up_handle, down_handle = nft_add_subscriber_rules(ip=ip, mac=mac, sub_if=iface)
        s.nft_up_handle = up_handle
        s.nft_down_handle = down_handle

        snapshot = nft_list_chain_rules()
        base_up_bytes, base_up_pkts = nft_get_counter_by_handle(snapshot, up_handle) or (0,0)
        base_down_bytes, base_down_pkts = nft_get_counter_by_handle(snapshot, down_handle) or (0,0)
        s.base_up_bytes = base_up_bytes
        s.base_down_bytes = base_down_bytes
        s.base_up_pkts = base_up_pkts
        s.base_down_pkts = base_down_pkts
    except Exception as e:
        print(f"Failed to install nftables rules for mac={mac} ip={ip}: {e}")


def _authorize_session(
    s: DHCPSession,
    ip: str,
    mac: str,
    iface: str,
    radius_server_ip: str,
    radius_secret: str,
    nas_ip: str,
    nas_port_id: str,
    ensure_rules: bool = False,
) -> str | None:
    access_request_pkt = build_access_request(s, nas_ip=nas_ip, nas_port_id=nas_port_id)
    access_request_response = rad_auth_send_from_bng(access_request_pkt, server_ip=radius_server_ip, secret=radius_secret)

    if not access_request_response:
        raise RuntimeError(f"RADIUS Access-Request unexpected response: {access_request_response}")

    if re.search(r'Access-Reject', access_request_response):
        s.auth_state = "REJECTED"
        return "REJECTED"

    if re.search(r'Access-Accept', access_request_response):
        if ensure_rules and (s.nft_up_handle is None or s.nft_down_handle is None):
            _install_rules_and_baseline(s, ip, mac, iface)
        s.auth_state = "AUTHORIZED"
        if ip:
            try:
                ip_clean = str(ip).replace("\x00", "")
                ipaddress.ip_address(ip_clean)
                nft_allow_ip(ip_clean)
            except Exception:
                print(f"Skip nft allow: invalid ip={ip!r}")

        acct_start_pkt = build_acct_start(s, nas_ip=nas_ip, nas_port_id=nas_port_id)
        rad_acct_send_from_bng(acct_start_pkt, server_ip=radius_server_ip, secret=radius_secret)

        print(f"RADIUS Acct-Start sent for mac={s.mac} ip={s.ip}")
        return "AUTHORIZED"
    return None

def get_counters_for_session(s: DHCPSession, nftables_snapshot=None) -> Tuple[int,int,int,int]:
    """
        Get total in octets, out octets, in pkts, out pkts for the session by reading nftables counters and calculating deltas from baseline.
        Returns:
            (total_in_octets, total_out_octets, total_in_pkts, total_out_pkts)
    """

    if nftables_snapshot is None:
        nftables_snapshot = nft_list_chain_rules()

    up_bytes, up_pkts = 0, 0
    down_bytes, down_pkts = 0, 0

    if s.nft_up_handle is not None:
        up_bytes, up_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_up_handle) or (0,0)
    if s.nft_down_handle is not None:
        down_bytes, down_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_down_handle) or (0,0)

    total_in_octets = max(0, up_bytes - s.base_up_bytes)
    total_out_octets = max(0, down_bytes - s.base_down_bytes)
    total_in_pkts = max(0, up_pkts - s.base_up_pkts)
    total_out_pkts = max(0, down_pkts - s.base_down_pkts)

    return total_in_octets, total_out_octets, total_in_pkts, total_out_pkts

def terminate_session(
    s: DHCPSession,
    cause: str,
    radius_server_ip: str,
    radius_secret: str,
    nas_ip: str,
    nas_port_id: str,
    nftables_snapshot=None,
    delete_rules: bool = True,
    event_dispatcher: BNGEventDispatcher | None = None,
) -> bool:
    try:
        if nftables_snapshot is None:
            nftables_snapshot = nft_list_chain_rules()

        total_in_octets, total_out_octets, total_in_pkts, total_out_pkts = get_counters_for_session(s, nftables_snapshot)

        if s.auth_state == "AUTHORIZED":
            pkt = build_acct_stop(s, nas_ip=nas_ip, nas_port_id=nas_port_id, cause=cause, 
                input_bytes=total_in_octets,
                output_bytes=total_out_octets,
                input_pkts=total_in_pkts,
                output_pkts=total_out_pkts,
            )
            rad_acct_send_from_bng(pkt, server_ip=radius_server_ip, secret=radius_secret)
            s.auth_state = "PENDING_AUTH"

        # Remove rulesets allowing traffic 
        if s.mac is not None:
            if s.ip:
                try:
                    ip_clean = str(s.ip).replace("\x00", "")
                    ipaddress.ip_address(ip_clean)
                    nft_remove_ip(ip_clean)
                except Exception:
                    print(f"Skip nft remove: invalid ip={s.ip!r}")

        if delete_rules:
            if s.nft_up_handle is not None:
                nft_delete_rule_by_handle(s.nft_up_handle)
            if s.nft_down_handle is not None:
                nft_delete_rule_by_handle(s.nft_down_handle)

        # Dispatch event
        if event_dispatcher is not None:
            event_dispatcher.dispatch_session_stop(
                s,
                input_octets=total_in_octets,
                output_octets=total_out_octets,
                input_packets=total_in_pkts,
                output_packets=total_out_pkts,
                terminate_cause=cause,
            )

        return True
    except Exception as e:
        print(f"RADIUS Acct-Stop failed for mac={s.mac} ip={s.ip}: {e}")
        return False


def dhcp_lease_handler(
    bng_id: str,
    bng_instance_id: str,
    event_dispatcher: BNGEventDispatcher,
    iface: str="eth0",
    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="eth0",
    kea_ctrl_agent_auth_key: str = __KEA_CTRL_AGENT_PASSWORD,
):
    sessions: Dict[Tuple[str,str,str], DHCPSession] = {}

    # Multimap pointing to the same session by IP
    # DHCPRELEASE doesn't container opt82 information so we need lookup by IP
    sessions_by_ip: Dict[str, DHCPSession] = {}

    tombstones: Dict[Tuple[str,str,str], Tombstone] = {} # NOTE: Used only when ENABLE_IDLE_DISCONNECT = True

    _kea_client = KeaClient(base_url=f"http://192.0.2.3:6772", auth_key=kea_ctrl_agent_auth_key)
    _kea_lease_service = KeaLeaseService(_kea_client, bng_relay_id=bng_id)

    def handle_dhcp_request(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (bng_id,circuit_id,remote_id)
        existing_sess = sessions.get(key)
        now = time.time()
        try:
            if chaddr is None or isinstance(chaddr, str) is False:
                raise RuntimeError("DHCP ACK missing chaddr")

            if existing_sess is None:
                # Creating an empty session for tracking
                sessions[key] = DHCPSession(
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
                print(f"Created temp DHCP session for mac={chaddr} circuit: {circuit_id}")

        except Exception as e:
            print(f"Failed to create temp DHCP session for mac={chaddr} circuit: {circuit_id}: {e}")
            
    
    def handle_dhcp_discover(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        ...

    def handle_dhcp_ack(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (bng_id,circuit_id,remote_id)
        now = time.time()

        try:
            leased_ip: str | None = event.get("ip")
            expiry: int | None = event.get("expiry")

            if expiry is None or expiry <= 0:
                raise RuntimeError("DHCP ACK missing valid expiry")

            if leased_ip is None or isinstance(leased_ip, str) is False:
                raise RuntimeError("DHCP ACK missing leased IP")

            if chaddr is None or isinstance(chaddr, str) is False:
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
                    # Renew with same IP
                    s.expiry = expiry
                    s.last_seen = now
                    s.status = "ACTIVE"
                    s.last_status_change_ts = now
                    s.last_idle_ts = None
                    s.last_traffic_seen_ts = None
                    return

                if s.ip is not None and s.auth_state == "AUTHORIZED":
                    # Renew with IP change; Accounting restart required
                    if s.nft_up_handle is not None:
                        nft_delete_rule_by_handle(s.nft_up_handle)
                    if s.nft_down_handle is not None:
                        nft_delete_rule_by_handle(s.nft_down_handle)

                    terminate_session( # Dispatches session stop automatically
                        s,
                        cause="IP-change",
                        radius_server_ip=radius_server_ip,
                        radius_secret=radius_secret,
                        nas_ip=nas_ip,
                        nas_port_id=nas_port_id,
                        event_dispatcher=event_dispatcher
                    )
                    s.nft_up_handle = None
                    s.nft_down_handle = None
                    s.auth_state = "PENDING_AUTH"

                if not leased_ip and (not isinstance(leased_ip, str) or leased_ip == "\x00") :
                    raise RuntimeError(f"DHCP ACK with invalid leased IP: {leased_ip!r}")

                # Create new session
                s.ip = leased_ip
                s.first_seen = now
                s.status = "ACTIVE"
                s.last_status_change_ts = now

                # Create a by IP index
                sessions_by_ip[s.ip] = s

                # Dispatch event for session start before RADIUS auth
                event_dispatcher.dispatch_session_start(s)

                print(f"DHCP SESSION START mac={s.mac} ip={s.ip} iface={iface} hostname={s.hostname}")

                try:
                    result = _authorize_session(
                        s,
                        leased_ip,
                        s.mac,
                        iface,
                        radius_server_ip,
                        radius_secret,
                        nas_ip,
                        nas_port_id,
                        ensure_rules=True,
                    )
                    if result == "REJECTED":
                        print(f"RADIUS Access-Reject received for mac={s.mac} ip={s.ip}")
                    elif result == "AUTHORIZED":
                        print(f"RADIUS Access-Accept received for mac={s.mac} ip={s.ip}")

                    event_dispatcher.dispatch_policy_apply(s)
                except Exception as e:
                    print(f"RADIUS Acct-Start failed for mac={s.mac} ip={s.ip}: {e}")
            else:
                print("Found DHCP ACK for unknown session")


        except Exception as e:
            print(f"Failed to handle DHCP ACK for mac={chaddr} circuit: {circuit_id}: {e}")
            return


    def handle_dhcp_nak(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (bng_id,circuit_id,remote_id)
        now = time.time()
        
        s = sessions.get(key)

        if s is not None:
            # Do nothing
            s.status = "PENDING"

            if s.dhcp_nak_count >= DHCP_NAK_TERMINATE_COUNT_THRESHOLD and s.ip is None:
                ...

            s.dhcp_nak_count += 1
            ...

    def handle_dhcp_release(ip: str):
        key = ip
        now = time.time()
        nftables_snapshot = nft_list_chain_rules()

        s = sessions_by_ip.pop(key, None) # Lookup by IP
        if s is None:
            print(f"DHCP RELEASE for unknown IP: {ip}")
            return

        sessions.pop((bng_id, s.circuit_id, s.remote_id), None) # Remove reference from main sessions map

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
            if terminate_session(
                s,
                cause="User-Request",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                nftables_snapshot=nftables_snapshot,
                event_dispatcher=event_dispatcher,
            ):
                print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")


    dhcp_events = {
        1: handle_dhcp_discover,
        3: handle_dhcp_request,
        5: handle_dhcp_ack,
        6: handle_dhcp_nak,
        7: handle_dhcp_release, # SPECIAL CASE | No Option 82 parameters
    }

    def handle_dhcp_event(event: dict):
        msg_type = event.get("msg_type")
        if msg_type is None:
            print(f"DHCP event missing message type: {event}")
            return 
        event_handler = dhcp_events.get(msg_type)
        
        circuit_id = _decode_bytes(event.get("circuit_id"))
        remote_id = _decode_bytes(event.get("remote_id"))
        chaddr = _decode_bytes(event.get("chaddr"))
        ip = _decode_bytes(event.get("ip"))

        if event_handler is not None:
            if msg_type == 7 and ip is not None:
                print(f"Hanling DHCP RELEASE event: {event}")
                handle_dhcp_release(ip)

            if circuit_id and remote_id and chaddr:
                print(f"Handling DHCP event {event_handler.__name__} event: {event}")
                event_handler(circuit_id, remote_id, chaddr, event)
        else:
            print(f"Dropped unsupported DHCP event: {event} msg_type={msg_type} circuit_id={circuit_id} remote_id={remote_id} chaddr={chaddr}")

    def reconcile_handler():
        now = time.time()
        leases = _kea_lease_service.get_all_leases()

        current = {(bng_id, l.circuit_id, l.remote_id): l for l in leases}

        for key, t in list(tombstones.items()):
            expired_by_lease = t.latest_state_update_ts_at_stop and now >= (t.latest_state_update_ts_at_stop + TOMBSTONE_EXPIRY_GRACE_SECONDS)
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
                    sessions[key] = DHCPSession(
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
                    sessions_by_ip[l.ip] = sessions[key]

                    _install_rules_and_baseline(sessions[key], l.ip, l.mac, iface)
                    event_dispatcher.dispatch_session_start(sessions[key])

                    print(f"Reconciler: DHCP SESSION START mac={l.mac} ip={l.ip} iface={iface} hostname={l.hostname}")

                    try:
                        result = _authorize_session(
                            sessions[key],
                            l.ip,
                            l.mac,
                            iface,
                            radius_server_ip,
                            radius_secret,
                            nas_ip,
                            nas_port_id,
                        )
                        if result == "REJECTED":
                            print(f"RADIUS Access-Reject received for mac={l.mac} ip={l.ip}")
                        elif result == "AUTHORIZED":
                            print(f"RADIUS Access-Accept received for mac={l.mac} ip={l.ip}")

                        event_dispatcher.dispatch_policy_apply(sessions[key])
                    except Exception as e:
                        print(f"Reconciler: RADIUS Acct-Start failed for mac={l.mac} ip={l.ip}: {e}")


                except Exception as e:
                    print(f"Reconciler: Failed to create DHCP session for mac={l.mac} ip={l.ip}: {e}")
            else:
                s = sessions[key]
                
                # Case 0: Temp session with no IP yet assigned
                if s.status == "PENDING" and s.ip is None:
                    # Give 8 seconds grace for DHCP ACK to arrive otherwise create session
                    if now - s.first_seen > 8:
                        s.last_seen = now
                        s.expiry = l.expiry
                        s.dhcp_nak_count = 0

                        if l.ip == s.ip: 
                            # total_in_octets, total_out_octets, total_in_pkts, total_out_pkts = get_counters_for_session(s)

                            # event_dispatcher.dispatch_session_update(
                            #     s,
                            #     input_octets=total_in_octets,
                            #     output_octets=total_out_octets,
                            #     input_packets=total_in_pkts,
                            #     output_packets=total_out_pkts,
                            # )
                            # Already have this lease assigned
                            continue

                        s.ip = l.ip
                        s.first_seen = now
                        s.status = "ACTIVE"
                        s.last_status_change_ts = now

                        _install_rules_and_baseline(s, s.ip, s.mac, iface)
                        event_dispatcher.dispatch_session_start(s)

                        print(f"DHCP SESSION START mac={s.mac} ip={s.ip} iface={iface} hostname={s.hostname}")

                        try:
                            result = _authorize_session(
                                s,
                                s.ip,
                                s.mac,
                                iface,
                                radius_server_ip,
                                radius_secret,
                                nas_ip,
                                nas_port_id,
                            )
                            if result == "REJECTED":
                                print(f"RADIUS Access-Reject received for mac={s.mac} ip={s.ip}")
                            elif result == "AUTHORIZED":
                                print(f"RADIUS Access-Accept received for mac={s.mac} ip={s.ip}")
                        except Exception as e:
                            print(f"RADIUS Acct-Start failed for mac={s.mac} ip={s.ip}: {e}")

                        event_dispatcher.dispatch_policy_apply(s)

                        continue

                # Case A: Lease renewed ( expiry extended ) but missed DHCP packet
                if s.expiry is not None and s.expiry != l.expiry:
                    s.expiry = l.expiry

                s.last_seen = now

                total_in_octets, total_out_octets, total_in_pkts, total_out_pkts = get_counters_for_session(s)

                # Case B: Lease changed ( IP changed )
                if s.ip != l.ip:
                    old_ip, old_expiry, old_session_id = s.ip, s.expiry, s.session_id
                    s.ip, s.expiry, s.hostname = l.ip, l.expiry, l.hostname


                    # Remove idle status on renew
                    s.last_idle_ts = None
                    s.status = "ACTIVE"
                    s.last_traffic_seen_ts = None
                    s.last_up_bytes = None
                    s.last_down_bytes = None

                    print(f"DHCP SESSION RENEW mac={l.mac} old_ip={old_ip} new_ip={s.ip} old_expiry={old_expiry} new_expiry={s.expiry} iface={iface} hostname={l.hostname}")

                    # Renew with IP change means a new session
                    if old_ip:
                        sessions_by_ip.pop(old_ip, None)

                    old_session = DHCPSession(
                        session_id=old_session_id, # New session ID will be generated for the updated session; keep old one for accurate event correlation in case of IP change
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

                    # Regenerating the session_id 
                    s.session_id = str(uuid.uuid4())

                    nftables_snapshot = nft_list_chain_rules()
                    total_in_octets, total_out_octets, total_in_pkts, total_out_pkts = get_counters_for_session(old_session, nftables_snapshot)
                    event_dispatcher.dispatch_session_stop(old_session, input_octets=total_in_octets, output_octets=total_out_octets, input_packets=total_in_pkts, output_packets=total_out_pkts, terminate_cause="IP-change")

                    if old_ip:
                        ip_clean = str(old_ip).replace("\x00", "")
                        ipaddress.ip_address(ip_clean)
                        nft_remove_ip(ip_clean)

                    if terminate_session(
                        old_session,
                        cause="IP-change",
                        radius_server_ip=radius_server_ip,
                        radius_secret=radius_secret,
                        nas_ip=nas_ip,
                        nas_port_id=nas_port_id,
                        nftables_snapshot=nftables_snapshot,
                        event_dispatcher=event_dispatcher,
                    ):
                        print(f"RADIUS Acct-Stop sent for mac={s.mac} old_ip={old_ip}")

                    # Reassign multimap with new IP
                    sessions_by_ip[s.ip] = s    
                    event_dispatcher.dispatch_session_start(s)
                    
                    reauth_result = _authorize_session(
                        s,
                        s.ip,
                        s.mac,
                        iface,
                        radius_server_ip,
                        radius_secret,
                        nas_ip,
                        nas_port_id,
                    )

                    if reauth_result == "REJECTED":
                        print(f"RADIUS Access-Reject received for mac={s.mac} new_ip={s.ip}")
                    elif reauth_result == "AUTHORIZED":
                        print(f"RADIUS Access-Accept received for mac={s.mac} new_ip={s.ip}")

                    event_dispatcher.dispatch_policy_apply(s)

        # Zombie sessions cleanup
        # ended = [key for key, l in sessions.items() if (key not in current and current[key])]
        ended = []
        print(f"Session keys: {sessions.keys()} Current keys: {current.keys()}")
        for key, s in list(sessions.items()):
            l = current.get(key)
            if l is None:
                # Not in current leases
                if s.expiry is not None and now >= s.expiry:
                    ended.append(key)
            elif l._kea_state != 0:
                # Not an active lease 
                ended.append(key)

        nftables_snapshot = None
        if ended:
            try:
                nftables_snapshot = nft_list_chain_rules()
            except Exception as e:
                print(f"Failed to get nftables snapshot for Acct-Stop: {e}")
                nftables_snapshot = None

        for key in ended:
            s = sessions.pop(key)
            if s.ip:
                sessions_by_ip.pop(s.ip)


            dur = int(now - s.first_seen)
            print(f"Reconciler: DHCP SESSION END mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} duration={dur}s")

            if terminate_session(
                s,
                cause="Reconcile-Timeout",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                nftables_snapshot=nftables_snapshot,
                event_dispatcher=event_dispatcher,
            ):
                print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")

        # Tombstones only clear on renewal (expiry moved forward) or TTL expiry.

    return reconcile_handler, sessions, tombstones, handle_dhcp_event


def bng_event_loop(
    stop_event: threading.Event,
    event_queue: Queue,
    *,
    redis_conn: redis.Redis | None = None,
    iface: str = "eth1",

    # Intervals
    interim_interval: int = 30,
    auth_retry_interval: int = 10,
    disconnection_check_interval: int = 5,
    reconciler_interval: int = 15,

    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="eth1",

    # BNG identification for distributed deployment
    bng_id: str = "bng-default",
    bng_instance_id: str = "",
):
    event_dispatcher = BNGEventDispatcher(
        config=BNGEventDispatcherConfig(
            bng_id=bng_id,
            bng_instance_id=bng_instance_id,
            nas_ip=nas_ip,
            redis_conn=redis_conn,
            print_dispatched_events=True,
        )
    )

    router_tracker = RouterTracker(bng_id=bng_id, event_dispatcher=event_dispatcher)

    dhcp_reconciler, sessions, tombstones, handle_dhcp_event = dhcp_lease_handler(
        bng_id,
        bng_instance_id,
        iface=iface,
        radius_server_ip=radius_server_ip,
        radius_secret=radius_secret,
        nas_ip=nas_ip,
        nas_port_id=nas_port_id,
        event_dispatcher=event_dispatcher,
    )
    next_interim = time.time() + interim_interval
    next_auth_retry = time.time() + auth_retry_interval
    next_disconnection_check = time.time() + disconnection_check_interval
    next_reconcile = time.time() + reconciler_interval
    next_router_ping = time.time() + 30

    while not stop_event.is_set():

        now = time.time()
        t_interim = max(0, next_interim - now)
        t_disc = max(0, next_disconnection_check - now)
        timeout = min(t_interim, t_disc, 0.5)

        event = None
        try:
            event = event_queue.get(timeout=timeout)
        except Empty:
            pass

        if isinstance(event, dict) and event.get("event") == "dhcp":
            try:
                handle_dhcp_event(event)
                router_tracker.on_dhcp_event(event)
                next_reconcile = time.time() + 1
            except Exception as e:
                print(f"BNG thread DHCP event processing error: {e}")
        
        now = time.time()
        if now >= next_interim:
            try:
                radius_handle_interim_updates(
                    sessions,
                    radius_server_ip=radius_server_ip,
                    radius_secret=radius_secret,
                    nas_ip=nas_ip,
                    nas_port_id=nas_port_id,
                    event_dispatcher=event_dispatcher
                )
            except Exception as e:
                print(f"BNG thread Interim-Update error: {e}")
            next_interim = now + interim_interval

        if now >= next_reconcile:
            try:
                dhcp_reconciler()
            except Exception as e:
                print(f"BNG thread Reconcile error: {e}")
            next_reconcile = now + reconciler_interval

        if now >= next_auth_retry:
            try:
                for s in sessions.values():
                    if s.auth_state != "PENDING_AUTH" or s.status == "PENDING" or s.ip is None:
                        continue
                    _authorize_session(
                        s,
                        s.ip,
                        s.mac,
                        iface,
                        radius_server_ip,
                        radius_secret,
                        nas_ip,
                        nas_port_id,
                        ensure_rules=True,
                    )
            except Exception as e:
                print(f"BNG thread Auth-Retry error: {e}")
            next_auth_retry = now + auth_retry_interval

        if ENABLE_IDLE_DISCONNECT and now >= next_disconnection_check:
            # Disconnect IDLE sessions after grace
            try:
                nftables_snapshot = None
                if sessions:
                    try:
                        nftables_snapshot = nft_list_chain_rules()
                    except Exception as e:
                        print(f"Failed to get nftables snapshot for IDLE disconnect: {e}")
                        nftables_snapshot = None

                for key, s in list(sessions.items()):
                    if s.status == "IDLE" and s.last_idle_ts is not None:
                        idle_duration = now - s.last_idle_ts
                        if idle_duration >= MARK_DISCONNECT_GRACE_SECONDS:
                            print(f"DHCP IDLE SESSION DISCONNECT mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} idle_duration={int(idle_duration)}s")
                            terminate_session(
                                s,
                                cause="Idle-Timeout",
                                radius_server_ip=radius_server_ip,
                                radius_secret=radius_secret,
                                nas_ip=nas_ip,
                                nas_port_id=nas_port_id,
                                nftables_snapshot=nftables_snapshot,
                                event_dispatcher=event_dispatcher,
                            )
                            tombstones[key] = Tombstone(
                                ip_at_stop=s.ip or "",
                                latest_state_update_ts_at_stop=s.expiry or int(time.time()),
                                stopped_at=time.time(),
                                reason="Idle-Timeout",
                                missing_seen=False,

                            )
                            sessions.pop(key)
            except Exception as e:
                print(f"BNG thread Disconnection check error: {e}")
            next_disconnection_check = now + disconnection_check_interval

        if now >= next_router_ping:
            try:
                router_tracker.ping_all()
            except Exception as e:
                print(f"BNG thread Router-Ping error: {e}")
            next_router_ping = now + 30
