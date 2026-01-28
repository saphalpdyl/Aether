import time
import threading
from queue import Queue, Empty
from typing import Dict, Tuple, List
from dataclasses import dataclass

from mininet.node import Host

from lib.dhcp.lease import DHCPLease
from lib.dhcp.utils import parse_dhcp_leases
from lib.nftables.helpers import nft_add_subscriber_rules, nft_delete_rule_by_handle, nft_get_counter_by_handle, nft_list_chain_rules
from lib.radius.packet_builders import build_acct_start, build_acct_stop, rad_acct_send_from_bng
from lib.radius.session import DHCPSession
from lib.secrets import __RADIUS_SECRET
from lib.constants import DHCP_LEASE_EXPIRY_SECONDS, DHCP_LEASE_FILE_PATH, MARK_DISCONNECT_GRACE_SECONDS, ENABLE_IDLE_DISCONNECT, TOMBSTONE_TTL_SECONDS
from lib.radius.handlers import radius_handle_interim_updates


@dataclass
class Tombstone:
    ip_at_stop: str
    lease_expiry_at_stop: float
    stopped_at: float
    reason: str
    missing_seen: bool = False


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

        pkt = build_acct_stop(s, nas_ip=nas_ip, nas_port_id=nas_port_id, cause=cause, 
            input_bytes=total_in_octets,
            output_bytes=total_out_octets,
            input_pkts=total_in_pkts,
            output_pkts=total_out_pkts,
        )
        rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)

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
):
    sessions: Dict[Tuple[str,str], DHCPSession] = {}
    tombstones: Dict[Tuple[str,str], Tombstone] = {} # NOTE: Used only when ENABLE_IDLE_DISCONNECT = True

    def handler():
        raw = bng.cmd(f"cat {leasefile} 2>/dev/null || true")
        now = time.time()
        leases: List[DHCPLease] | None = []

        lease_parse_success = False
        lease_parse_err_message = "Unknown error"
        if raw and raw.strip():
            leases, lease_parse_success, lease_parse_err_message = parse_dhcp_leases(raw)

            if not lease_parse_success:
                print(f"DHCP Lease parse error: {lease_parse_err_message}", leases, raw)
                return

        current = {(l.mac,iface): l for l in leases}
        now_mono = time.monotonic()

        for key, t in list(tombstones.items()):
            if now_mono - t.stopped_at >= TOMBSTONE_TTL_SECONDS:
                tombstones.pop(key, None)

        for key, l in current.items():
            tombstone = tombstones.get(key)
            if tombstone is not None:
                lease_changed = l.time > tombstone.lease_expiry_at_stop
                if not lease_changed:
                    continue
                tombstones.pop(key, None)

            if key not in sessions:
                try:
                    up_handle, down_handle = nft_add_subscriber_rules(bng, ip=l.ip, mac=l.mac, sub_if=iface)

                    nftables_snapshot = nft_list_chain_rules(bng)
                    base_up_bytes, base_up_pkts = nft_get_counter_by_handle(nftables_snapshot, up_handle) or (0,0)
                    base_down_bytes, base_down_pkts = nft_get_counter_by_handle(nftables_snapshot, down_handle) or (0,0)

                    sessions[key] = DHCPSession(
                        mac=l.mac,
                        ip=l.ip,
                        first_seen=now,
                        last_seen=now,
                        expiry=l.time,
                        iface=iface,
                        hostname=l.hostname,
                        last_interim=now,

                        nft_up_handle=up_handle,
                        nft_down_handle=down_handle,

                        base_up_bytes=base_up_bytes,
                        base_down_bytes=base_down_bytes,
                        base_up_pkts=base_up_pkts,
                        base_down_pkts=base_down_pkts,
                    )

                    print(f"DHCP SESSION START mac={l.mac} ip={l.ip} iface={iface} hostname={l.hostname}")

                    try:
                        pkt = build_acct_start(sessions[key], nas_ip=nas_ip, nas_port_id=nas_port_id)
                        rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
                        print(f"RADIUS Acct-Start sent for mac={l.mac} ip={l.ip}")
                    except Exception as e:
                        print(f"RADIUS Acct-Start failed for mac={l.mac} ip={l.ip}: {e}")
                except Exception as e:
                    print(f"Failed to create DHCP session for mac={l.mac} ip={l.ip}: {e}")
            else:
                s = sessions[key]
                s.last_seen = now
                if s.ip != l.ip or s.expiry != l.time:
                    old_ip, old_expiry = s.ip, s.expiry
                    s.ip, s.expiry, s.hostname = l.ip, l.time, l.hostname

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
                            pkt = build_acct_stop(old_session, nas_ip=nas_ip, nas_port_id=nas_port_id, cause="Lost-Service",
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

                            rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
                            print(f"RADIUS Acct-Stop sent for mac={s.mac} old_ip={old_ip}")
                        except Exception as e:
                            print(f"RADIUS Acct-Stop failed for mac={s.mac} old_ip={old_ip}: {e}")

                        try:
                            pkt = build_acct_start(s, nas_ip=nas_ip, nas_port_id=nas_port_id)

                            up_handle, down_handle = nft_add_subscriber_rules(bng, ip=l.ip, mac=l.mac, sub_if=iface)

                            nftables_snapshot = nft_list_chain_rules(bng)
                            base_up_bytes, base_up_pkts = nft_get_counter_by_handle(nftables_snapshot, up_handle) or (0,0)
                            base_down_bytes, base_down_pkts = nft_get_counter_by_handle(nftables_snapshot, down_handle) or (0,0)

                            s.nft_up_handle = up_handle
                            s.nft_down_handle = down_handle

                            s.base_up_bytes = base_up_bytes
                            s.base_down_bytes = base_down_bytes
                            s.base_up_pkts = base_up_pkts
                            s.base_down_pkts = base_down_pkts

                            rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
                            s.last_interim = now
                            print(f"RADIUS Acct-Start sent for mac={s.mac} new_ip={s.ip}")
                        except Exception as e:
                            print(f"RADIUS Acct-Start failed for mac={s.mac} new_ip={s.ip}: {e}")


        ended = [key for key in sessions.keys() if key not in current]
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

    return handler, sessions, tombstones


def bng_event_loop(
    bng: Host,
    stop_event: threading.Event,
    event_queue: Queue,
    iface: str = "bng-eth0",
    interim_interval: int = 30,
    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="bng-eth0",
):
    dhcp_handler, sessions, tombstones = dhcp_lease_handler(bng, iface=iface)
    next_interim = time.time() + interim_interval
    next_disconnection_check = time.time() + 5

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

        if event == "lease_changed":
            try:
                while True:
                    event_queue.get_nowait()
            except Empty:
                pass
            try:
                dhcp_handler()
            except Exception as e:
                print(f"BNG thread DHCP handler error: {e}")
        
        now = time.time()
        if now >= next_interim:
            try:
                radius_handle_interim_updates(bng, sessions)
            except Exception as e:
                print(f"BNG thread Interim-Update error: {e}")
            next_interim = now + interim_interval

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
                                ip_at_stop=s.ip,
                                lease_expiry_at_stop=s.expiry,
                                stopped_at=time.monotonic(),
                                reason="Idle-Timeout",
                                missing_seen=False,
                            )
                            sessions.pop(key)
            except Exception as e:
                print(f"BNG thread Disconnection check error: {e}")

            next_disconnection_check = now + 5
