FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    net-tools \
    procps \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

COPY docker/radius-pg/init/00-radius-hba.sh /docker-entrypoint-initdb.d/00-radius-hba.sh
RUN chmod +x /docker-entrypoint-initdb.d/00-radius-hba.sh
