#!/bin/sh
set -eu

# Basic startup marker
echo "bng entrypoint start" >> /tmp/bng-entry.log

subscriber_if="${BNG_SUBSCRIBER_IFACE:-eth1}"
uplink_if="${BNG_UPLINK_IFACE:-eth2}"
dhcp_uplink_if="${BNG_DHCP_UPLINK_IFACE:-eth3}"
subscriber_ip_cidr="${BNG_SUBSCRIBER_IP_CIDR:-10.0.0.1/24}"
uplink_ip_cidr="${BNG_UPLINK_IP_CIDR:-192.0.2.1/30}"
dhcp_uplink_ip_cidr="${BNG_DHCP_UPLINK_IP_CIDR:-198.18.0.1/24}"
default_gw="${BNG_DEFAULT_GW:-192.0.2.2}"
nat_source_cidr="${BNG_NAT_SOURCE_CIDR:-10.0.0.0/24}"

# Wait for interfaces to appear
for i in $(seq 1 30); do
  if ip link show "$subscriber_if" >/dev/null 2>&1 && ip link show "$uplink_if" >/dev/null 2>&1 && ip link show "$dhcp_uplink_if" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

ip addr flush dev "$subscriber_if" || true
ip addr flush dev "$uplink_if" || true
ip addr flush dev "$dhcp_uplink_if" || true
ip link set "$subscriber_if" mtu 1500
ip link set "$subscriber_if" up
ip link set "$uplink_if" up
ip link set "$dhcp_uplink_if" up
ip addr add "$subscriber_ip_cidr" dev "$subscriber_if"
ip addr add "$uplink_ip_cidr" dev "$uplink_if"
ip addr add "$dhcp_uplink_ip_cidr" dev "$dhcp_uplink_if"
ip route replace default via "$default_gw" dev "$uplink_if"
# Routes to DHCP relay gi-addresses and client subnets
i=1
while [ "$i" -le 64 ]; do
  eval relay_subnet_cidr=\${BNG_RELAY${i}_SUBNET_CIDR:-}
  eval relay_next_hop=\${BNG_RELAY${i}_NEXT_HOP:-}
  if [ -n "$relay_subnet_cidr" ] && [ -n "$relay_next_hop" ]; then
    ip route add "$relay_subnet_cidr" via "$relay_next_hop" dev "$subscriber_if" || true
  fi
  i=$((i + 1))
done
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true

# MSS clamping - standard ISP practice to prevent oversized TCP segments
# on paths with mixed MTUs (veth 9500 vs SR Linux port MTU ~9232)
# Use --set-mss (not --clamp-mss-to-pmtu) because clamp-mss-to-pmtu derives
# from the outgoing interface MTU.
iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1460

# Disable conntrack checksum validation - SR Linux's dataplane doesn't
# finalize veth TX checksum offload, so forwarded packets arrive at BNG
# with partial checksums that conntrack would otherwise mark INVALID
sysctl -w net.netfilter.nf_conntrack_checksum=0 >/dev/null 2>&1 || true

# NAT FIRST - set up before any ct state rules
nft delete table ip nat 2>/dev/null || true
nft add table ip nat
nft "add chain ip nat postrouting { type nat hook postrouting priority 100; policy accept; }"
nft "add rule ip nat postrouting ip saddr $nat_source_cidr oifname \"$uplink_if\" masquerade"

# nftables filtering setup
nft delete table inet aether_auth 2>/dev/null || true
nft delete table inet bngacct 2>/dev/null || true
nft add table inet aether_auth 2>/dev/null || true
nft add table inet bngacct 2>/dev/null || true
nft "add set inet aether_auth authed_ips { type ipv4_addr; }" 2>/dev/null || true
nft "add chain inet aether_auth forward { type filter hook forward priority -10; policy drop; }" 2>/dev/null || true
nft "add rule inet aether_auth forward ct state established,related accept" 2>/dev/null || true
# Allow ICMP through for PMTU discovery (frag needed), ping, traceroute
nft "add rule inet aether_auth forward ip protocol icmp accept" 2>/dev/null || true
nft "add rule inet aether_auth forward iifname \"$subscriber_if\" udp sport 68 udp dport 67 accept" 2>/dev/null || true
nft "add rule inet aether_auth forward iifname \"$dhcp_uplink_if\" udp sport 67 udp dport 68 accept" 2>/dev/null || true
nft "add rule inet aether_auth forward iifname \"$subscriber_if\" ip saddr @authed_ips accept" 2>/dev/null || true
# Reject unauthorized traffic (after authed_macs rule)
nft "add rule inet aether_auth forward iifname \"$subscriber_if\" reject" 2>/dev/null || true
nft "add chain inet bngacct sess { type filter hook forward priority 0; policy accept; }" 2>/dev/null || true

mkdir -p /tmp/dnsmasq

exec sleep infinity
