#!/bin/bash

# Script to move KEA DHCP server configuration files to a /etc/kea directory

cp conf/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf
cp conf/kea-ctrl-agent.conf /etc/kea/kea-ctrl-agent.conf
