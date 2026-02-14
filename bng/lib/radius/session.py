from typing import Literal
from dataclasses import dataclass, field
import uuid

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

    # opt82
    relay_id: str
    remote_id: str
    circuit_id: str

    # Unique session ID for event tracking
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # QoS parameters
    qos_download_kbit: int | None = None
    qos_upload_kbit: int | None = None
    qos_download_burst_kbit: int | None = None
    qos_upload_burst_kbit: int | None = None

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
    last_status_change_ts: float | None = None


    dhcp_nak_count: int = 0

    def access_key(self) -> str:
        """Generate a unique key for this session based on MAC, IP, and first seen timestamp."""
        return f"{self.relay_id}/{self.circuit_id}/{self.remote_id}"
