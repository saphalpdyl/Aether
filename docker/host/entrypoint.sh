#!/bin/sh
set -eu

SUBSCRIBER_IFACE="${SUBSCRIBER_IFACE:-eth1}"
HOST_MAC="${HOST_MAC:-}"
DISABLE_MGMT_IFACE="${DISABLE_MGMT_IFACE:-true}"

# Wait briefly for interfaces to appear under containerlab.
for _ in $(seq 1 50); do
  if ip link show "$SUBSCRIBER_IFACE" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

if ip link show "$SUBSCRIBER_IFACE" >/dev/null 2>&1; then
  if [ -n "$HOST_MAC" ]; then
    ip link set "$SUBSCRIBER_IFACE" address "$HOST_MAC" || true
  fi
  ip link set "$SUBSCRIBER_IFACE" up || true
fi

if [ "$DISABLE_MGMT_IFACE" = "true" ]; then
  ip link set eth0 down || true
fi

exec tail -f /dev/null
