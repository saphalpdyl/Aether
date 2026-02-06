FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iproute2 \
    iputils-ping \
    kea-admin \
    kea-ctrl-agent \
    kea-dhcp4-server \
    postgresql-client \
    tcpdump \
    procps \
  && rm -rf /var/lib/apt/lists/*

COPY bng/conf/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf
COPY bng/conf/kea-ctrl-agent.conf /etc/kea/kea-ctrl-agent.conf

ENTRYPOINT ["sleep", "infinity"]
