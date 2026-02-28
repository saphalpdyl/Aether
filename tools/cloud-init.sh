#!/bin/bash
set -euo pipefail
# Aether Lab - Hetzner cloud-init script
# Paste this into the "Cloud config" field when creating a Hetzner server,
# or run it manually on a fresh Ubuntu server.
#
# Usage (cloud-init):
#   Paste into Hetzner's "User data" / "Cloud config" field as-is.
#
# Usage (manual):
#   curl -sL https://raw.githubusercontent.com/saphalpdyl/Aether/master/tools/cloud-init.sh | bash
#
# NOTE: After first boot, run the following to obtain a TLS certificate:
#   certbot --nginx -d aether.saphal.me
#   systemctl reload nginx

REPO_URL="https://github.com/saphalpdyl/Aether.git"
LAB_DIR="/root/lab"
CLAB_VERSION="0.72.0"
NGINX_MGMT_IP="172.20.20.23"
export DEBIAN_FRONTEND=noninteractive

echo "==> Installing system packages"
apt-get update
apt-get install -y --no-install-recommends \
  python3 \
  python3-pip \
  python3-yaml \
  python3-jinja2 \
  make

echo "==> Installing Docker"
curl -fsSL https://get.docker.com | sh

echo "==> Installing containerlab ${CLAB_VERSION}"
bash -c "$(curl -sL https://get.containerlab.dev)" -- -v "${CLAB_VERSION}"

echo "==> Cloning repository"
git clone "${REPO_URL}" "${LAB_DIR}"

echo "==> Installing nginx and certbot"
apt-get install -y --no-install-recommends nginx certbot python3-certbot-nginx

echo "==> Setting up maintenance page"
mkdir -p /var/www/maintenance
cp "${LAB_DIR}/cloud/nginx/maintenance/maintenance.html" /var/www/maintenance/maintenance.html

cat > /etc/nginx/sites-available/maintenance <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name aether.saphal.me;

    root /var/www/maintenance;

    location / {
        return 503;
    }

    error_page 503 /maintenance.html;

    location = /maintenance.html {
        internal;
    }
}
EOF

echo "==> Writing nginx aether configuration"
cat > /etc/nginx/sites-available/aether <<'EOF'
# Temporary HTTP-only config until cert is provisioned.
# After running certbot, this file will be updated automatically.
server {
    listen 80;
    listen [::]:80;
    server_name aether.saphal.me;

    location / {
        proxy_pass http://172.20.20.23:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/aether /etc/nginx/sites-enabled/aether
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable --now nginx

echo "==> Building and deploying lab"
cd "${LAB_DIR}"
ENVIRONMENT=prod make apply MAX_WORKERS=3

echo "==> Setting up certbot for TLS certificate provisioning"
certbot --nginx -d aether.saphal.me
systemctl reload nginx

echo "==> Done! Lab is running."