#!/bin/sh

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

exec freeradius -f
