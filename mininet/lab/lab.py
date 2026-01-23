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


@dataclass
class DHCPSession:
    mac: str
    ip: str
    first_seen: float
    last_seen: float
    expiry: int
    iface: str
    hostname: str

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

def build_acct_stop(s: DHCPSession, nas_ip="192.0.2.1", nas_port_id="bng-eth0", cause="User-Request") -> str:
    now = int(time.time())
    duration = max(0, int(time.time() - s.first_seen))
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
        "",
    ])


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

            if raw:
                leases = parse_dhcp_leases(raw)

            # Current is our single source of truth for active leases
            # We keep the sessions synchronized with it
            current = {(l.mac,iface): l for l in leases}
            
            for key, l in current.items():
                if key not in sessions:
                    sessions[key] = DHCPSession(
                        mac=l.mac,
                        ip=l.ip,
                        first_seen=now,
                        last_seen=now,
                        expiry=l.time,
                        iface=iface,
                        hostname=l.hostname,
                    )
                    print(f"DHCP SESSION START mac={l.mac} ip={l.ip} iface={iface} hostname={l.hostname}")

                    # RADIUS Accounting Start
                    try:
                        pkt = build_acct_start(sessions[key], nas_ip=nas_ip, nas_port_id=nas_port_id)
                        rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
                        print(f"RADIUS Acct-Start sent for mac={l.mac} ip={l.ip}")
                    except Exception as e:
                        print(f"RADIUS Acct-Start failed for mac={l.mac} ip={l.ip}: {e}")
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
                            )

                            try:
                                pkt = build_acct_stop(old_session, nas_ip=nas_ip, nas_port_id=nas_port_id, cause="Lost-Service")
                                rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
                                print(f"RADIUS Acct-Stop sent for mac={s.mac} old_ip={old_ip}")
                            except Exception as e:
                                print(f"RADIUS Acct-Stop failed for mac={s.mac} old_ip={old_ip}: {e}")

                            try:
                                pkt = build_acct_start(s, nas_ip=nas_ip, nas_port_id=nas_port_id)
                                rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
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
                    pkt = build_acct_stop(s, nas_ip=nas_ip, nas_port_id=nas_port_id, cause="User-Request")
                    rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
                    print(f"RADIUS Acct-Stop sent for mac={s.mac} ip={s.ip}")
                except Exception as e:
                    print(f"RADIUS Acct-Stop failed for mac={s.mac} ip={s.ip}: {e}")


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

