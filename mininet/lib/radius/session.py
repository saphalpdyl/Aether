from typing import Literal
from dataclasses import dataclass 

@dataclass
class DHCPSession:
    mac: str | None
    ip: str | None
    first_seen: float
    last_seen: float
    expiry: int | None
    iface: str
    hostname: str | None
    last_interim: float | None # For Interim-Update tracking

    # nftables related data
    nft_up_handle: int | None = None
    nft_down_handle: int | None = None

    base_up_bytes: int = 0
    base_down_bytes: int = 0
    base_up_pkts: int = 0
    base_down_pkts: int = 0

    # None if no data yet
    last_up_bytes: int | None = None
    last_down_bytes: int | None = None
    last_traffic_seen_ts: float | None = None
    last_idle_ts: float | None = None

    status: Literal["ACTIVE", "IDLE", "EXPIRED", "PENDING"] = "PENDING"
    auth_state: Literal["PENDING_AUTH", "AUTHORIZED", "REJECTED"] = "PENDING_AUTH"

    dhcp_nak_count: int = 0
