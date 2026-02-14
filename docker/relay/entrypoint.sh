#!/bin/sh
set -eu

# Wait for interfaces to appear
ifaces=""
for i in $(seq 1 30); do
  ifaces=$(ls /sys/class/net | grep '^eth' | grep -v '^eth0$' || true)
  if [ -n "$ifaces" ]; then
    break
  fi
  sleep 0.2
done

# Get all data-plane interfaces (skip mgmt eth0)
if [ -z "$ifaces" ]; then
  echo "No data-plane interfaces found; sleeping for debug"
  exec sleep infinity
fi
ifaces=$(printf '%s\n' "$ifaces" | sort)
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
remote_id="${REMOTE_ID:-OLT-1}"
set -- "$@" --uplink "$uplink" --remote-id "$remote_id"

if [ -n "${GIADDR:-}" ]; then
  set -- "$@" --giaddr "$GIADDR"
fi

if [ -n "${CIRCUIT_ID:-}" ]; then
  set -- "$@" --circuit-id "$CIRCUIT_ID"
fi

if [ -n "${CIRCUIT_ID_MAP:-}" ]; then
  OLDIFS=$IFS
  IFS=','
  for mapping in $CIRCUIT_ID_MAP; do
    [ -n "$mapping" ] && set -- "$@" --circuit-id-map "$mapping"
  done
  IFS=$OLDIFS
fi

exec "$@"
