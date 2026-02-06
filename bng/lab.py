#!/usr/bin/env python3

import subprocess
import shutil
import time
import builtins

builtins.unicode = str

from mininet.net import Containernet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel


def run():
    net = Containernet(controller=None, switch=OVSSwitch)

    sap = net.addExtSAP(
        'i1',
        sapIP="192.0.2.5/24",
        NAT=True,
    )

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
        network_mode='none',
    )
    net.addLink(h1, relay)
    net.addLink(h2, relay)

    bng = net.addDocker(
        'bng',
        dimage='lab-bng',
        dcmd='sleep infinity',
        ip=None,
        privileged=True,
        network_mode='none',
    )
    net.addLink(bng, relay)  # bng-eth0 subscriber side
    net.addLink(bng, s2)  # bng-eth1 upstream side

    net.addLink(s2, sap)

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

    # Extra NAT for subscriber subnet behind BNG via SAP bridge
    def ensure_ipt(rule_check, rule_add):
        if subprocess.run(rule_check).returncode != 0:
            subprocess.run(rule_add)

    sap_if = sap.deployed_name
    uplink = subprocess.check_output(
        "ip route | awk '$1==\"default\" {print $5; exit}'",
        shell=True,
        text=True,
    ).strip()
    ipt = shutil.which("iptables-legacy") or "iptables"
    subprocess.run(["ip", "route", "replace", "10.0.0.0/24", "via", "192.0.2.1", "dev", sap_if], check=False)
    ensure_ipt(
        [ipt, "-t", "nat", "-C", "POSTROUTING", "-s", "10.0.0.0/24", "-o", uplink, "-j", "MASQUERADE"],
        [ipt, "-t", "nat", "-A", "POSTROUTING", "-s", "10.0.0.0/24", "-o", uplink, "-j", "MASQUERADE"],
    )
    ensure_ipt(
        [ipt, "-C", "FORWARD", "-i", sap_if, "-j", "ACCEPT"],
        [ipt, "-A", "FORWARD", "-i", sap_if, "-j", "ACCEPT"],
    )
    ensure_ipt(
        [ipt, "-C", "FORWARD", "-o", sap_if, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        [ipt, "-A", "FORWARD", "-o", sap_if, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
    )

    bng.cmd('ip route add default via 192.0.2.5 dev bng-eth1')

    # Start relay + bng entrypoints after interfaces exist
    relay.cmd('/opt/relay/entrypoint.sh > /tmp/relay-entry.log 2>&1 &')
    bng.cmd('/opt/bng/entrypoint.sh >> /tmp/bng-entry.log 2>&1 &')

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

    bng.cmd('pkill -f bng_main.py 2>/dev/null || true')
    bng.cmd('nohup python3 /opt/bng/bng_main.py > /tmp/bng_main.log 2>&1 &')

    CLI(net)

    bng.cmd('pkill -f bng_main.py 2>/dev/null || true')
    kea.cmd('pkill -f "kea-dhcp4 -c /etc/kea/kea-dhcp4.conf" 2>/dev/null || true')
    kea.cmd('pkill -f "kea-ctrl-agent -c /etc/kea/kea-ctrl-agent.conf" 2>/dev/null || true')
    # Also remove the config file to avoid confusion on next run
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
