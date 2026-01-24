#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSSwitch, Host
from mininet.nodelib import NAT
from mininet.cli import CLI
from mininet.log import setLogLevel

import time 
import threading
import subprocess
from dataclasses import dataclass 
from typing import Dict, Tuple, List
import shlex

import json

@dataclass
class DHCPSession:
    mac: str
    ip: str
    first_seen: float
    last_seen: float
    expiry: int
    iface: str
    hostname: str
    last_interim: float # For Interim-Update tracking

    # nftables related data
    nft_up_handle: int | None = None
    nft_down_handle: int | None = None

    base_up_bytes: int = 0
    base_down_bytes: int = 0
    base_up_pkts: int = 0
    base_down_pkts: int = 0

@dataclass
class DHCPLease:
    time: int
    mac: str
    ip: str
    hostname: str
    client_id: str # Might be a MAC or * if not sent


# RADIUS Accounting
__RADIUS_SECRET = "testing123"

def rad_acct_send_from_bng(
    bng: Host,
    packet: str,
    server_ip: str,
    port: int = 1813,
    secret: str = __RADIUS_SECRET,
    timeout: int = 1,
):
    pkt_q = shlex.quote(packet)
    secret_q = shlex.quote(secret)
    cmd = f"printf %s {pkt_q} | radclient -x -t {timeout} {server_ip}:{port} acct {secret_q}"
    return bng.cmd(cmd)

def acct_session_id(mac: str, ip: str, first_seen: float) -> str:
    return f"{mac.lower()}-{ip}-{int(first_seen)}"

def build_acct_start(s: DHCPSession, nas_ip="192.0.2.1", nas_port_id="bng-eth0") -> str:
    now = int(time.time())
    return "\n".join([
        "Acct-Status-Type = Start",
        f'User-Name = "mac:{s.mac.lower()}"',
        f'Acct-Session-Id = "{acct_session_id(s.mac, s.ip, s.first_seen)}"',
        f"Framed-IP-Address = {s.ip}",
        f'Calling-Station-Id = "{s.mac.lower()}"',
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Event-Timestamp = {now}",
        "",
    ])

def build_acct_stop(
    s: "DHCPSession",
    input_bytes: int,
    output_bytes: int,
    input_pkts: int,
    output_pkts: int,
    nas_ip: str = "192.0.2.1",
    nas_port_id: str = "bng-eth0",
    cause: str = "User-Request",
) -> str:
    now = int(time.time())
    duration = max(0, int(time.time() - s.first_seen))

    in_gw, in_oct = split_bytes_to_gigawords_octets(input_bytes)
    out_gw, out_oct = split_bytes_to_gigawords_octets(output_bytes)

    return "\n".join([
        "Acct-Status-Type = Stop",
        f'User-Name = "mac:{s.mac.lower()}"',
        f'Acct-Session-Id = "{acct_session_id(s.mac, s.ip, s.first_seen)}"',
        f"Framed-IP-Address = {s.ip}",
        f'Calling-Station-Id = "{s.mac.lower()}"',
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Acct-Session-Time = {duration}",
        f'Acct-Terminate-Cause = "{cause}"',
        f"Event-Timestamp = {now}",

        # Bytes (64-bit via octets+gigawords)
        f"Acct-Input-Octets = {in_oct}",
        f"Acct-Input-Gigawords = {in_gw}",
        f"Acct-Output-Octets = {out_oct}",
        f"Acct-Output-Gigawords = {out_gw}",

        # Packets (32-bit best-effort; no standard gigawords field)
        f"Acct-Input-Packets = {max(0, int(input_pkts))}",
        f"Acct-Output-Packets = {max(0, int(output_pkts))}",
        "",
    ])


def build_acct_interim(
    s: "DHCPSession",
    input_bytes: int,
    output_bytes: int,
    input_pkts: int,
    output_pkts: int,
    nas_ip: str = "192.0.2.1",
    nas_port_id: str = "bng-eth0",
) -> str:
    now = int(time.time())
    session_time = max(0, int(time.time() - s.first_seen))

    in_gw, in_oct = split_bytes_to_gigawords_octets(input_bytes)
    out_gw, out_oct = split_bytes_to_gigawords_octets(output_bytes)

    return "\n".join([
        "Acct-Status-Type = Interim-Update",
        f'User-Name = "mac:{s.mac.lower()}"',
        f'Acct-Session-Id = "{acct_session_id(s.mac, s.ip, s.first_seen)}"',
        f"Framed-IP-Address = {s.ip}",
        f'Calling-Station-Id = "{s.mac.lower()}"',
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Acct-Session-Time = {session_time}",
        f"Event-Timestamp = {now}",

        # Bytes (64-bit via octets+gigawords)
        f"Acct-Input-Octets = {in_oct}",
        f"Acct-Input-Gigawords = {in_gw}",
        f"Acct-Output-Octets = {out_oct}",
        f"Acct-Output-Gigawords = {out_gw}",

        # Packets (32-bit best-effort)
        f"Acct-Input-Packets = {max(0, int(input_pkts))}",
        f"Acct-Output-Packets = {max(0, int(output_pkts))}",
        "",
    ])

# nftables helpers
def nft_list_chain_rules(bng: Host):
    out = bng.cmd("nft -j list chain inet bngacct sess")

    if not out or not out.strip():
        return {}

    return json.loads(out)

