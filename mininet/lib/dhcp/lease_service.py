from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple
import requests

from lib.dhcp.lease import DHCPLease
from lib.secrets import __KEA_CTRL_AGENT_PASSWORD
from lib.dhcp.utils import parse_network_tlv

class LeaseService(ABC):
    @abstractmethod
    def get_all_leases(self) -> list[DHCPLease]:
        ...

    def get_lease_by_id(self, lease_id: str) -> DHCPLease | None:
        ...

class KeaClient:
    def __init__(self, base_url: str, auth_key: str) -> None:
        self.base_url = base_url
        self.auth_key = auth_key

    def get_leases(self) -> Tuple[list[dict], bool]:
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
        response = response.json()

        try:
            response[0]["arguments"]["leases"]
        except (KeyError, IndexError):
            return [], False

        return response[0]['arguments']['leases'], True

class KeaLeaseService(LeaseService):
    def __init__(self, kea_client: KeaClient, bng_relay_id: str) -> None:
        self.kea_client = kea_client
        self.relay_id = bng_relay_id

    def get_all_leases(self) -> list[DHCPLease]:
        leases_data, success = self.kea_client.get_leases()
        if not success:
            raise Exception("Failed to get leases from Kea")

        leases = []
        for data in leases_data:
            if data.get("state", -1) != 0:
                continue

            user_ctx = data.get("user-context") or {}
            isc_ctx = user_ctx.get("ISC") or {}
            relay_info = isc_ctx.get("relay-agent-info") or {}
            sub_options = relay_info.get("sub-options")
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
