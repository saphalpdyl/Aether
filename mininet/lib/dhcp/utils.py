from re import L
from typing import List

from typing import Tuple, List
from .lease import DHCPLease

def parse_dhcp_leases(lines: str) -> Tuple[List[DHCPLease], bool, str | None]:
    """
    returns: leases: List[DHCPLease] | None, success: bool, error_message: str
    """

    leases: List[DHCPLease] = []
    try:
        split_lines = lines.splitlines()
        if len(split_lines) < 1:
            return [], True, None

        for line_no, line in enumerate(split_lines):
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
    except Exception as e:
        return [], False, str(e)

    return leases, True, None

def format_mac(raw_mac: str, delimiter: str = ":") -> str:
    clean_mac = "".join(c for c in raw_mac if c.isalnum())
    
    if len(clean_mac) != 12:
        raise ValueError("Invalid MAC address length")

    return delimiter.join(clean_mac[i:i+2] for i in range(0, 12, 2)).lower()
