#!/bin/sh
set -eu

# Basic startup marker
echo "bng entrypoint start" >> /tmp/bng-entry.log

# Wait for interfaces to appear (eth1 = subscriber, eth2 = upstream)
for i in $(seq 1 30); do
  if ip link show eth1 >/dev/null 2>&1 && ip link show eth2 >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

ip addr flush dev eth1 || true
ip addr flush dev eth2 || true
ip link set eth1 up
ip link set eth2 up
ip addr add 10.0.0.1/24 dev eth1
ip addr add 192.0.2.1/24 dev eth2
ip route replace default via 192.0.2.5 dev eth2
# Routes to DHCP relay gi-addresses and client subnets
# srl: gi-addr 10.0.1.1, clients 10.0.1.0/26 -> via 10.0.0.2
# srl2: gi-addr 10.0.1.2, clients 10.0.1.64/26 -> via 10.0.0.3
ip route add 10.0.1.0/26 via 10.0.0.2 dev eth1 || true
ip route add 10.0.1.64/26 via 10.0.0.3 dev eth1 || true
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true

# NAT FIRST - set up before any ct state rules
nft delete table ip nat 2>/dev/null || true
nft add table ip nat
nft 'add chain ip nat postrouting { type nat hook postrouting priority 100; policy accept; }'
nft 'add rule ip nat postrouting ip saddr 10.0.0.0/24 oifname "eth2" masquerade'

# nftables filtering setup
nft delete table inet aether_auth 2>/dev/null || true
nft delete table inet bngacct 2>/dev/null || true
nft add table inet aether_auth 2>/dev/null || true
nft add table inet bngacct 2>/dev/null || true
nft 'add set inet aether_auth authed_ips { type ipv4_addr; }' 2>/dev/null || true
nft 'add chain inet aether_auth forward { type filter hook forward priority -10; policy drop; }' 2>/dev/null || true
nft 'add rule inet aether_auth forward ct state established,related accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "eth1" udp sport 68 udp dport 67 accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "eth2" udp sport 67 udp dport 68 accept' 2>/dev/null || true
nft 'add rule inet aether_auth forward iifname "eth1" ip saddr @authed_ips accept' 2>/dev/null || true
# Reject unauthorized traffic (after authed_macs rule)
nft 'add rule inet aether_auth forward iifname "eth1" reject' 2>/dev/null || true
nft 'add chain inet bngacct sess { type filter hook forward priority 0; policy accept; }' 2>/dev/null || true

mkdir -p /tmp/dnsmasq

exec sleep infinity
