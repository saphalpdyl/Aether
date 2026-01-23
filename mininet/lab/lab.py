#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.nodelib import NAT
from mininet.cli import CLI
from mininet.log import setLogLevel


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

    CLI(net)
    bng.cmd('kill $(cat /tmp/dnsmasq-bng.pid) 2>/dev/null || true')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()

