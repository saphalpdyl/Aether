import random
import threading

from fastapi import FastAPI

from config import log
from oss import fetch_customers_and_plans, routers_to_bng_id_hashmap, create_service_in_oss
from containers import __LAB_ONLY_get_host_containers, get_host_access_node_name_and_iface_from_container_name
from traffic import dhcp_acquire_all, traffic_loop

def startup():
    # Get initial customers and plans
    total_customers, total_plans = fetch_customers_and_plans()

    routers_hmap = routers_to_bng_id_hashmap()

    all_host_containers = __LAB_ONLY_get_host_containers()
    host_container_names = [container.name for container in all_host_containers]

    print("Routers hashmap: ", routers_hmap)

    # Remove random host_containers from the list
    to_remove_host_containers = random.sample(host_container_names, len(host_container_names) // 2)
    host_container_names = [name for name in host_container_names if name not in to_remove_host_containers]

    # Remove random customers from the list
    to_remove_customers = random.sample(total_customers, len(total_customers) // 2)
    total_customers = [customer for customer in total_customers if customer not in to_remove_customers]

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

startup()

@app.get("/health")
async def health():
    log.info("health_check")
    return {"status": "ok"}
