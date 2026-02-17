from typing import Tuple
import docker

def __LAB_ONLY_get_host_containers():
    client = docker.from_env()
    containers = client.containers.list(filters={"name": "clab-isp-lab-h-"})

    return containers

def get_host_access_node_name_and_iface_from_container_name(container_name: str) -> Tuple[str, str]:
    # The host container names are in the format of clab-isp-lab-h-cstm-relay-{id}-{iface}
    return "-".join(container_name.split("-")[4:7]), container_name.split("-")[-1]
