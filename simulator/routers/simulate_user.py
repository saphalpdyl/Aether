from dataclasses import dataclass
from typing import Literal

import docker
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import SIMULATOR_CONFIG, log, oss_backend_url

router = APIRouter()

@dataclass
class SimulateOptionNote:
    type: Literal["info", "warning"]
    text: str

@dataclass
class SimulateOption:
    name: str
    description: str
    commands: list[dict]
    note: SimulateOptionNote | None = None

@dataclass
class GetSimulateOptionsResponse:
    count: int
    options: list[SimulateOption]


@router.get("/get_simulate_options")
def get_simulate_options() -> GetSimulateOptionsResponse:
    options: list[SimulateOption] = []

    for name, cgroup in SIMULATOR_CONFIG["traffic_commands"].items():
        if cgroup["allow_for_demo_simulation"]:
            options.append(
                SimulateOption(
                    name=name,
                    description=cgroup.get("description", ""),
                    commands=cgroup["commands"],
                    note=SimulateOptionNote(**cgroup["note"]) if "note" in cgroup else None
                )
            )

    return GetSimulateOptionsResponse(
        count=len(options),
        options=options,
    )


class CmdRequest(BaseModel):
    service_id: int
    name: str
    command: str


def _get_container_for_service(service_id: int):
    """Fetch service from OSS, derive the host container name, and return the Docker container."""
    try:
        resp = requests.get(f"{oss_backend_url}/api/services/{service_id}", timeout=5)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch service: {e}")

    service = resp.json()["data"]
    remote_id = service["remote_id"]    # e.g. "cstm-relay-1"
    circuit_id = service["circuit_id"]  # e.g. "1/0/1"
    iface_number = circuit_id.split("/")[-1]
    container_name = f"clab-isp-lab-h-{remote_id}-eth{iface_number}"

    try:
        client = docker.from_env()
        return client.containers.get(container_name)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container not found: {container_name!r}")
    except docker.errors.DockerException as e:
        raise HTTPException(status_code=502, detail=f"Docker error: {e}")


@router.post("/cmd")
def execute_cmd(body: CmdRequest):
    traffic_commands = SIMULATOR_CONFIG["traffic_commands"]

    if body.name not in traffic_commands:
        raise HTTPException(status_code=400, detail=f"Unknown command group: {body.name!r}")

    # This is to prevent Remote Code Execution - we only allow commands that are predefined in simulator.config.json
    allowed_commands = [c["command"] for c in traffic_commands[body.name]["commands"]]
    if body.command not in allowed_commands:
        raise HTTPException(status_code=400, detail="Command not in allowed list")

    try:
        container = _get_container_for_service(body.service_id)
    except Exception as e:
        print(f"Error fetching container for service {body.service_id}: {e}")
        raise e

    try:
        result = container.exec_run(["sh", "-c", body.command], demux=False)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Exec failed: {e}")

    output = result.output.decode(errors="replace") if result.output else ""
    log.info("simulate_cmd", service_id=body.service_id, container=container.name,
             cmd=body.command, exit_code=result.exit_code)

    return {
        "exit_code": result.exit_code,
        "output": output,
    }
