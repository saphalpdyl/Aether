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

def _normalize_remote_id(raw_bytes: bytes) -> str:
    """Convert raw remote_id bytes to hex string."""
    return raw_bytes.hex()


def parse_network_tlv(hex_str):
    # Clean up the input string
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]

    raw_data = bytes.fromhex(hex_str)

    # Define our mapping: {Type_Byte: "Desired_Key_Name"}
    mapping = {
        1: "circuit_id",
        2: "remote_id",
        12: "relay_id"  # Type 0x0C is 12 in decimal
    }

    decoded_dict = {}
    i = 0

    while i < len(raw_data):
        try:
            t_type = raw_data[i]      # The Type byte
            t_len = raw_data[i+1]     # The Length byte
            t_raw = raw_data[i+2 : i+2+t_len]

            # Normalize remote_id to MAC format, decode others as ASCII
            if t_type == 2:  # remote_id
                t_value = _normalize_remote_id(t_raw)
            else:
                t_value = t_raw.decode('ascii', errors='replace')

            # If the type is in our map, add it to the dictionary
            if t_type in mapping:
                decoded_dict[mapping[t_type]] = t_value

            # Move index to the start of the next TLV block
            i += 2 + t_len
        except (IndexError, UnicodeDecodeError):
            # Break if the packet is malformed or truncated
            break

    return decoded_dict
