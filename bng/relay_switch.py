#!/usr/bin/env python3
import argparse
import select
import socket
import struct

# Ethernet + IPv4 constants (raw socket parsing).
ETH_P_ALL = 0x0003
ETH_P_IP = 0x0800
UDP_PROTO = 17
ETH_HDR_LEN = 14
IPV4_MIN_IHL = 5
UDP_HDR_LEN = 8
PACKET_OUTGOING = 4

# BOOTP/DHCP layout and option codes (RFC 2131/3046).
BOOTP_FIXED_LEN = 236
DHCP_MAGIC = b"\x63\x82\x53\x63"
DHCP_OPTION_PAD = 0
DHCP_OPTION_END = 255
DHCP_OPTION_RELAY_AGENT = 82
DHCP_RELAY_SUBOPT_CIRCUIT_ID = 1
DHCP_RELAY_SUBOPT_REMOTE_ID = 2
DHCP_CLIENT_PORT = 68
DHCP_SERVER_PORT = 67
BOOTP_GIADDR_OFFSET = 24
BOOTP_CHADDR_OFFSET = 28


def parse_remote_id(value: str) -> bytes:
    # Accept textual IDs, or raw hex (e.g. 000000000002 / 00:00:00:00:00:02).
    h = value.strip().replace(":", "").replace("-", "")
    if len(h) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in h):
        return bytes.fromhex(h)
    return value.strip().encode()


def set_giaddr(payload: bytes, giaddr: str) -> bytes:
    if len(payload) < BOOTP_FIXED_LEN:
        return payload
    if payload[BOOTP_GIADDR_OFFSET:BOOTP_GIADDR_OFFSET + 4] != b"\x00\x00\x00\x00":
        return payload
    return payload[:BOOTP_GIADDR_OFFSET] + socket.inet_aton(giaddr) + payload[BOOTP_GIADDR_OFFSET + 4:]


def build_option82(circuit_id: bytes, remote_id: bytes) -> bytes:
    sub1 = bytes([DHCP_RELAY_SUBOPT_CIRCUIT_ID, len(circuit_id)]) + circuit_id
    sub2 = bytes([DHCP_RELAY_SUBOPT_REMOTE_ID, len(remote_id)]) + remote_id
    data = (sub1 + sub2)[:255]
    return bytes([DHCP_OPTION_RELAY_AGENT, len(data)]) + data


def parse_options(opts: bytes) -> list[tuple[int, bytes]]:
    out = []
    i = 0
    while i < len(opts):
        code = opts[i]
        if code == DHCP_OPTION_PAD:
            i += 1
            continue
        if code == DHCP_OPTION_END or i + 1 >= len(opts):
            break
        ln = opts[i + 1]
        out.append((code, opts[i + 2 : i + 2 + ln]))
        i += 2 + ln
    return out


def rebuild_options(opts: list[tuple[int, bytes]], opt82: bytes) -> bytes:
    # Strip any existing Option 82 and append a fresh one.
    out = bytearray()
    for code, data in opts:
        if code in (DHCP_OPTION_RELAY_AGENT, DHCP_OPTION_PAD, DHCP_OPTION_END):
            continue
        out.extend(bytes([code, len(data)]) + data)
    out.extend(opt82)
    out.append(DHCP_OPTION_END)
    return bytes(out)


def strip_option82(payload: bytes) -> bytes:
    # RFC 3046 2.1: drop the Relay Agent Information option from a server reply
    # before forwarding it down to the client.
    magic_end = BOOTP_FIXED_LEN + len(DHCP_MAGIC)
    if len(payload) < magic_end or payload[BOOTP_FIXED_LEN:magic_end] != DHCP_MAGIC:
        return payload
    opts = parse_options(payload[magic_end:])
    if not any(code == DHCP_OPTION_RELAY_AGENT for code, _ in opts):
        return payload
    out = bytearray()
    for code, data in opts:
        if code == DHCP_OPTION_RELAY_AGENT:
            continue
        out.extend(bytes([code, len(data)]) + data)
    out.append(DHCP_OPTION_END)
    return payload[:magic_end] + bytes(out)


