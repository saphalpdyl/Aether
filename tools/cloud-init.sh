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
  iptables \
  make

echo "==> Installing Docker"
curl -fsSL https://get.docker.com | sh

echo "==> Installing containerlab ${CLAB_VERSION}"
bash -c "$(curl -sL https://get.containerlab.dev)" -- -v "${CLAB_VERSION}"

echo "==> Cloning repository"
git clone "${REPO_URL}" "${LAB_DIR}"

echo "==> Setting up iptables DNAT (port 80/443 -> nginx container)"
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 80 -j DNAT --to-destination "${NGINX_MGMT_IP}":80
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 443 -j DNAT --to-destination "${NGINX_MGMT_IP}":443
iptables -t nat -A POSTROUTING -d "${NGINX_MGMT_IP}" -j MASQUERADE

echo "==> Making iptables rules persistent"
apt-get install -y --no-install-recommends iptables-persistent
netfilter-persistent save

echo "==> Building and deploying lab"
cd "${LAB_DIR}"
ENVIRONMENT=prod make apply MAX_WORKERS=3

echo "==> Done! Lab is running."
