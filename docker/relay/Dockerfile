FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    nftables \
    tcpdump \
    ebtables \
    iproute2 \
    iputils-ping \
  && rm -rf /var/lib/apt/lists/*

COPY mininet/relay_switch.py /opt/relay/relay_switch.py
COPY docker/relay/entrypoint.sh /opt/relay/entrypoint.sh
RUN chmod +x /opt/relay/entrypoint.sh

ENTRYPOINT ["/opt/relay/entrypoint.sh"]
