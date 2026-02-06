FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    freeradius-utils \
    curl \
    iproute2 \
    iputils-ping \
    nftables \
    procps \
    python3 \
    python3-requests \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY bng/lib /opt/bng/lib
COPY bng/bng_main.py /opt/bng/bng_main.py
COPY bng/bng_dhcp_sniffer.py /opt/bng/bng_dhcp_sniffer.py
COPY docker/bng/entrypoint.sh /opt/bng/entrypoint.sh
RUN chmod +x /opt/bng/entrypoint.sh

ENTRYPOINT ["/opt/bng/entrypoint.sh"]
