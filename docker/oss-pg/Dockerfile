FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    net-tools \
    procps \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY docker/oss-pg/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY docker/oss-pg/init/ /docker-entrypoint-initdb.d/

CMD ["postgres", "-c", "listen_addresses=*"]
