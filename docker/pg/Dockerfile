FROM postgres:16
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    net-tools \
    procps \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY docker/pg/init/00-kea-hba.sh /docker-entrypoint-initdb.d/00-kea-hba.sh
RUN chmod +x /docker-entrypoint-initdb.d/00-kea-hba.sh

# Let the default entrypoint handle everything
CMD ["postgres", "-c", "listen_addresses=*"]
