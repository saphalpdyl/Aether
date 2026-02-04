# Make file for building and running
#

dev:
	sudo docker compose build
	sudo containerlab deploy -t containerlab/topology.yml

clean:
	sudo containerlab destroy -t containerlab/topology.yml

debug:
	sudo docker compose build
	sudo containerlab deploy -t /home/test/lab/containerlab/topology.yml --log-level debug
