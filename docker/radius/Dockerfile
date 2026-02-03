FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    freeradius \
    freeradius-postgresql \
    iproute2 \
    iputils-ping \
    procps \
    postgresql-client \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY docker/radius/raddb/ /etc/freeradius/3.0/
COPY docker/radius/entrypoint.sh /opt/radius/entrypoint.sh
RUN chmod +x /opt/radius/entrypoint.sh

ENTRYPOINT ["/opt/radius/entrypoint.sh"]
