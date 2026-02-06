#!/bin/sh
set -eu

echo "Aggregation switch starting..."

# Wait for interfaces
for i in $(seq 1 30); do
  if ip link show eth1 >/dev/null 2>&1 && \
     ip link show eth2 >/dev/null 2>&1 && \
     ip link show eth3 >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

# Create bridge
ip link add br0 type bridge 2>/dev/null || true

# Disable STP and set forward delay to 0
ip link set br0 type bridge stp_state 0
ip link set br0 type bridge forward_delay 0

# Bring up interfaces
ip link set eth1 up
ip link set eth2 up
ip link set eth3 up

# Add to bridge
ip link set eth1 master br0
ip link set eth2 master br0
ip link set eth3 master br0

# Bring up bridge
ip link set br0 up

# Disable management interface
ip link set eth0 down 2>/dev/null || true

echo "Bridge br0 ready with eth1, eth2, eth3"
ip link show br0
bridge link show

exec sleep infinity
