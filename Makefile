# Make file for building and running
#

dev:
	sudo mn -c
	sudo docker compose build
	sudo python3 mininet/lab.py
