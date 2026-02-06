#!/bin/sh
set -eu

HBA_FILE="${PGDATA}/pg_hba.conf"
LINE="host    kea_lease_db    kea             192.0.2.0/24            md5"

if ! grep -Fqs "$LINE" "$HBA_FILE"; then
  printf "\n%s\n" "$LINE" >> "$HBA_FILE"
fi
