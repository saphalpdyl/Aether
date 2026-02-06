from dataclasses import dataclass

@dataclass
class DHCPLease:
    ip: str
    mac: str
    expiry_for: int | None
    expiry: int

    # Option 82 
    relay_id: str
    remote_id: str
    circuit_id: str

    last_state_update_ts: float
    _kea_state: int

    hostname: str | None = None
    client_id: str | None = None



    # time: int
    # mac: str
    # ip: str
    # hostname: str
    # client_id: str # Might be a MAC or * if not sent
