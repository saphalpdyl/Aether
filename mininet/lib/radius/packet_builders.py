# COMMENT: All packet builders AI-generated because I didn't want to bother myself

import time
import shlex

from mininet.node import Host

from lib.radius.session import DHCPSession
from lib.radius.utils import split_bytes_to_gigawords_octets
from lib.secrets import __RADIUS_SECRET

# Future: Move to somewhere so that mininet code and bng code can separate
def rad_acct_send_from_bng(
    bng: Host,
    packet: str,
    server_ip: str,
    port: int = 1813,
    secret: str = __RADIUS_SECRET,
    timeout: int = 1,
):
    pkt_q = shlex.quote(packet)
    secret_q = shlex.quote(secret)
    cmd = f"printf %s {pkt_q} | radclient -x -t {timeout} {server_ip}:{port} acct {secret_q}"
    return bng.cmd(cmd)

def rad_auth_send_from_bng(
    bng: Host,
    packet: str,
    server_ip: str,
    port: int = 1812,
    secret: str = __RADIUS_SECRET,
    timeout: int = 1,
):
    pkt_q = shlex.quote(packet)
    secret_q = shlex.quote(secret)
    cmd = f"printf %s {pkt_q} | radclient -x -t {timeout} {server_ip}:{port} auth {secret_q}"
    return bng.cmd(cmd)

def acct_session_id(mac: str, ip: str, first_seen: float) -> str:
    return f"{mac.lower()}-{ip}-{int(first_seen)}"

def build_acct_start(s: DHCPSession, nas_ip="192.0.2.1", nas_port_id="bng-eth0") -> str:
    now = int(time.time())
    return "\n".join([
        "Acct-Status-Type = Start",
        f'User-Name = "mac:{s.mac.lower()}"',
        f'Acct-Session-Id = "{acct_session_id(s.mac, s.ip, s.first_seen)}"',
        f"Framed-IP-Address = {s.ip}",
        f'Calling-Station-Id = "{s.mac.lower()}"',
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Event-Timestamp = {now}",
        "",
    ])

def build_acct_stop(
    s: "DHCPSession",
    input_bytes: int,
    output_bytes: int,
    input_pkts: int,
    output_pkts: int,
    nas_ip: str = "192.0.2.1",
    nas_port_id: str = "bng-eth0",
    cause: str = "User-Request",
) -> str:
    now = int(time.time())
    duration = max(0, int(time.time() - s.first_seen))

    in_gw, in_oct = split_bytes_to_gigawords_octets(input_bytes)
    out_gw, out_oct = split_bytes_to_gigawords_octets(output_bytes)

    return "\n".join([
        "Acct-Status-Type = Stop",
        f'User-Name = "mac:{s.mac.lower()}"',
        f'Acct-Session-Id = "{acct_session_id(s.mac, s.ip, s.first_seen)}"',
        f"Framed-IP-Address = {s.ip}",
        f'Calling-Station-Id = "{s.mac.lower()}"',
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Acct-Session-Time = {duration}",
        f'Acct-Terminate-Cause = "{cause}"',
        f"Event-Timestamp = {now}",

        # Bytes (64-bit via octets+gigawords)
        f"Acct-Input-Octets = {in_oct}",
        f"Acct-Input-Gigawords = {in_gw}",
        f"Acct-Output-Octets = {out_oct}",
        f"Acct-Output-Gigawords = {out_gw}",

        # Packets (32-bit best-effort; no standard gigawords field)
        f"Acct-Input-Packets = {max(0, int(input_pkts))}",
        f"Acct-Output-Packets = {max(0, int(output_pkts))}",
        "",
    ])


def build_acct_interim(
    s: "DHCPSession",
    input_bytes: int,
    output_bytes: int,
    input_pkts: int,
    output_pkts: int,
    nas_ip: str = "192.0.2.1",
    nas_port_id: str = "bng-eth0",
) -> str:
    now = int(time.time())
    session_time = max(0, int(time.time() - s.first_seen))

    in_gw, in_oct = split_bytes_to_gigawords_octets(input_bytes)
    out_gw, out_oct = split_bytes_to_gigawords_octets(output_bytes)

    return "\n".join([
        "Acct-Status-Type = Interim-Update",
        f'User-Name = "mac:{s.mac.lower()}"',
        f'Acct-Session-Id = "{acct_session_id(s.mac, s.ip, s.first_seen)}"',
        f"Framed-IP-Address = {s.ip}",
        f'Calling-Station-Id = "{s.mac.lower()}"',
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Acct-Session-Time = {session_time}",
        f"Event-Timestamp = {now}",

        # Bytes (64-bit via octets+gigawords)
        f"Acct-Input-Octets = {in_oct}",
        f"Acct-Input-Gigawords = {in_gw}",
        f"Acct-Output-Octets = {out_oct}",
        f"Acct-Output-Gigawords = {out_gw}",

        # Packets (32-bit best-effort)
        f"Acct-Input-Packets = {max(0, int(input_pkts))}",
        f"Acct-Output-Packets = {max(0, int(output_pkts))}",
        "",
    ])

def build_access_request(
    s: DHCPSession,
    user_password: str = "testing123",
    nas_ip: str = "192.0.2.1",
    nas_port_id: str = "bng-eth0",
) -> str:
    """
    Returns a radclient-compatible Access-Request attribute list.
    Use with: radclient -x <radius_ip> auth <secret>
    """
    now = int(time.time())
    mac = s.mac.lower()

    return "\n".join([
        # RADIUS auth type implied by radclient 'auth' (Access-Request)
        f'User-Name = "mac:{mac}"',
        f'User-Password = "{user_password}"',          # lab-simple PAP
        f'Calling-Station-Id = "{mac}"',               # who is calling (subscriber MAC)
        f'Called-Station-Id = "{nas_port_id}"',        # optional; can be iface or BNG id
        f"Framed-IP-Address = {s.ip}",                 # IP the subscriber got via DHCP
        f"NAS-IP-Address = {nas_ip}",
        f'NAS-Port-Id = "{nas_port_id}"',
        "NAS-Port-Type = Ethernet",
        f"Event-Timestamp = {now}",
        "",
    ])
