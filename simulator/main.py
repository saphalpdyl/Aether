import random
import threading
import requests
import time

from fastapi import FastAPI

from config import log, OSS_BACKEND_MAX_RETRY, OSS_RETRY_INTERVAL, oss_backend_url, SIMULATOR_CONFIG
from oss import fetch_customers_and_plans, routers_to_bng_id_hashmap, create_service_in_oss
from containers import __LAB_ONLY_get_host_containers, get_host_access_node_name_and_iface_from_container_name
from traffic import dhcp_acquire_all, traffic_loop

from routers.simulate_user import router as simulate_user_router


# Wait for OSS-backend to be ready
wait_retry_count = 0
while True:
    try:
        response = requests.get(f"{oss_backend_url}/health")
        if response.status_code == 200:
            log.info("OSS-backend is ready")
            break

    except requests.exceptions.ConnectionError:
        if wait_retry_count > OSS_BACKEND_MAX_RETRY:
            log.error("Failed to connect to OSS-backend after maximum retries")
            raise

        wait_retry_count += 1
        log.info(f"Waiting for OSS-backend to be ready... ({wait_retry_count}/{OSS_BACKEND_MAX_RETRY})")
    finally:
        time.sleep(OSS_RETRY_INTERVAL)

def startup():
    # Get initial customers and plans
    total_customers, total_plans = fetch_customers_and_plans()

    routers_hmap = routers_to_bng_id_hashmap()

    all_host_containers = __LAB_ONLY_get_host_containers()
    host_container_names = [container.name for container in all_host_containers]

    print("Routers hashmap: ", routers_hmap)

    sim_cfg = SIMULATOR_CONFIG.get("simulation", {})
    container_fraction = float(sim_cfg.get("container_fraction", 0.5))
    customer_fraction = float(sim_cfg.get("customer_fraction", 0.5))

    # Select a random subset of containers based on configured fraction
    n_containers = max(1, round(len(host_container_names) * container_fraction))
    host_container_names = random.sample(host_container_names, min(n_containers, len(host_container_names)))

    # Select a random subset of customers based on configured fraction
    n_customers = max(1, round(len(total_customers) * customer_fraction))
    total_customers = random.sample(total_customers, min(n_customers, len(total_customers)))

    # Build a name->container lookup for the selected hosts
    container_by_name = {c.name: c for c in all_host_containers}

    for container_name in host_container_names:
        access_node_name, access_node_iface = get_host_access_node_name_and_iface_from_container_name(container_name)
        connected_bng_id = routers_hmap.get(access_node_name, None)

        if connected_bng_id is None:
            log.warning(f"No connected BNG found for access node {access_node_name} (container: {container_name}), Tried routers_hmap[{access_node_name}] but got None.")
            continue

        # Get the next customer from the list ( cycle through the list if we reach the end )
        customer = total_customers.pop(0)
        total_customers.append(customer)

        # Get random plan
        plan = random.choice(total_plans)

        # Create service in OSS-backend
        # The circuit_id is dependent on the format of 1/0/{iface_number}
        # For example: if the iface is eth1, then the circuit_id will be 1/0/1
        # I know this is not a good way to generate circuit_id, but for the sake of this lab, it will work

        iface_number = access_node_iface.replace("eth", "")
        relay_id = routers_hmap[access_node_name] # bng_id is the relay_id in our architecture
        circuit_id = f"1/0/{iface_number}"
        remote_id = access_node_name # remote_id is the access node name in our architecture
        _ = create_service_in_oss(
            customer_id=customer["id"],
            plan_id=plan["id"],
            relay_id=relay_id,
            circuit_id=circuit_id,
            remote_id=remote_id
        )

    # Phase 1: DHCP lease acquisition on selected hosts
    selected_containers = [container_by_name[name] for name in host_container_names if name in container_by_name]
    leased_containers = dhcp_acquire_all(selected_containers)
    log.info("DHCP acquisition complete", leased=len(leased_containers), total=len(selected_containers))

    # Phase 2: Spawn traffic generation threads for leased hosts
    for container in leased_containers:
        t = threading.Thread(target=traffic_loop, args=(container,), daemon=True)
        t.start()
        log.info("Traffic thread started", host=container.name)
    log.info("All traffic threads spawned", count=len(leased_containers))

app = FastAPI()
app.include_router(simulate_user_router, prefix="/simulation")

startup()

@app.get("/health")
async def health():
    log.info("health_check")
    return {"status": "ok"}

@app.get("/simulation/topology")
async def get_topology():
    """
    Returns the topology YAML file content.
    The topology is mounted at /opt/simulator/topology.yaml
    """
    import yaml
    from pathlib import Path
    
    topology_path = Path("/opt/simulator/topology.yaml")
    
    try:
        with open(topology_path, "r") as f:
            topology_content = yaml.safe_load(f)
        
        log.info("topology_fetched")
        return topology_content
    except FileNotFoundError:
        log.error("topology_file_not_found", path=str(topology_path))
        return {"error": "Topology file not found"}, 404
    except Exception as e:
        log.error("topology_fetch_error", error=str(e))
        return {"error": str(e)}, 500
