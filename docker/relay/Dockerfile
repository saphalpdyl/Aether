FROM python:3.11-slim

ENV RELAY_BR_IP_CIDR=10.0.1.1/26
ENV RELAY_UPLINK_IP_CIDR=10.0.0.2/24
ENV RELAY_DEFAULT_GW=10.0.0.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    nftables \
    tcpdump \
    ebtables \
    iproute2 \
    iputils-ping \
  && rm -rf /var/lib/apt/lists/*

COPY bng/relay_switch.py /opt/relay/relay_switch.py
COPY docker/relay/entrypoint.sh /opt/relay/entrypoint.sh
RUN chmod +x /opt/relay/entrypoint.sh

ENTRYPOINT ["/opt/relay/entrypoint.sh"]
