#!/bin/sh
set -eu

if [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export POSTGRES_HOST_AUTH_METHOD="${POSTGRES_HOST_AUTH_METHOD:-md5}"
else
  export POSTGRES_HOST_AUTH_METHOD="${POSTGRES_HOST_AUTH_METHOD:-trust}"
fi

if [ -n "${PGDATA:-}" ] && [ -f "${PGDATA}/postgresql.conf" ]; then
  sed -i "s/^#listen_addresses =.*/listen_addresses = '*'/" "${PGDATA}/postgresql.conf" || true
fi

exec /usr/local/bin/docker-entrypoint.sh "$@"
