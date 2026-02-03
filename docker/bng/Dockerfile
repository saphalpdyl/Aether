FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    freeradius-utils \
    iproute2 \
    iputils-ping \
    nftables \
    procps \
    python3 \
    python3-requests \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY mininet/lib /opt/bng/lib
COPY mininet/bng_event_server.py /opt/bng/bng_event_server.py
COPY mininet/bng_dhcp_sniffer.py /opt/bng/bng_dhcp_sniffer.py
COPY docker/bng/entrypoint.sh /opt/bng/entrypoint.sh
RUN chmod +x /opt/bng/entrypoint.sh

ENTRYPOINT ["/opt/bng/entrypoint.sh"]
