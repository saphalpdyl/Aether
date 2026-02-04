#!/bin/sh

# Wait for data-plane interface and DB reachability before starting radius.
for i in $(seq 1 60); do
  if ip link show eth1 >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

ip addr flush dev eth1 2>/dev/null || true
ip link set eth1 up 2>/dev/null || true
ip addr add 192.0.2.2/24 dev eth1 2>/dev/null || true
ip route replace default via 192.0.2.1 dev eth1 2>/dev/null || true

for i in $(seq 1 60); do
  if pg_isready -h 192.0.2.6 -U radius >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Initialize SQL schema if missing (idempotent).
if psql "host=192.0.2.6 user=radius password=test dbname=radius" -tc "SELECT to_regclass('public.radcheck');" | grep -q radcheck; then
  : # already initialized
else
  psql "host=192.0.2.6 user=radius password=test dbname=radius" \
    -f /etc/freeradius/3.0/mods-config/sql/main/postgresql/schema.sql || true
  psql "host=192.0.2.6 user=radius password=test dbname=radius" \
    -f /etc/freeradius/3.0/mods-config/sql/main/postgresql/setup.sql || true
fi

#ln -sf /etc/freeradius/3.0/mods-available/files /etc/freeradius/3.0/mods-enabled/files
ln -sf /etc/freeradius/3.0/mods-available/sql /etc/freeradius/3.0/mods-enabled/sql

for site in /etc/freeradius/3.0/sites-enabled/default /etc/freeradius/3.0/sites-enabled/inner-tunnel; do
  if [ -f "$site" ] && ! grep -q "^[[:space:]]*sql$" "$site"; then
    sed -i '/^[[:space:]]*authorize[[:space:]]*{/a\ \ \ \ sql' "$site"
    sed -i '/^[[:space:]]*accounting[[:space:]]*{/a\ \ \ \ sql' "$site"
  fi
  if [ -f "$site" ] && ! grep -q "^[[:space:]]*files$" "$site"; then
    sed -i '/^[[:space:]]*authorize[[:space:]]*{/a\ \ \ \ files' "$site"
  fi
done

freeradius
