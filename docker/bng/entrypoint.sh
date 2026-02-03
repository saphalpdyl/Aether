#!/bin/sh
set -eu

# Basic startup marker
echo "bng entrypoint start" >> /tmp/bng-entry.log

# Wait for interfaces to appear
for i in $(seq 1 30); do
  if ip link show bng-eth0 >/dev/null 2>&1 && ip link show bng-eth1 >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

ip addr flush dev bng-eth0 || true
ip addr flush dev bng-eth1 || true
ip link set bng-eth0 up
ip link set bng-eth1 up
ip addr add 10.0.0.1/24 dev bng-eth0
ip addr add 192.0.2.1/24 dev bng-eth1
ip route replace default via 192.0.2.5 dev bng-eth1
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true

# nftables setup
nft delete table inet aether_auth 2>/dev/null || true
nft delete table inet bngacct 2>/dev/null || true
nft add table inet aether_auth 2>/dev/null || true
nft add table inet bngacct 2>/dev/null || true
nft 'add set inet aether_auth authed_macs { type ether_addr; }' 2>/dev/null || true
nft 'add chain inet aether_auth forward { type filter hook forward priority -10; policy drop; }' 2>/dev/null || true
nft 'add rule inet aether_auth forward ct state established,related accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "bng-eth0" udp sport 68 udp dport 67 accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "bng-eth1" udp sport 67 udp dport 68 accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "bng-eth0" ether saddr @authed_macs accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "bng-eth0" ct state new tcp reject with tcp reset' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "bng-eth0" ct state new reject with icmpx type admin-prohibited' 2>/dev/null || true
nft 'add chain inet bngacct sess { type filter hook forward priority 0; policy accept; }' 2>/dev/null || true

mkdir -p /tmp/dnsmasq

exec sleep infinity
