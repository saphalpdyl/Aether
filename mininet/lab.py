#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSSwitch, Host
from mininet.nodelib import NAT
from mininet.cli import CLI
from mininet.log import setLogLevel

import time 
import threading
import os
from typing import Callable, Dict, Tuple, List
from watchdog.observers import Observer

from lib.dhcp.lease import DHCPLease
from lib.dhcp.utils import parse_dhcp_leases
from lib.nftables.helpers import nft_add_subscriber_rules, nft_delete_rule_by_handle, nft_get_counter_by_handle, nft_list_chain_rules
from lib.radius.packet_builders import build_acct_start, build_acct_stop, build_acct_interim, rad_acct_send_from_bng
from lib.radius.session import DHCPSession
from lib.secrets import __RADIUS_SECRET
from lib.constants import DHCP_LEASE_FILE_PATH, DHCP_LEASE_FILE_DIR_PATH
from lib.services.lease_watcher import LeaseObserver

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
    sessions_lock = threading.Lock()

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

        # Current is our single source of truth for active leases
        # We keep the sessions synchronized with it
        current = {(l.mac,iface): l for l in leases}
        
        with sessions_lock:
            for key, l in current.items():
                # Create new session
                if key not in sessions:
                    # Creating nftables rules
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

                        # RADIUS Accounting Start
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

                            # Calculation of usage for old IP before sending Acct-Stop
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

                                # Delete nftables rules 
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
            for key in ended:
                s = sessions.pop(key)
                dur = int(now - s.first_seen)
                print(f"DHCP SESSION END mac={s.mac} ip={s.ip} iface={s.iface} hostname={s.hostname} duration={dur}s")

                # RADIUS Accounting Stop
                try:
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

                    pkt = build_acct_stop(s, nas_ip=nas_ip, nas_port_id=nas_port_id, cause="User-Request", 
                        input_bytes=total_in_octets,
                        output_bytes=total_out_octets,
                        input_pkts=total_in_pkts,
                        output_pkts=total_out_pkts,
                    )
                    rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)

                    # Delete nftables rules 
                    if s.nft_up_handle is not None:
                        nft_delete_rule_by_handle(bng, s.nft_up_handle)
                    if s.nft_down_handle is not None:
                        nft_delete_rule_by_handle(bng, s.nft_down_handle)

                    print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")
                except Exception as e:
                    print(f"RADIUS Acct-Stop failed for mac={s.mac} ip={s.ip}: {e}")

    return handler, sessions, sessions_lock

# Interim-Update Processing
def radius_handle_interim_updates(
        bng: Host, 
        sessions: Dict[Tuple[str,str], DHCPSession],
        radius_server_ip: str ="192.0.2.2",
        radius_secret: str = __RADIUS_SECRET,
        nas_ip: str="192.0.2.1",
        nas_port_id: str="bng-eth0"):
    now = time.time()
    nftables_snapshot = nft_list_chain_rules(bng)
    for key, s in sessions.items():
        try:

            up_bytes, up_pkts = 0, 0
            down_bytes, down_pkts = 0, 0

            if s.nft_up_handle is not None:
                up_bytes, up_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_up_handle) or (0,0)
            if s.nft_down_handle is not None:
                down_bytes, down_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_down_handle) or (0,0)

            # in_octers as BNG is recieving from subscriber on upload i.e base_up_bytes/pkts
            # out_octets as BNG is sending to subscriber on download i.e base_down_bytes/pkts
            total_in_octets = max(0, up_bytes - s.base_up_bytes)
            total_out_octets = max(0, down_bytes - s.base_down_bytes)
            total_in_pkts = max(0, up_pkts - s.base_up_pkts)
            total_out_pkts = max(0, down_pkts - s.base_down_pkts)

            pkt = build_acct_interim(s, nas_ip=nas_ip, nas_port_id=nas_port_id, 
                input_bytes=total_in_octets,
                output_bytes=total_out_octets,
                input_pkts=total_in_pkts,
                output_pkts=total_out_pkts,
            )
            rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
            s.last_interim = now
            print(f"RADIUS Acct-Interim sent for mac={s.mac} ip={s.ip}")
        except Exception as e:
            print(f"RADIUS Acct-Interim failed for mac={s.mac} ip={s.ip}: {e}")

def dhcp_interim_update_loop(
    bng: Host, 
    sessions: Dict[Tuple[str,str], DHCPSession],
    sessions_lock: threading.Lock,
    stop_event: threading.Event,
    interval: int = 30,
):
    while not stop_event.is_set():
        start = time.time()
        try:
            with sessions_lock:
                sessions_copy = sessions.copy()

            radius_handle_interim_updates(bng, sessions_copy)
        except Exception as e:
            print(f"DHCP Interim-Update thread error: {e}")

        elapsed = time.time() - start
        sleep_for = max(0, interval - elapsed)
        time.sleep(sleep_for)

