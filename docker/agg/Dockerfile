FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bridge-utils \
    iproute2 \
    procps \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY docker/agg/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
