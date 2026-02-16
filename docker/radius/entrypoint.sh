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
ip addr add 198.18.0.2/24 dev eth1 2>/dev/null || true
ip route replace default via 198.18.0.254 dev eth1 2>/dev/null || true

# Ensure custom OSS dictionary is loaded.
if [ -f /etc/freeradius/3.0/dictionary.oss ] && ! grep -q '^\$INCLUDE[[:space:]]\+dictionary\.oss$' /etc/freeradius/3.0/dictionary; then
  echo '$INCLUDE dictionary.oss' >> /etc/freeradius/3.0/dictionary
fi

for i in $(seq 1 60); do
  if pg_isready -h 198.18.0.6 -U radius >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Initialize SQL schema if missing (idempotent).
if psql "host=198.18.0.6 user=radius password=test dbname=radius" -tc "SELECT to_regclass('public.radcheck');" | grep -q radcheck; then
  : # already initialized
else
  psql "host=198.18.0.6 user=radius password=test dbname=radius" \
    -f /etc/freeradius/3.0/mods-config/sql/main/postgresql/schema.sql || true
  psql "host=198.18.0.6 user=radius password=test dbname=radius" \
    -f /etc/freeradius/3.0/mods-config/sql/main/postgresql/setup.sql || true
fi

# Seed default plan policies into group reply attributes (idempotent).
psql "host=198.18.0.6 user=radius password=test dbname=radius" <<'SQL'
DELETE FROM radgroupreply
WHERE groupname IN ('Bronze 25/10', 'Silver 100/30', 'Gold 300/100', 'Legacy 10/5')
  AND attribute IN ('OSS-Download-Speed', 'OSS-Upload-Speed', 'OSS-Download-Burst', 'OSS-Upload-Burst');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
  ('Bronze 25/10', 'OSS-Download-Speed', ':=', '25000'),
  ('Bronze 25/10', 'OSS-Upload-Speed',   ':=', '10000'),
  ('Bronze 25/10', 'OSS-Download-Burst', ':=', '1000'),
  ('Bronze 25/10', 'OSS-Upload-Burst',   ':=', '500'),
  ('Silver 100/30', 'OSS-Download-Speed', ':=', '100000'),
  ('Silver 100/30', 'OSS-Upload-Speed',   ':=', '30000'),
  ('Silver 100/30', 'OSS-Download-Burst', ':=', '3000'),
  ('Silver 100/30', 'OSS-Upload-Burst',   ':=', '1200'),
  ('Gold 300/100', 'OSS-Download-Speed',  ':=', '300000'),
  ('Gold 300/100', 'OSS-Upload-Speed',    ':=', '100000'),
  ('Gold 300/100', 'OSS-Download-Burst',  ':=', '8000'),
  ('Gold 300/100', 'OSS-Upload-Burst',    ':=', '3000'),
  ('Legacy 10/5', 'OSS-Download-Speed',   ':=', '10000'),
  ('Legacy 10/5', 'OSS-Upload-Speed',     ':=', '5000'),
  ('Legacy 10/5', 'OSS-Download-Burst',   ':=', '500'),
  ('Legacy 10/5', 'OSS-Upload-Burst',     ':=', '250');

-- Seed default subscriber: Acme Bakery on cstm-relay-01 (Gold 300/100)
DELETE FROM radcheck WHERE username = 'bng-01/cstm-relay-01/1/0/2';
INSERT INTO radcheck (username, attribute, op, value) VALUES
  ('bng-01/cstm-relay-01/1/0/2', 'Cleartext-Password', ':=', 'testing123');

DELETE FROM radusergroup WHERE username = 'bng-01/cstm-relay-01/1/0/2';
INSERT INTO radusergroup (username, groupname, priority) VALUES
  ('bng-01/cstm-relay-01/1/0/2', 'Gold 300/100', 1);
SQL

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
