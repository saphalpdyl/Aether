#!/usr/bin/env python3

import re
import subprocess
import sys
from pathlib import Path
import json
import threading
from queue import Queue

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.nodelib import NAT
from mininet.cli import CLI
from mininet.log import setLogLevel

from lib.constants import DHCP_LEASE_FILE_DIR_PATH
from lib.services.bng import bng_event_loop


def ovs_port_map(sw: OVSSwitch):
    out = sw.cmd(f"ovs-ofctl show {sw.name}")
    ports = {}
    for line in out.splitlines():
        m = re.search(r"\s*(\d+)\(([^)]+)\):", line)
        if m:
            ports[m.group(2)] = int(m.group(1))
    return ports


def ovs_install_dhcp_punt(sw: OVSSwitch, access_ports: list[str]):
    ports = ovs_port_map(sw)
    sw.cmd(f"ovs-ofctl del-flows {sw.name}")
    for p in access_ports:
        if p in ports:
            sw.cmd(
                f'ovs-ofctl add-flow {sw.name} "priority=100,in_port={ports[p]},udp,tp_src=68,tp_dst=67,actions=drop"'
            )
    sw.cmd(f'ovs-ofctl add-flow {sw.name} "priority=1,actions=NORMAL"')

def run():
    net = Mininet(controller=None, switch=OVSSwitch)

    # Canonical switch names so Mininet can derive DPIDs
    s1 = net.addSwitch('s1', failMode='standalone')  # access
    s2 = net.addSwitch('s2', failMode='standalone')  # upstream

    h1 = net.addHost('h1', ip=None, mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip=None, mac='00:00:00:00:00:02')
    net.addLink(h1, s1)
    net.addLink(h2, s1)

    bng = net.addHost('bng')
    net.addLink(bng, s1)  # bng-eth0 subscriber side
    net.addLink(bng, s2)  # bng-eth1 upstream side

    nat = net.addHost('nat', cls=NAT, ip='192.0.2.2/24', inNamespace=False)
    net.addLink(nat, s2)  # nat-eth0 on upstream segment

    kea = net.addHost('kea')
    net.addLink(kea, s2)  # kea-eth0 on upstream segment

    net.start()

    # OLT-style DHCP punt for access ports
    ovs_install_dhcp_punt(s1, ["s1-eth1", "s1-eth2"])

    # Deterministic BNG config
    bng.cmd('ip addr flush dev bng-eth0')
    bng.cmd('ip addr flush dev bng-eth1')
    bng.cmd('ip link set bng-eth0 up')
    bng.cmd('ip link set bng-eth1 up')
    bng.cmd('ip addr add 10.0.0.1/24 dev bng-eth0')
    bng.cmd('ip addr add 192.0.2.1/24 dev bng-eth1')
    bng.cmd('ip route replace default via 192.0.2.2 dev bng-eth1')
    bng.cmd('sysctl -w net.ipv4.ip_forward=1')

    # Setting up nftables for BNG 

    bng.cmd("nft delete table inet aether_auth 2>/dev/null || true")
    bng.cmd("nft delete table inet bngacct 2>/dev/null || true")

    bng.cmd("nft add table inet aether_auth 2>/dev/null || true")
    bng.cmd("nft add table inet bngacct 2>/dev/null || true")

    bng.cmd("nft 'add set inet aether_auth authed_macs { type ether_addr; }' 2>/dev/null || true")

    bng.cmd("nft 'add chain inet aether_auth forward { type filter hook forward priority -10; policy drop; }' 2>/dev/null || true")

    bng.cmd("nft 'add rule inet aether_auth forward ct state established,related accept' 2>/dev/null || true")
    bng.cmd("nft 'add rule inet aether_auth forward iifname \"bng-eth0\" udp sport 68 udp dport 67 accept' 2>/dev/null || true")
    bng.cmd("nft 'add rule inet aether_auth forward iifname \"bng-eth1\" udp sport 67 udp dport 68 accept' 2>/dev/null || true")


    bng.cmd("nft 'add rule inet aether_auth forward iifname \"bng-eth0\" ether saddr @authed_macs accept' 2>/dev/null || true")

    # Reject rule for non-authenticated MACs
    # For TCP traffic
    bng.cmd("nft 'add rule inet aether_auth forward iifname \"bng-eth0\" ct state new tcp reject with tcp reset'")
    # For non-TCP traffic
    bng.cmd("nft 'add rule inet aether_auth forward iifname \"bng-eth0\" ct state new reject with icmpx type admin-prohibited'")

    # Creating a chain in table 'bngacct' called 'sess'
    # The chain hooks into the 'forward' hook with policy 'accept' meaning packets are allowed by default 
    #   since we are only counting packets/bytes here and not enforcing any filtering
    bng.cmd("nft 'add chain inet bngacct sess { type filter hook forward priority 0; policy accept; }' 2>/dev/null || true")

    # Allow h1 for now ( TESTING ONLY )
    # bng.cmd("nft add element inet aether_auth authed_macs { 00:00:00:00:00:01 } 2>/dev/null || true")

    # Root-namespace NAT (known-good baseline)
    nat.configDefault()
    nat.cmd('ip route replace 10.0.0.0/24 via 192.0.2.1 dev nat-eth0')

    # KEA DHCPv4 server host
    kea.cmd('ip addr flush dev kea-eth0')
    kea.cmd('ip link set kea-eth0 up')
    kea.cmd('ip addr add 192.0.2.3/24 dev kea-eth0')
    kea.cmd('ip route replace default via 192.0.2.1 dev kea-eth0')
    kea.cmd('rm -f /tmp/kea/logger_lockfile 2>/dev/null || true')
    kea.cmd('mkdir -p /run/kea')
    kea.cmd('chmod 777 /run/kea')
    kea.cmd('KEA_LOCKFILE_DIR=none kea-dhcp4 -c /etc/kea/kea-dhcp4.conf > /tmp/kea-dhcp4.log 2>&1 &')

    kea.cmd('rm -f /run/kea/kea-ctrl-agent.*.pid')
    kea.cmd('KEA_LOCKFILE_DIR=none kea-ctrl-agent -c /etc/kea/kea-ctrl-agent.conf > /tmp/kea-ctrl-agent.log 2>&1 &')

    bng.cmd('mkdir -p ' + DHCP_LEASE_FILE_DIR_PATH)

    # OLT processor runs in root namespace
    bng_mac = bng.cmd("cat /sys/class/net/bng-eth0/address").strip()
    s1_uplink_mac = s1.cmd("cat /sys/class/net/s1-eth3/address").strip()
    relay_switch_path = str(Path(__file__).resolve().parent / "relay_switch.py")
    relay_switch_proc = subprocess.Popen(
        [
            sys.executable,
            relay_switch_path,
            "--access",
            "s1-eth1",
            "--access",
            "s1-eth2",
            "--uplink",
            "s1-eth3",
            "--remote-id",
            "OLT-1",
            "--dst-mac",
            bng_mac,
            "--src-mac",
            s1_uplink_mac,
        ]
    )

    bng_event_queue: Queue = Queue(maxsize=100)
    bng_stop_event = threading.Event()

    bng_thread = threading.Thread(
        target=bng_event_loop,
        args=(bng, bng_stop_event, bng_event_queue, "bng-eth0", 30),
        daemon=False,
    )
    bng_thread.start()

    sniffer_path = str(Path(__file__).resolve().parent / "bng_dhcp_sniffer.py")
    kea_mac = kea.cmd("cat /sys/class/net/kea-eth0/address").strip()
    bng_uplink_mac = bng.cmd("cat /sys/class/net/bng-eth1/address").strip()
    sniffer_proc = bng.popen(
        [
            sys.executable,
            sniffer_path,
            "--client-if",
            "bng-eth0",
            "--uplink-if",
            "bng-eth1",
            "--server-ip",
            "192.0.2.3",
            "--giaddr",
            "10.0.0.1",
            "--relay-id",
            "192.0.2.1",
            "--src-ip",
            "192.0.2.1",
            "--src-mac",
            bng_uplink_mac,
            "--dst-mac",
            kea_mac,
            "--log",
            "/tmp/bng_dhcp_relay.log",
            "--json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def sniffer_reader():
        if not sniffer_proc.stdout:
            return
        for line in sniffer_proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                bng_event_queue.put(event)
            except Exception:
                continue

    sniffer_thread = threading.Thread(target=sniffer_reader, daemon=True)
    sniffer_thread.start()

    CLI(net)

    try:
        relay_switch_proc.terminate()
        relay_switch_proc.wait(timeout=2)
    except Exception:
        relay_switch_proc.kill()
    if sniffer_proc:
        try:
            sniffer_proc.terminate()
            sniffer_proc.wait(timeout=2)
        except Exception:
            sniffer_proc.kill()
    bng_stop_event.set()
    bng_thread.join()
    kea.cmd('pkill -f "kea-dhcp4 -c /etc/kea/kea-dhcp4.conf" 2>/dev/null || true')
    kea.cmd('pkill -f "kea-ctrl-agent -c /etc/kea/kea-ctrl-agent.conf" 2>/dev/null || true')
    # Also remove the config file to avoid confusion on next run
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