def build_relay_payload(
    pkt: bytes,
    iface: str,
    remote_id: bytes,
    circuit_id_map: dict[str, bytes],
    default_circuit_id: bytes | None,
    giaddr: str | None,
) -> bytes | None:
    # Return the BOOTP payload of a client->server DHCP frame with Option 82
    # inserted and giaddr set, or None if it isn't such a frame.
    if len(pkt) < ETH_HDR_LEN or struct.unpack("!H", pkt[12:14])[0] != ETH_P_IP:
        return None

    ip_off = ETH_HDR_LEN
    ihl = (pkt[ip_off] & 0x0F) * 4
    if ihl < IPV4_MIN_IHL * 4 or len(pkt) < ip_off + ihl + UDP_HDR_LEN:
        return None
    if pkt[ip_off + 9] != UDP_PROTO:
        return None

    udp_off = ip_off + ihl
    src_port, dst_port, udp_len, _ = struct.unpack("!HHHH", pkt[udp_off : udp_off + 8])
    if src_port != DHCP_CLIENT_PORT or dst_port != DHCP_SERVER_PORT:
        return None
    if len(pkt) < udp_off + udp_len:
        return None

    payload = pkt[udp_off + UDP_HDR_LEN : udp_off + udp_len]
    if len(payload) < BOOTP_FIXED_LEN + len(DHCP_MAGIC):
        return None
    if payload[BOOTP_FIXED_LEN : BOOTP_FIXED_LEN + len(DHCP_MAGIC)] != DHCP_MAGIC:
        return None

    opt_list = parse_options(payload[BOOTP_FIXED_LEN + len(DHCP_MAGIC) :])
    circuit_id = circuit_id_map.get(iface, default_circuit_id or iface.encode())
    opt82 = build_option82(circuit_id, remote_id)
    new_payload = payload[: BOOTP_FIXED_LEN + len(DHCP_MAGIC)] + rebuild_options(opt_list, opt82)
    if giaddr:
        new_payload = set_giaddr(new_payload, giaddr)
    return new_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--access", action="append", required=True)
    parser.add_argument("--uplink", required=True)
    parser.add_argument("--server-ip", required=True)
    parser.add_argument("--remote-id", default="OLT-1")
    parser.add_argument("--circuit-id", default=None)
    parser.add_argument("--circuit-id-map", action="append", default=[])
    parser.add_argument("--giaddr", default=None)
    args = parser.parse_args()

    remote_id = parse_remote_id(args.remote_id)
    default_circuit_id = args.circuit_id.encode() if args.circuit_id else None
    circuit_id_map: dict[str, bytes] = {}
    for item in args.circuit_id_map:
        if "=" not in item:
            continue
        iface, value = item.split("=", 1)
        if iface.strip():
            circuit_id_map[iface.strip()] = value.encode()

    # Raw sockets to catch client->server DHCP on each access port.
    access_socks = []
    for iface in args.access:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        s.bind((iface, 0))
        access_socks.append((s, iface))

    # L3 relay socket: unicast requests to the server, receive its replies (server -> giaddr:67).
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, args.uplink.encode())
    server_sock.bind(("0.0.0.0", DHCP_SERVER_PORT))

    # Per-access sockets to push replies back down to clients (67 -> 68 broadcast).
    down_socks = {}
    for iface in args.access:
        d = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        d.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        d.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        d.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, iface.encode())
        d.bind(("0.0.0.0", DHCP_SERVER_PORT))
        down_socks[iface] = d

    # Remember which access port each client is on, to steer replies by chaddr.
    client_iface: dict[bytes, str] = {}

    while True:
        rlist, _, _ = select.select([s for s, _ in access_socks] + [server_sock], [], [], 1.0)
        for s in rlist:
            if s is server_sock:
                data, _ = server_sock.recvfrom(65535)
                if len(data) < BOOTP_CHADDR_OFFSET + 6:
                    continue
                chaddr = data[BOOTP_CHADDR_OFFSET : BOOTP_CHADDR_OFFSET + 6]
                data = strip_option82(data)
                iface = client_iface.get(chaddr)
                targets = [down_socks[iface]] if iface in down_socks else down_socks.values()
                for d in targets:
                    d.sendto(data, ("255.255.255.255", DHCP_CLIENT_PORT))
                continue

            pkt, addr = s.recvfrom(65535)
            if len(addr) >= 3 and addr[2] == PACKET_OUTGOING:
                continue
            iface = next(i for sock, i in access_socks if sock is s)
            payload = build_relay_payload(
                pkt, iface, remote_id, circuit_id_map, default_circuit_id, args.giaddr
            )
            if not payload:
                continue
            client_iface[payload[BOOTP_CHADDR_OFFSET : BOOTP_CHADDR_OFFSET + 6]] = iface
            server_sock.sendto(payload, (args.server_ip, DHCP_SERVER_PORT))


if __name__ == "__main__":
    main()
