import asyncio
import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple
import requests

from lib.dhcp.lease import DHCPLease
from lib.secrets import __KEA_CTRL_AGENT_PASSWORD
from lib.dhcp.utils import parse_network_tlv

class LeaseService(ABC):
    @abstractmethod
    async def get_all_leases(self) -> list[DHCPLease]:
        ...

    def get_lease_by_id(self, lease_id: str) -> DHCPLease | None:
        ...

class KeaClient:
    def __init__(self, base_url: str, auth_key: str) -> None:
        self.base_url = base_url
        self.auth_key = auth_key

    async def get_leases(self) -> Tuple[list[dict], bool]:
        loop = asyncio.get_running_loop()
        def _sync_get():
            url = f"{self.base_url}/leases"
            headers = {
                "Content-Type": "application/json"
            }
            response = requests.post(
                url,
                headers=headers,
                auth=('bng', self.auth_key),
                json={
                    "command": "lease4-get-all",
                    "service": ["dhcp4"]
                }
            )
            response.raise_for_status()
            return response.json()

        response = await loop.run_in_executor(None, _sync_get)

        try:
            leases = response[0]["arguments"]["leases"]
        except (KeyError, IndexError, TypeError):
            return [], False
        if not isinstance(leases, list):
            return [], False
        return leases, True

class KeaLeaseService(LeaseService):
    def __init__(self, kea_client: KeaClient, bng_relay_id: str) -> None:
        self.kea_client = kea_client
        self.relay_id = bng_relay_id

    async def get_all_leases(self) -> list[DHCPLease]:
        leases_data, success = await self.kea_client.get_leases()
        if not success:
            raise Exception("Failed to get leases from Kea")

        leases = []
        for data in leases_data:
            if data.get("state", -1) != 0:
                continue

            user_ctx = data.get("user-context") or {}
            isc_ctx = user_ctx.get("ISC") or {}
            relay_info = isc_ctx.get("relay-agent-info")
            sub_options = None
            if isinstance(relay_info, dict):
                sub_options = relay_info.get("sub-options")
            elif isinstance(relay_info, str):
                sub_options = relay_info
            if not sub_options:
                continue

            parsed_opt82 = parse_network_tlv(sub_options)
            relay_id = parsed_opt82.get("relay_id")
            circuit_id = parsed_opt82.get("circuit_id")
            remote_id = parsed_opt82.get("remote_id")
            if not relay_id or not circuit_id or not remote_id:
                continue

            if relay_id != self.relay_id:
                continue

            lease = DHCPLease(
                ip=data.get("ip-address", ""),
                mac=data.get("hw-address", ""),

                expiry_for=data.get("valid-lifetime", None),
                expiry=data["cltt"]+data["valid-lft"],

                remote_id=remote_id,
                relay_id=relay_id,
                circuit_id=circuit_id,

                last_state_update_ts=data["cltt"],
                _kea_state=data.get("state", -1),
            )
            leases.append(lease)
        return leases
