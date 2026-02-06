#!/bin/sh
set -eu

# Wait for interfaces to appear
for i in $(seq 1 30); do
  if ls /sys/class/net/eth* >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

# Get all data-plane interfaces (skip mgmt eth0)
ifaces=$(ls /sys/class/net | grep '^eth' | grep -v '^eth0$' | sort)
uplink=$(echo "$ifaces" | tail -n 1)
access_ifaces=$(echo "$ifaces" | sed '$d')

# Just bring interfaces UP - don't bridge them
for iface in $ifaces; do
  ip link set "$iface" up
  # Enable promiscuous mode for raw sockets
  ip link set "$iface" promisc on
done

# NO bridge needed - relay_switch.py will forward packets
set -- python3 /opt/relay/relay_switch.py
for iface in $access_ifaces; do
  set -- "$@" --access "$iface"
done
set -- "$@" --uplink "$uplink" --remote-id OLT-1
exec "$@"
