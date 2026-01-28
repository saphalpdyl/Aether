#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.nodelib import NAT
from mininet.cli import CLI
from mininet.log import setLogLevel

import time 
import threading
from queue import Queue
from watchdog.observers import Observer

from lib.constants import DHCP_LEASE_FILE_PATH, DHCP_LEASE_FILE_DIR_PATH
from lib.services.bng import bng_event_loop
from lib.services.lease_watcher import LeaseObserver

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

    bng.cmd(f'rm -f /tmp/dnsmasq-bng.pid 2>/dev/null || true')
    bng.cmd(f'rm -f {DHCP_LEASE_FILE_PATH} 2>/dev/null || true')

    # Create the DHCP lease file directory
    bng.cmd('mkdir -p ' + DHCP_LEASE_FILE_DIR_PATH)
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
    time.sleep(0.2)
    bng_event_queue: Queue = Queue(maxsize=1)
    bng_stop_event = threading.Event()

    def notify_bng_thread():
        try:
            bng_event_queue.put_nowait("lease_changed")
        except Exception:
            pass

    dhcp_observer = Observer()
    dhcp_observer.schedule(LeaseObserver(notify_bng_thread), path=DHCP_LEASE_FILE_DIR_PATH, recursive=False)
    dhcp_observer.start()

    bng_thread = threading.Thread(
        target=bng_event_loop,
        args=(bng, bng_stop_event, bng_event_queue, "bng-eth0", 30),
        daemon=False,
    )
    bng_thread.start()

    CLI(net)

    # Stopping watcher thread
    bng_stop_event.set()
    try:
        bng_event_queue.put_nowait("stop")
    except Exception:
        pass
    bng_thread.join()
    dhcp_observer.stop()
    dhcp_observer.join()

    bng.cmd('kill $(cat /tmp/dnsmasq-bng.pid) 2>/dev/null || true')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
