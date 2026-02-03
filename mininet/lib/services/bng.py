from os import wait
import re
import time
import threading
from queue import Queue, Empty
from typing import Dict, Tuple, List
from dataclasses import dataclass

from mininet.node import Host

from lib.dhcp.lease import DHCPLease
from lib.dhcp.utils import parse_dhcp_leases, format_mac
from lib.nftables.helpers import nft_add_subscriber_rules, nft_allow_mac, nft_delete_rule_by_handle, nft_get_counter_by_handle, nft_list_chain_rules, nft_remove_mac
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


def _install_rules_and_baseline(bng: Host, s: DHCPSession, ip: str, mac: str, iface: str) -> None:
    up_handle, down_handle = nft_add_subscriber_rules(bng, ip=ip, mac=mac, sub_if=iface)
    s.nft_up_handle = up_handle
    s.nft_down_handle = down_handle

    snapshot = nft_list_chain_rules(bng)
    base_up_bytes, base_up_pkts = nft_get_counter_by_handle(snapshot, up_handle) or (0,0)
    base_down_bytes, base_down_pkts = nft_get_counter_by_handle(snapshot, down_handle) or (0,0)
    s.base_up_bytes = base_up_bytes
    s.base_down_bytes = base_down_bytes
    s.base_up_pkts = base_up_pkts
    s.base_down_pkts = base_down_pkts


def _authorize_session(
    bng: Host,
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
    access_request_response = rad_auth_send_from_bng(bng, access_request_pkt, server_ip=radius_server_ip, secret=radius_secret)
    print(access_request_response)
    if not access_request_response:
        raise RuntimeError(f"RADIUS Access-Request unexpected response: {access_request_response}")
    if re.search(r'Access-Reject', access_request_response):
        s.auth_state = "REJECTED"
        return "REJECTED"
    if re.search(r'Access-Accept', access_request_response):
        if ensure_rules and (s.nft_up_handle is None or s.nft_down_handle is None):
            _install_rules_and_baseline(bng, s, ip, mac, iface)
        s.auth_state = "AUTHORIZED"
        nft_allow_mac(bng, mac)
        acct_start_pkt = build_acct_start(s, nas_ip=nas_ip, nas_port_id=nas_port_id)
        rad_acct_send_from_bng(bng, acct_start_pkt, server_ip=radius_server_ip, secret=radius_secret)
        print(f"RADIUS Acct-Start sent for mac={s.mac} ip={s.ip}")
        return "AUTHORIZED"
    return None


def terminate_session(
    bng: Host,
    s: DHCPSession,
    cause: str,
    radius_server_ip: str,
    radius_secret: str,
    nas_ip: str,
    nas_port_id: str,
    nftables_snapshot=None,
    delete_rules: bool = True,
):
    try:
        if nftables_snapshot is None:
            nftables_snapshot = nft_list_chain_rules(bng)

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

        if s.auth_state == "AUTHORIZED":
            pkt = build_acct_stop(s, nas_ip=nas_ip, nas_port_id=nas_port_id, cause=cause, 
                input_bytes=total_in_octets,
                output_bytes=total_out_octets,
                input_pkts=total_in_pkts,
                output_pkts=total_out_pkts,
            )
            rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)

        # Remove rulesets allowing traffic 
        if s.mac is not None:
            nft_remove_mac(bng, s.mac)

        if delete_rules:
            if s.nft_up_handle is not None:
                nft_delete_rule_by_handle(bng, s.nft_up_handle)
            if s.nft_down_handle is not None:
                nft_delete_rule_by_handle(bng, s.nft_down_handle)

        return True
    except Exception as e:
        print(f"RADIUS Acct-Stop failed for mac={s.mac} ip={s.ip}: {e}")
        return False


