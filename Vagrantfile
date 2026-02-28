# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# Aether Lab - Local demo via Vagrant
#
# Prerequisites:
#   - Vagrant (https://www.vagrantup.com/)
#   - A provider: libvirt (recommended) or VirtualBox
#
# Usage:
#   vagrant up
#   vagrant ssh
#
# After provisioning, the lab will be running inside the VM.
# The VM gets a network IP (e.g. 192.168.122.x) — check with `vagrant ssh -c "hostname -I"`.
# An nginx reverse proxy on the VM forwards traffic to the containerlab management network.
#

# During provisioning, Vagrant will ask for the interface, make sure to select the one that corresponds to your host's network (e.g. enp1s0 for me).

##### NOTE #####
# NOTE: The initial setup install dependencies and builds docker images, so it will take ~10 minutes
##### NOTE #####

CLAB_VERSION = "0.72.0"

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"
  config.vm.hostname = "aether-lab"

  # Provider: libvirt
  config.vm.provider "libvirt" do |lv|
    lv.memory = 4096
    lv.cpus = 2
  end

  # Provider: VirtualBox
  config.vm.provider "virtualbox" do |vb|
    vb.memory = 4096
    vb.cpus = 2
  end

  # Bridge to the host network so the VM gets a routable IP (e.g. 192.168.122.x)
  config.vm.network "public_network"

  # Sync the project as a read-only source; we copy it locally inside the VM
  # so that generated files don't leak back to the host.
  config.vm.synced_folder ".", "/vagrant"

  # --- Stage 1: Install dependencies (runs once on first `vagrant up`) ---
  config.vm.provision "setup", type: "shell", inline: <<~SHELL
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    echo "==> Installing system packages"
    apt-get update
    apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-yaml \
      python3-jinja2 \
      make \
      git

    echo "==> Installing Docker"
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker vagrant

    echo "==> Installing containerlab #{CLAB_VERSION}"
    bash -c "$(curl -sL https://get.containerlab.dev)" -- -v "#{CLAB_VERSION}"

    echo "==> Installing nginx"
    apt-get install -y --no-install-recommends nginx
  SHELL

  # --- Stage 2: Copy project, build & deploy lab ---
  # Re-run with: vagrant provision --provision-with deploy
  config.vm.provision "deploy", type: "shell", inline: <<~SHELL
    set -euo pipefail

    echo "==> Copying project into VM"
    rsync -a --delete --exclude-from=/vagrant/.rsyncignore /vagrant/ /home/vagrant/lab/
    chown -R vagrant:vagrant /home/vagrant/lab

    echo "==> Patching aether.config.yaml for Vagrant"

    # Patching the config for lab-root-path and macvlan parent
    sed -i 's|lab-root-path:.*|lab-root-path: /home/vagrant/lab|' /home/vagrant/lab/aether.config.yaml
    sed -i 's|internet-macvlan-parent:.*|internet-macvlan-parent: eth1|' /home/vagrant/lab/aether.config.yaml

    echo "==> Building and deploying lab"
    cd /home/vagrant/lab
    make apply MAX_WORKERS=3

    echo "==> Configuring nginx reverse proxy"
    cat > /etc/nginx/sites-available/aether <<'NGINX'
    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://172.20.20.23:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    NGINX
    ln -sf /etc/nginx/sites-available/aether /etc/nginx/sites-enabled/aether
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl enable nginx && systemctl restart nginx

    VM_IP=$(ip -4 addr show eth1 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "<pending>")
    echo "==> Done! Lab is running."
    echo "    Access via: http://${VM_IP}"
    echo "    (If <pending>, run: vagrant ssh -c 'ip -4 addr show eth1')"
  SHELL
end
