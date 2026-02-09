#!/bin/sh
set -eu

# Background network configuration - keeps trying until eth1 exists
configure_network() {
    while true; do
        if ip link show eth1 >/dev/null 2>&1; then
            ip addr flush dev eth1 2>/dev/null || true
            ip link set eth1 up 2>/dev/null || true
            ip addr add 192.0.2.11/24 dev eth1 2>/dev/null || true
            ip route replace default via 192.0.2.5 2>/dev/null || true
            echo "Network configured on eth1"
            break
        fi
        sleep 1
    done
}

# Run network config in background so postgres can start
configure_network &

# Run the original postgres entrypoint
exec docker-entrypoint.sh "$@"
