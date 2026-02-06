#!/bin/sh
set -eu

# Wait for eth1 to appear
for i in $(seq 1 30); do
  ip link show eth1 >/dev/null 2>&1 && break
  sleep 0.2
done

exec redis-server --bind 0.0.0.0 --protected-mode no
