import requests

from config import log, oss_backend_url

def fetch_customers_and_plans():

    try:
        response = requests.get(f"{oss_backend_url}/api/customers")
        response.raise_for_status()
        customers = response.json()['data']
        log.info("Fetched customers", count=len(customers))
    except requests.exceptions.RequestException as e:
        log.error("Failed to fetch customers", error=str(e))
        customers = []

    try:
        response = requests.get(f"{oss_backend_url}/api/plans")
        response.raise_for_status()
        plans = response.json()['data']
        log.info("Fetched plans", count=len(plans))
    except requests.exceptions.RequestException as e:
        log.error("Failed to fetch plans", error=str(e))
        plans = []

    return customers, plans

def routers_to_bng_id_hashmap():
    try:
        response = requests.get(f"{oss_backend_url}/api/routers")
        response.raise_for_status()
        routers = response.json()['data']
        log.info("Fetched routers", count=len(routers))
    except requests.exceptions.RequestException as e:
        log.error("Failed to fetch routers", error=str(e))
        routers = []

    routers_hmap = {router["router_name"]: router["bng_id"] for router in routers }
    return routers_hmap

def create_service_in_oss(*, customer_id, plan_id, relay_id, circuit_id, remote_id, status: str= "ACTIVE") -> bool:
    service_data = {
        "customer_id": customer_id,
        "plan_id": plan_id,
        "relay_id": relay_id,
        "circuit_id": circuit_id,
        "remote_id": remote_id,
        "status": status
    }
    try:
        response = requests.post(f"{oss_backend_url}/api/services", json=service_data)
        response.raise_for_status()
        log.info("Service created successfully", service_id=response.json().get("id"))
        return True
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to create service for customer_id={customer_id} and plan_id={plan_id} ", error=str(e))
        return False
