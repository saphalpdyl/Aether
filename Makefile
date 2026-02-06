# Make file for building and running
#

dev:
	sudo docker compose build
	sudo containerlab deploy -t containerlab/topology.yml
	$(MAKE) ips

clean:
	sudo containerlab destroy -t containerlab/topology.yml

debug:
	sudo docker compose build
	sudo containerlab deploy -t /home/test/lab/containerlab/topology.yml --log-level debug

ips:
	@printf "%-24s %-60s\n" "Name" "Interfaces"
	@for c in $$(docker ps --format '{{.Names}}' | grep '^clab-isp-lab-'); do \
	  ifaces=$$(docker exec -it "$$c" sh -c "ip -4 -o addr show scope global | awk '\$$2!=\"lo\" && \$$2!=\"eth0\" {print \$$2 \":\" \$$4}'" 2>/dev/null | tr -d '\r' | paste -sd ', ' -); \
	  printf "%-24s %-60s\n" "$$c" "$${ifaces:-<none>}"; \
	done
