#!/bin/sh
set -eu
for i in $(seq 1 30); do
  if ls /sys/class/net/relay-eth* >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

ifaces=$(ls /sys/class/net | grep '^relay-eth' | sort)
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