def run():
    net = Mininet(controller=None, switch=OVSSwitch)

    # Canonical switch names so Mininet can derive DPIDs
    s1 = net.addSwitch('s1', failMode='standalone')  # access
    s2 = net.addSwitch('s2', failMode='standalone')  # upstream

    h1 = net.addHost('h1', ip=None)
    h2 = net.addHost('h2', ip=None)
    net.addLink(h1, s1)
    net.addLink(h2, s1)

    bng = net.addHost('bng')
    net.addLink(bng, s1)  # bng-eth0 subscriber side
    net.addLink(bng, s2)  # bng-eth1 upstream side

    nat = net.addHost('nat', cls=NAT, ip='192.0.2.2/24', inNamespace=False)
    net.addLink(nat, s2)  # nat-eth0 on upstream segment

    net.start()

    # Deterministic BNG config
    bng.cmd('ip addr flush dev bng-eth0')
    bng.cmd('ip addr flush dev bng-eth1')
    bng.cmd('ip link set bng-eth0 up')
    bng.cmd('ip link set bng-eth1 up')
    bng.cmd('ip addr add 10.0.0.1/24 dev bng-eth0')
    bng.cmd('ip addr add 192.0.2.1/24 dev bng-eth1')
    bng.cmd('ip route replace default via 192.0.2.2 dev bng-eth1')
    bng.cmd('sysctl -w net.ipv4.ip_forward=1')

    # Settings up nftables for BNG 
    bng.cmd("nft add table inet bngacct 2>/dev/null || true") # Creating a table called bngacct

    # Creating a chain in table 'bngacct' called 'sess'
    # The chain hooks into the 'forward' hook with policy 'accept' meaning packets are allowed by default 
    #   since we are only counting packets/bytes here and not enforcing any filtering
    bng.cmd("nft 'add chain inet bngacct sess {type filter hook forward priority 0; policy accept;}' 2>/dev/null || true") 

    # Root-namespace NAT (known-good baseline)
    nat.configDefault()
    nat.cmd('ip route replace 10.0.0.0/24 via 192.0.2.1 dev nat-eth0')

    bng.cmd(f'rm -f /tmp/dnsmasq-bng.pid {DHCP_LEASE_FILE_DIR_PATH} 2>/dev/null || true')

    # Create the DHCP lease file directory
    bng.cmd('mkdir -p ' + os.path.dirname(DHCP_LEASE_FILE_DIR_PATH))
    bng.cmd(
        'dnsmasq '
        '--port=0 ' # Disabled DNS 
        '--interface=bng-eth0 '
        '--dhcp-authoritative '
        '--dhcp-range=10.0.0.10,10.0.0.200,255.255.255.0,12h '
        '--dhcp-option=option:router,10.0.0.1 '
        '--dhcp-option=option:dns-server,1.1.1.1,8.8.8.8 '
        f'--dhcp-leasefile={DHCP_LEASE_FILE_PATH} '
        '--pid-file=/tmp/dnsmasq-bng.pid '
        '--log-dhcp '
        '> /tmp/dnsmasq-bng.log 2>&1 & '
    )

    # Starting our DHCP Lease to Sessions watcher
    # watcher_opts, sessions = start_lease_poll_watcher(bng, iface="bng-eth0")
    # time.sleep(0.2)
    dhcp_handler_func, sessions, sessions_lock = dhcp_lease_handler(bng, iface="bng-eth0")

    dhcp_observer = Observer()
    dhcp_observer.schedule(LeaseObserver(dhcp_handler_func), path=DHCP_LEASE_FILE_DIR_PATH, recursive=False)
    dhcp_observer.start()

    # Create a thread to handle RADIUS Interim-Updates every 30 seconds
    radius_interim_stop_event = threading.Event()
    radius_interim_thread = threading.Thread(
        target=dhcp_interim_update_loop,
        args=(bng, sessions, sessions_lock, radius_interim_stop_event, 10),
        daemon=False
    )
    radius_interim_thread.start()

    CLI(net)

    # Stopping watcher thread
    # watcher_opts["stop"] = True
    radius_interim_stop_event.set()
    radius_interim_thread.join()
    dhcp_observer.stop()
    dhcp_observer.join()

    bng.cmd('kill $(cat /tmp/dnsmasq-bng.pid) 2>/dev/null || true')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()

