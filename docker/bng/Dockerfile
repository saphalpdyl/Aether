# Golang stage
FROM golang:1.25-bookworm AS coad-build
WORKDIR /src
COPY bng/coad/go.mod bng/coad/go.sum ./
RUN go mod download
COPY bng/coad/ .
RUN CGO_ENABLED=0 go build -o /coad .

# BNG stage
FROM debian:bookworm-slim

# BNG identifier for distributed deployment (set at runtime)
ENV BNG_IDENTIFIER=bng-default

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
    python3-redis \
    python3-psutil \
    tcpdump \
  && rm -rf /var/lib/apt/lists/*

# Go CoA/DM daemon
COPY --from=coad-build /coad /usr/local/bin/coad

COPY bng/lib /opt/bng/lib
COPY bng/bng_main.py /opt/bng/bng_main.py
COPY bng/bng_dhcp_sniffer.py /opt/bng/bng_dhcp_sniffer.py
COPY docker/bng/entrypoint.sh /opt/bng/entrypoint.sh
RUN chmod +x /opt/bng/entrypoint.sh

ENTRYPOINT ["/opt/bng/entrypoint.sh"]
