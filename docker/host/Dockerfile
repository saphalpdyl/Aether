FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    dnsutils \
    iperf3 \
    iproute2 \
    iputils-ping \
    isc-dhcp-client \
  && rm -rf /var/lib/apt/lists/*

COPY docker/host/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
