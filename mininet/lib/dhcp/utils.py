from typing import List

from .lease import DHCPLease

def parse_dhcp_leases(lines: str) -> List[DHCPLease]:
    leases: List[DHCPLease] = []
    for line_no, line in enumerate(lines.splitlines()):
        parts = line.split()
        if len(parts) < 5:
            raise ValueError(f"Invalid DHCP lease line: {line_no + 1}")
        lease = DHCPLease(
            time=int(parts[0]),
            mac=parts[1],
            ip=parts[2],
            hostname=parts[3],
            client_id=parts[4]
        )
        leases.append(lease)
    return leases
