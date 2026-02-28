# Make file for building and running
#

CONFIG_FILE ?= aether.config.yaml
MAX_WORKERS ?= 0

validate:
	python3 tools/config_pipeline.py validate --config $(CONFIG_FILE)

generate: validate
	python3 tools/config_pipeline.py generate --config $(CONFIG_FILE)

apply: generate
	sudo docker compose build
	-sudo containerlab destroy -t containerlab/topology.yml
	-sudo docker rm -f $$(docker ps -aq --filter "name=^clab-isp-lab-")
	sudo containerlab deploy -t containerlab/topology.yml --max-workers $(MAX_WORKERS)
	$(MAKE) ips

apply-prod: generate
	sudo docker compose build
	-sudo containerlab destroy -t containerlab/topology.yml
	-sudo docker rm -f $$(docker ps -aq --filter "name=^clab-isp-lab-")
# 3 workers seemed to not cause concurrency issues during containerlab setup on cloud
	sudo containerlab deploy -t containerlab/topology.yml --max-workers 3
	$(MAKE) ips

dev:
	$(MAKE) apply

clean:
	sudo containerlab destroy -t containerlab/topology.yml

ips:
	@printf "%-24s %-60s\n" "Name" "Interfaces"
	@for c in $$(docker ps --format '{{.Names}}' | grep '^clab-isp-lab-'); do \
	  ifaces=$$(docker exec -it "$$c" sh -c "ip -4 -o addr show scope global | awk '\$$2!=\"lo\" && \$$2!=\"eth0\" {print \$$2 \":\" \$$4}'" 2>/dev/null | tr -d '\r' | paste -sd ', ' -); \
	  printf "%-24s %-60s\n" "$$c" "$${ifaces:-<none>}"; \
	done

dev-ssh:
	ssh -L 3000:172.20.20.20:3000 -L 8000:172.20.20.21:8000 test@192.168.122.216

# IMPORTANT: If in VM, go to /etc/fuse.conf and uncomment "user_allow_other" in the VM
dev-unmount:
	fusermount -u ~/lab