def dhcp_lease_handler(
    bng: Host,
    leasefile=DHCP_LEASE_FILE_PATH,
    iface: str="bng-eth0",
    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="bng-eth0",
    kea_ctrl_agent_auth_key: str = __KEA_CTRL_AGENT_PASSWORD
):
    sessions: Dict[Tuple[str,str,str], DHCPSession] = {}
    tombstones: Dict[Tuple[str,str,str], Tombstone] = {} # NOTE: Used only when ENABLE_IDLE_DISCONNECT = True
    
    _kea_client = KeaClient(base_url=f"http://192.0.2.3:6772", auth_key=kea_ctrl_agent_auth_key)
    _kea_lease_service = KeaLeaseService(_kea_client, bng_relay_id=nas_ip)

    def handle_dhcp_request(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (nas_ip,circuit_id,remote_id)
        existing_sess = sessions.get(key)
        now = time.time()
        try:
            if chaddr is None or isinstance(chaddr, str) is False:
                raise RuntimeError("DHCP ACK missing chaddr")

            print(sessions.keys())
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

                    relay_id=nas_ip,
                    remote_id=remote_id,
                    circuit_id=circuit_id,

                )
                print(f"Created temp DHCP session for mac={chaddr} circuit: {circuit_id}")

        except Exception as e:
            print(f"Failed to create temp DHCP session for mac={chaddr} circuit: {circuit_id}: {e}")
            
    
    def handle_dhcp_discover(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        ...

    def handle_dhcp_ack(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (nas_ip,circuit_id,remote_id)
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
                        nft_delete_rule_by_handle(bng, s.nft_up_handle)
                    if s.nft_down_handle is not None:
                        nft_delete_rule_by_handle(bng, s.nft_down_handle)

                    terminate_session(
                        bng,
                        s,
                        cause="Lost-Service",
                        radius_server_ip=radius_server_ip,
                        radius_secret=radius_secret,
                        nas_ip=nas_ip,
                        nas_port_id=nas_port_id,
                    )
                    s.nft_up_handle = None
                    s.nft_down_handle = None
                    s.auth_state = "PENDING_AUTH"

                s.ip = leased_ip
                s.first_seen = now
                s.status = "ACTIVE"
                s.last_status_change_ts = now


                print(f"DHCP SESSION START mac={s.mac} ip={s.ip} iface={iface} hostname={s.hostname}")

                try:
                    result = _authorize_session(
                        bng,
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
                except Exception as e:
                    print(f"RADIUS Acct-Start failed for mac={s.mac} ip={s.ip}: {e}")
            else:
                print("Found DHCP ACK for unknown session")


        except Exception as e:
            print(f"Failed to handle DHCP ACK for mac={chaddr} circuit: {circuit_id}: {e}")
            return


    def handle_dhcp_nak(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (nas_ip,circuit_id,remote_id)
        now = time.time()
        
        s = sessions.get(key)

        if s is not None:
            # Do nothing
            s.status = "PENDING"

            if s.dhcp_nak_count >= DHCP_NAK_TERMINATE_COUNT_THRESHOLD and s.ip is None:
                ...

            s.dhcp_nak_count += 1
            ...

    def handle_dhcp_release(circuit_id: str, remote_id: str, chaddr: str, event: dict):
        key = (nas_ip,circuit_id,remote_id)
        now = time.time()
        nftables_snapshot = nft_list_chain_rules(bng)

        s = sessions.pop(key, None)
        if s is None:
            print(f"DHCP RELEASE for unknown session circuit: {circuit_id} remote: {remote_id}")
            return
        tombstones[key] = Tombstone(
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
                bng,
                s,
                cause="User-Request",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                nftables_snapshot=nftables_snapshot,
            ):
                print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")

    dhcp_events = {
        1: handle_dhcp_discover,
        3: handle_dhcp_request,
        5: handle_dhcp_ack,
        6: handle_dhcp_nak,
        7: handle_dhcp_release,
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

        if event_handler is not None and circuit_id is not None and remote_id is not None and chaddr:
            print(f"Handling DHCP event {event_handler.__name__} event: {event}")
            event_handler(circuit_id, remote_id, chaddr, event)

    def reconcile_handler():
        # raw = bng.cmd(f"cat {leasefile} 2>/dev/null || true")
        # now = time.time()
        # leases: List[DHCPLease] | None = []
        #
        # lease_parse_success = False
        # lease_parse_err_message = "Unknown error"
        # if raw and raw.strip():
        #     leases, lease_parse_success, lease_parse_err_message = parse_dhcp_leases(raw)
        #
        #     if not lease_parse_success:
        #         print(f"DHCP Lease parse error: {lease_parse_err_message}", leases, raw)
        #         return

        now = time.time()
        leases = _kea_lease_service.get_all_leases()

        current = {(l.relay_id, l.circuit_id , l.remote_id): l for l in leases}

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

                    _install_rules_and_baseline(bng, sessions[key], l.ip, l.mac, iface)

                    print(f"Reconciler: DHCP SESSION START mac={l.mac} ip={l.ip} iface={iface} hostname={l.hostname}")

                    try:
                        result = _authorize_session(
                            bng,
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
                            # Already have this lease assigned
                            continue

                        s.ip = l.ip
                        s.first_seen = now
                        s.status = "ACTIVE"
                        s.last_status_change_ts = now

                        _install_rules_and_baseline(bng, s, s.ip, s.mac, iface)

                        print(f"DHCP SESSION START mac={s.mac} ip={s.ip} iface={iface} hostname={s.hostname}")

                        try:
                            result = _authorize_session(
                                bng,
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

                        continue

                # Case A: Lease renewed ( expiry extended ) but missed DHCP packet
                if s.expiry is not None and s.expiry != l.expiry:
                    s.expiry = l.expiry

                s.last_seen = now

                # Case B: Lease changed ( IP changed )
                if s.ip != l.ip:
                    old_ip, old_expiry = s.ip, s.expiry
                    s.ip, s.expiry, s.hostname = l.ip, l.expiry, l.hostname

                    # Remove idle status on renew
                    s.last_idle_ts = None
                    s.status = "ACTIVE"
                    s.last_traffic_seen_ts = None
                    s.last_up_bytes = None
                    s.last_down_bytes = None

                    print(f"DHCP SESSION RENEW mac={l.mac} old_ip={old_ip} new_ip={s.ip} old_expiry={old_expiry} new_expiry={s.expiry} iface={iface} hostname={l.hostname}")

                    if old_ip != s.ip:
                        old_session = DHCPSession(
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
                        )

                        nftables_snapshot = nft_list_chain_rules(bng)
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

                        try:
                            acct_start_pkt = build_acct_stop(old_session, nas_ip=nas_ip, nas_port_id=nas_port_id, cause="Lost-Service",
                                input_bytes=total_in_octets,
                                output_bytes=total_out_octets,
                                input_pkts=total_in_pkts,
                                output_pkts=total_out_pkts,
                            )

                            if s.nft_up_handle is not None:
                                nft_delete_rule_by_handle(bng, s.nft_up_handle)
                                s.nft_up_handle = None
                            if s.nft_down_handle is not None:
                                nft_delete_rule_by_handle(bng, s.nft_down_handle)
                                s.nft_down_handle = None

                            rad_acct_send_from_bng(bng, acct_start_pkt, server_ip=radius_server_ip, secret=radius_secret)
                            print(f"RADIUS Acct-Stop sent for mac={s.mac} old_ip={old_ip}")
                        except Exception as e:
                            print(f"RADIUS Acct-Stop failed for mac={s.mac} old_ip={old_ip}: {e}")

                        try:
                            acct_start_pkt = build_acct_start(s, nas_ip=nas_ip, nas_port_id=nas_port_id)

                            _install_rules_and_baseline(bng, s, l.ip, l.mac, iface)

                            rad_acct_send_from_bng(bng, acct_start_pkt, server_ip=radius_server_ip, secret=radius_secret)
                            s.last_interim = now
                            print(f"RADIUS Acct-Start sent for mac={s.mac} new_ip={s.ip}")
                        except Exception as e:
                            print(f"RADIUS Acct-Start failed for mac={s.mac} new_ip={s.ip}: {e}")


        # Zombie sessions cleanup
        # ended = [key for key, l in sessions.items() if (key not in current and current[key])]
        ended = []
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
                nftables_snapshot = nft_list_chain_rules(bng)
            except Exception as e:
                print(f"Failed to get nftables snapshot for Acct-Stop: {e}")
                nftables_snapshot = None

        for key in ended:
            s = sessions.pop(key)
            dur = int(now - s.first_seen)
            print(f"DHCP SESSION END mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} duration={dur}s")

            if terminate_session(
                bng,
                s,
                cause="User-Request",
                radius_server_ip=radius_server_ip,
                radius_secret=radius_secret,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                nftables_snapshot=nftables_snapshot,
            ):
                print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")

        # Tombstones only clear on renewal (expiry moved forward) or TTL expiry.

    return reconcile_handler, sessions, tombstones, handle_dhcp_event


def bng_event_loop(
    bng: Host,
    stop_event: threading.Event,
    event_queue: Queue,
    iface: str = "bng-eth0",
    interim_interval: int = 30,
    auth_retry_interval: int = 10,
    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="bng-eth0",
):
    dhcp_reconciler, sessions, tombstones, handle_dhcp_event = dhcp_lease_handler(
        bng,
        iface=iface,
        radius_server_ip=radius_server_ip,
        radius_secret=radius_secret,
        nas_ip=nas_ip,
        nas_port_id=nas_port_id,
    )
    next_interim = time.time() + interim_interval
    next_auth_retry = time.time() + auth_retry_interval
    next_disconnection_check = time.time() + 5
    next_reconcile = time.time() + 15

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
                next_reconcile = time.time() + 1
            except Exception as e:
                print(f"BNG thread DHCP event processing error: {e}")
        
        now = time.time()
        if now >= next_interim:
            try:
                radius_handle_interim_updates(
                    bng,
                    sessions,
                    radius_server_ip=radius_server_ip,
                    radius_secret=radius_secret,
                    nas_ip=nas_ip,
                    nas_port_id=nas_port_id,
                )
            except Exception as e:
                print(f"BNG thread Interim-Update error: {e}")
            next_interim = now + interim_interval

        if now >= next_reconcile:
            try:
                dhcp_reconciler()
            except Exception as e:
                print(f"BNG thread Reconcile error: {e}")
            next_reconcile = now + 15

        if now >= next_auth_retry:
            try:
                for s in sessions.values():
                    if s.auth_state != "PENDING_AUTH" or s.status == "PENDING" or s.ip is None:
                        continue
                    _authorize_session(
                        bng,
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
                        nftables_snapshot = nft_list_chain_rules(bng)
                    except Exception as e:
                        print(f"Failed to get nftables snapshot for IDLE disconnect: {e}")
                        nftables_snapshot = None

                for key, s in list(sessions.items()):
                    if s.status == "IDLE" and s.last_idle_ts is not None:
                        idle_duration = now - s.last_idle_ts
                        if idle_duration >= MARK_DISCONNECT_GRACE_SECONDS:
                            print(f"DHCP IDLE SESSION DISCONNECT mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} idle_duration={int(idle_duration)}s")
                            terminate_session(
                                bng,
                                s,
                                cause="Idle-Timeout",
                                radius_server_ip=radius_server_ip,
                                radius_secret=radius_secret,
                                nas_ip=nas_ip,
                                nas_port_id=nas_port_id,
                                nftables_snapshot=nftables_snapshot,
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
            next_disconnection_check = now + 5
