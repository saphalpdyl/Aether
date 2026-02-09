# Make file for building and running
#

dev:
	$(MAKE) clean
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

dev-ssh:
	ssh -L 3000:172.20.20.20:3000 test@192.168.122.216

# IMPORTANT: If in VM, go to /etc/fuse.conf and uncomment "user_allow_other" in the VM
dev-unmount:
	fusermount -u ~/lab
