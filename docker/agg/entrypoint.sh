#!/bin/sh
set -eu

echo "Aggregation switch starting..."

# Wait for at least one data interface (eth1) to appear.
for i in $(seq 1 150); do
  if ip link show eth1 >/dev/null 2>&1; then
    echo "Interfaces ready after $i attempts"
    break
  fi
  sleep 0.2
done

ETH_IFACES="$(ls /sys/class/net | grep '^eth' | grep -v '^eth0$' | sort)"
if [ -z "$ETH_IFACES" ]; then
  echo "No data interfaces found (eth1+). Exiting."
  exit 1
fi

# Create bridge
ip link add br0 type bridge 2>/dev/null || true

# Disable STP and set forward delay to 0
ip link set br0 type bridge stp_state 0
ip link set br0 type bridge forward_delay 0

# Disable MAC ageing (keep learned MACs forever)
ip link set br0 type bridge ageing_time 0

# Bring up interfaces with promiscuous mode
for iface in $ETH_IFACES; do
  ip link set "$iface" up
  ip link set "$iface" promisc on
  ip link set "$iface" master br0
  # Enable hairpin mode (allows frames to be sent back out the same port)
  bridge link set dev "$iface" hairpin on 2>/dev/null || true
  # Flood unknown unicast
  bridge link set dev "$iface" flood on 2>/dev/null || true
  # Enable learning
  bridge link set dev "$iface" learning on 2>/dev/null || true
done

# Bring up bridge
ip link set br0 up
ip link set br0 promisc on

# Disable management interface
ip link set eth0 down 2>/dev/null || true

echo "Bridge br0 ready"
ip link show br0
bridge link show

exec sleep infinity