def nft_find_rule_handle(nft_json: dict, comment_match: str):
    for item in nft_json.get("nftables", []):
        rule = item.get("rule")
        if not rule:
            continue

        # Check for correct table and chain
        if rule.get("table") != "bngacct" or rule.get("chain") != "sess":
            continue

        comment = rule.get("comment", None);
        if comment == comment_match:
            return rule.get("handle", None)

    return None

def nft_add_subscriber_rules(
    bng: Host,
    ip: str,
    mac: str,
    sub_if: str = "bng-eth0", # if = interface
    # NOTE: We have bng-eth0 as the default iface because we want to measure on subscriber facing interface 
    #   We could have measured on bng-eth1 ( upstream facing ) but that would not capture traffic that is dropped by BNG itself
):
    mac_l = mac.lower()

    # Upload counter rule
    bng.cmd(
        f"nft \'add rule inet bngacct sess iif \"{sub_if}\" ip saddr {ip} counter "
        f"comment \"sub;mac={mac_l};dir=up;ip={ip}\"\'"
    )

    # Download counter rule
    bng.cmd(
        f"nft \'add rule inet bngacct sess oif \"{sub_if}\" ip daddr {ip} counter "
        f"comment \"sub;mac={mac_l};dir=down;ip={ip}\"\'"
    )

    nftables_data = nft_list_chain_rules(bng)
    up_rule_handle = nft_find_rule_handle(nftables_data, f"sub;mac={mac_l};dir=up;ip={ip}")
    down_rule_handle = nft_find_rule_handle(nftables_data, f"sub;mac={mac_l};dir=down;ip={ip}")

    if up_rule_handle is None or down_rule_handle is None:
        raise RuntimeError("Failed to add nftables rules for subscriber")

    return up_rule_handle, down_rule_handle

def nft_delete_rule_by_handle(bng: Host, handle: int):
    bng.cmd(f"nft delete rule inet bngacct sess handle {handle} 2>/dev/null || true")


def nft_get_counter_by_handle(nftables_json, handle: int) -> Tuple[int, int] | None:
    for item in nftables_json.get("nftables", []):
        rule = item.get("rule")
        if not rule:
            continue

        if rule.get("table") != "bngacct" or rule.get("chain") != "sess":
            continue

        if rule.get("handle") != handle:
            continue

        expr = rule.get("expr", [])
        for e in expr:
            counter = e.get("counter", None)
            if counter:
                return counter.get("bytes", 0), counter.get("packets", 0)

    return None

def split_bytes_to_gigawords_octets(total_bytes: int) -> Tuple[int, int]:
    # The RADIUS protocol uses 32-bit counters for octets, so counters > 4.29 GB will reset to 0 without splitting
    if total_bytes < 0:
        total_bytes = 0

    gigawords = total_bytes >> 32
    remaining_octets = total_bytes & 0xFFFFFFFF

    return gigawords, remaining_octets

def parse_dhcp_leases(lines: str) -> List[DHCPLease]:
    leases: List[DHCPLease] = []
    for line_no, line in enumerate(lines.splitlines()):
        parts = line.split()
        if len(parts) < 5:
            raise ValueError(f"Invalid DHCP lease line: {line_no + 1}")
        lease = DHCPLease(
            time=int(parts[0]),
            mac=parts[1],
            ip=parts[2],
            hostname=parts[3],
            client_id=parts[4]
        )
        leases.append(lease)
    return leases

def start_lease_poll_watcher(
    bng: Host,
    leasefile="/tmp/dnsmasq-bng.leases",
    interval=1.0,
    iface: str="bng-eth0",
    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="bng-eth0",
    last_interim_interval: int = 30,
):
    sessions: Dict[Tuple[str, str], DHCPSession] = {}
    watcher_options = {
        "stop": False,
    }

    def loop():
        while not watcher_options["stop"]:
            raw = bng.cmd(f"cat {leasefile} 2>/dev/null || true")
            now = time.time()
            leases: List[DHCPLease] = []

            if raw and raw.strip():
                leases = parse_dhcp_leases(raw)

            # Current is our single source of truth for active leases
            # We keep the sessions synchronized with it
            current = {(l.mac,iface): l for l in leases}
            
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

            # Interim-Update processing
            nftables_snapshot = nft_list_chain_rules(bng)
            for key, s in sessions.items():
                if ( now - s.last_interim ) >= last_interim_interval:
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

            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()

    return watcher_options, sessions



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

    bng.cmd('rm -f /tmp/dnsmasq-bng.pid /tmp/dnsmasq-bng.leases')
    bng.cmd(
        'dnsmasq '
        '--port=0 ' # Disabled DNS 
        '--interface=bng-eth0 '
        '--dhcp-authoritative '
        '--dhcp-range=10.0.0.10,10.0.0.200,255.255.255.0,12h '
        '--dhcp-option=option:router,10.0.0.1 '
        '--dhcp-option=option:dns-server,1.1.1.1,8.8.8.8 '
        '--dhcp-leasefile=/tmp/dnsmasq-bng.leases '
        '--pid-file=/tmp/dnsmasq-bng.pid '
        '--log-dhcp '
        '> /tmp/dnsmasq-bng.log 2>&1 & '
    )

    # Starting our DHCP Lease to Sessions watcher
    watcher_opts, sessions = start_lease_poll_watcher(bng, iface="bng-eth0")
    time.sleep(0.2)

    CLI(net)

    # Stopping watcher thread
    watcher_opts["stop"] = True

    bng.cmd('kill $(cat /tmp/dnsmasq-bng.pid) 2>/dev/null || true')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()

