FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    procps \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir redis psycopg2-binary

COPY bng-ingestor/ /opt/ingestor/
COPY docker/bng-ingestor/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
