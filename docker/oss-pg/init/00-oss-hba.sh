#!/bin/sh
set -eu

HBA_FILE="${PGDATA}/pg_hba.conf"
LINE="host    oss    oss         198.18.0.0/24            md5"

if ! grep -Fqs "$LINE" "$HBA_FILE"; then
  printf "\n%s\n" "$LINE" >> "$HBA_FILE"
fi
