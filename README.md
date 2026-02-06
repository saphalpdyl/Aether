# ISP lab (containerlab)

This repository runs an ISP lab topology using containerlab. It replaces the previous Containernet/Mininet setup and is meant to be the single source of truth.

## Prerequisites
- Docker + Docker Compose
- containerlab
- SR Linux image: `ghcr.io/nokia/srlinux:25.3.1` (or update the tag in `containerlab/topology.yml`)
- A host interface for macvlan (edit `containerlab/topology.yml` -> `macvlan:enp1s0`)

## Build and run
```
make dev
```

To tear down:
```
make clean
```

## Notes on networking
- The upstream node NATs both `192.0.2.0/24` and `10.0.0.0/24` out `eth6` (macvlan).
- The access node is Nokia SR Linux and inserts DHCP Option 82 sub-options 1 and 2 via `containerlab/srl-access.cli`.
- The BNG appends Option 82 sub-option 12 (relay-id) on relay-to-server traffic.
- Update the macvlan interface name to your host's uplink (e.g., `enp1s0`, `eth0`, `wlan0`).
- If your environment requires a static IP/gateway on the macvlan side, add it to the `upstream` exec block in `containerlab/topology.yml`.

## Quick validation
After deploy:
```
# Get a DHCP lease on the subscribers
sudo docker exec -it clab-isp-lab-h1 dhclient -v eth1
sudo docker exec -it clab-isp-lab-h2 dhclient -v eth1

# Verify subscriber -> upstream reachability
sudo docker exec -it clab-isp-lab-h1 ping -c 3 192.0.2.1
sudo docker exec -it clab-isp-lab-h1 ping -c 3 8.8.8.8

# Check service health
sudo docker exec -it clab-isp-lab-kea kea-admin lease-dump -4 -o /tmp/leases.json
sudo docker exec -it clab-isp-lab-radius psql "host=192.0.2.6 user=radius password=test dbname=radius" -c "\dt"
```

If DHCP or RADIUS queries fail, inspect logs:
```
sudo docker exec -it clab-isp-lab-bng tail -n +1 /tmp/bng-entry.log
sudo docker exec -it clab-isp-lab-kea tail -n +1 /tmp/kea-dhcp4.log
sudo docker exec -it clab-isp-lab-radius tail -n +1 /var/log/freeradius/radius.log
```
