#!/usr/bin/env python3

import json
import threading
import subprocess
import shlex
import re
from queue import Queue
import time

from mininet.net import Containernet
from mininet.node import Docker, OVSSwitch
from mininet.nodelib import NAT
from mininet.cli import CLI
from mininet.log import setLogLevel

from lib.services.bng import bng_event_loop

def run():
    net = Containernet(controller=None, switch=OVSSwitch)

    # Canonical switch names so Mininet can derive DPIDs
    s2 = net.addSwitch('s2', failMode='standalone')  # upstream

    h1 = net.addHost('h1', ip=None, mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip=None, mac='00:00:00:00:00:02')

    relay = net.addDocker(
        'relay',
        dimage='lab-relay',
        dcmd='sleep infinity',
        ip=None,
        privileged=True,
    )
    net.addLink(h1, relay)
    net.addLink(h2, relay)

    bng = net.addDocker(
        'bng',
        dimage='lab-bng',
        dcmd='sleep infinity',
        ip=None,
        privileged=True,
    )
    net.addLink(bng, relay)  # bng-eth0 subscriber side
    net.addLink(bng, s2)  # bng-eth1 upstream side

    nat = net.addHost('nat', cls=NAT, ip='192.0.2.5/24', inNamespace=False)
    net.addLink(nat, s2)  # nat-eth0 on upstream segment

    radius = net.addDocker(
        'radius',
        dimage='lab-radius',
        ip=None,
        dcmd="/bin/sh -c '/opt/radius/entrypoint.sh 2>&1 || sleep infinity'",
        privileged=False,
    )
    net.addLink(radius, s2)  # radius-eth0 on upstream segment

    radius_pg = net.addDocker(
        'radius_pg',
        dimage='lab-radius-pg',
        ip=None,
        privileged=False,
        environment={
            'POSTGRES_DB': 'radius',
            'POSTGRES_USER': 'radius',
            'POSTGRES_PASSWORD': 'test',
        },
        dcmd='docker-entrypoint.sh postgres -c listen_addresses=*'
    )
    net.addLink(radius_pg, s2)  # radius-pg-eth0 on upstream segment

    pg = net.addDocker(
        'pg',
        dimage='lab-pg',
        ip=None,
        privileged=False,
        environment={
            'POSTGRES_DB': 'kea_lease_db',
            'POSTGRES_USER': 'kea',
            'POSTGRES_PASSWORD': 'test',
        },
        ports=[5432],
        port_bindings={5432: 5432},
        dcmd='docker-entrypoint.sh postgres -c listen_addresses=*'
    )
    net.addLink(pg, s2)  # pg-eth0 on upstream segment

    kea = net.addDocker(
        'kea',
        dimage='lab-kea',
        ip=None,
        privileged=True,
    )
    net.addLink(kea, s2)  # kea-eth0 on upstream segment

    net.start()
    net.waitConnected()

    # Start relay + bng entrypoints after interfaces exist
    relay.cmd('/opt/relay/entrypoint.sh > /tmp/relay-entry.log 2>&1 &')
    bng.cmd('/opt/bng/entrypoint.sh >> /tmp/bng-entry.log 2>&1 &')

    # Root-namespace NAT (known-good baseline)
    nat.configDefault()
    nat.cmd('ip route replace 10.0.0.0/24 via 192.0.2.1 dev nat-eth0')

    # RADIUS server container
    radius.cmd('ip addr flush dev radius-eth0')
    radius.cmd('ip link set radius-eth0 up')
    radius.cmd('ip addr add 192.0.2.2/24 dev radius-eth0')
    radius.cmd('ip route replace default via 192.0.2.1 dev radius-eth0')

    radius_pg.cmd('ip addr flush dev radius_pg-eth0')
    radius_pg.cmd('ip link set radius_pg-eth0 up')
    radius_pg.cmd('ip addr add 192.0.2.6/24 dev radius_pg-eth0')
    radius_pg.cmd('ip route replace default via 192.0.2.1 dev radius_pg-eth0')

    radius.cmd(
        "psql \"host=192.0.2.6 user=radius password=test dbname=radius\" "
        "-tc \"SELECT to_regclass('public.radcheck');\" | grep -q radcheck || "
        "psql \"host=192.0.2.6 user=radius password=test dbname=radius\" "
        "-f /etc/freeradius/3.0/mods-config/sql/main/postgresql/schema.sql "
        "2>/tmp/radius_schema.err || true"
    )
    radius.cmd(
        "psql \"host=192.0.2.6 user=radius password=test dbname=radius\" "
        "-tc \"SELECT to_regclass('public.radcheck');\" | grep -q radcheck || "
        "psql \"host=192.0.2.6 user=radius password=test dbname=radius\" "
        "-f /etc/freeradius/3.0/mods-config/sql/main/postgresql/setup.sql "
        "2>/tmp/radius_setup.err || true"
    )

    time.sleep(3)
    # PostgreSQL container for Kea leases
    pg.cmd('ip addr flush dev pg-eth0')
    pg.cmd('ip link set pg-eth0 up')
    pg.cmd('ip addr add 192.0.2.4/24 dev pg-eth0')
    pg.cmd('ip route replace default via 192.0.2.1 dev pg-eth0')
    # KEA DHCPv4 server host
    kea.cmd('ip addr flush dev kea-eth0')
    kea.cmd('ip link set kea-eth0 up')
    kea.cmd('ip addr add 192.0.2.3/24 dev kea-eth0')
    kea.cmd('ip route replace default via 192.0.2.1 dev kea-eth0')
    kea.cmd('kea-admin db-init pgsql -u kea -p test -n kea_lease_db -h 192.0.2.4')
    kea.cmd('rm -f /tmp/kea/logger_lockfile 2>/dev/null || true')
    kea.cmd('mkdir -p /run/kea')
    kea.cmd('chmod 777 /run/kea')
    kea.cmd('KEA_LOCKFILE_DIR=none kea-dhcp4 -c /etc/kea/kea-dhcp4.conf > /tmp/kea-dhcp4.log 2>&1 &')

    kea.cmd('rm -f /run/kea/kea-ctrl-agent.*.pid')
    kea.cmd('KEA_LOCKFILE_DIR=none kea-ctrl-agent -c /etc/kea/kea-ctrl-agent.conf > /tmp/kea-ctrl-agent.log 2>&1 &')

    # OLT processor runs in root namespace
    bng_event_queue: Queue = Queue(maxsize=100)
    bng_stop_event = threading.Event()

    bng_thread = threading.Thread(
        target=bng_event_loop,
        args=(bng, bng_stop_event, bng_event_queue, "bng-eth0", 30),
        daemon=False,
    )
    bng_thread.start()

    sniffer_path = "/opt/bng/bng_dhcp_sniffer.py"
    def _clean_mac(raw: str) -> str:
        token = raw.strip().split()[0] if raw else ""
        token = token.lower()
        token = re.sub(r"[^0-9a-f:]", "", token)
        return token

    kea_mac = _clean_mac(kea.cmd("cat /sys/class/net/kea-eth0/address"))
    bng_uplink_mac = _clean_mac(bng.cmd("cat /sys/class/net/bng-eth1/address"))
    for _ in range(20):
        if bng.cmd('ip link show bng-eth0 >/dev/null 2>&1 && ip link show bng-eth1 >/dev/null 2>&1; echo $?').strip() == "0":
            break
        time.sleep(0.5)

    bng.cmd("pkill -f bng_dhcp_sniffer.py 2>/dev/null || true")
    bng.cmd("rm -f /tmp/bng_dhcp_events.json /tmp/bng_dhcp_sniffer.stderr")
    sniffer_q = shlex.quote(sniffer_path)
    src_mac_q = shlex.quote(bng_uplink_mac)
    dst_mac_q = shlex.quote(kea_mac)
    bng.cmd(
        "nohup python3 {sniffer} "
        "--client-if bng-eth0 --uplink-if bng-eth1 "
        "--server-ip 192.0.2.3 --giaddr 10.0.0.1 --relay-id 192.0.2.1 "
        "--src-ip 192.0.2.1 --src-mac {src_mac} --dst-mac {dst_mac} "
        "--log /tmp/bng_dhcp_relay.log --json "
        "> /tmp/bng_dhcp_events.json 2> /tmp/bng_dhcp_sniffer.stderr &".format(
            sniffer=sniffer_q,
            src_mac=src_mac_q,
            dst_mac=dst_mac_q,
        )
    )

    sniffer_proc = bng.popen(
        ["tail", "-F", "/tmp/bng_dhcp_events.json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def sniffer_reader():
        if not sniffer_proc or not sniffer_proc.stdout:
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
