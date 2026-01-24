from dataclasses import dataclass

@dataclass
class DHCPLease:
    time: int
    mac: str
    ip: str
    hostname: str
    client_id: str # Might be a MAC or * if not sent
