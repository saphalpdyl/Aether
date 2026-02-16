# Golang stage
FROM golang:1.25-bookworm AS coad-build
WORKDIR /src
COPY bng/coad/go.mod bng/coad/go.sum ./
RUN go mod download
COPY bng/coad/ .
RUN CGO_ENABLED=0 go build -o /coad .

# BNG stage
FROM debian:bookworm-slim

# BNG identifier for distributed deployment (set at runtime)
ENV BNG_IDENTIFIER=bng-default
ENV BNG_SUBSCRIBER_IFACE=eth1
ENV BNG_UPLINK_IFACE=eth2
ENV BNG_DHCP_UPLINK_IFACE=eth3
ENV BNG_SUBSCRIBER_IP_CIDR=10.0.0.1/24
ENV BNG_UPLINK_IP_CIDR=192.0.2.1/30
ENV BNG_DHCP_UPLINK_IP_CIDR=198.18.0.1/24
ENV BNG_DEFAULT_GW=192.0.2.2
ENV BNG_NAT_SOURCE_CIDR=10.0.0.0/24
ENV BNG_RELAY1_SUBNET_CIDR=10.0.1.0/26
ENV BNG_RELAY1_NEXT_HOP=10.0.0.2
ENV BNG_RELAY2_SUBNET_CIDR=10.0.1.64/26
ENV BNG_RELAY2_NEXT_HOP=10.0.0.3
ENV BNG_DHCP_SERVER_IP=198.18.0.3
ENV BNG_RADIUS_SERVER_IP=198.18.0.2
ENV BNG_NAS_IP=198.18.0.1
ENV BNG_REDIS_HOST=198.18.0.10
ENV BNG_OSS_API_URL=http://198.18.0.21:8000
ENV BNG_KEA_CTRL_URL=http://198.18.0.3:6772

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    freeradius-utils \
    curl \
    iperf3 \
    iproute2 \
    iputils-ping \
    iptables \
    nftables \
    procps \
    python3 \
    python3-requests \
    python3-redis \
    python3-psutil \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

# Go CoA/DM daemon
COPY --from=coad-build /coad /usr/local/bin/coad

COPY bng/lib /opt/bng/lib
COPY bng/bng_main.py /opt/bng/bng_main.py
COPY bng/bng_dhcp_sniffer.py /opt/bng/bng_dhcp_sniffer.py
COPY docker/bng/entrypoint.sh /opt/bng/entrypoint.sh
RUN chmod +x /opt/bng/entrypoint.sh

ENTRYPOINT ["/opt/bng/entrypoint.sh"]
