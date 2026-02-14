# @deprecated

#!/usr/bin/env python3
import argparse
import select
import socket
import struct
import time

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


def mac_to_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))

def parse_remote_id(value: str) -> bytes:
    # Accept textual IDs, or raw hex (e.g. 000000000002 / 00:00:00:00:00:02).
    s = value.strip()
    h = s.replace(":", "").replace("-", "")
    if len(h) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in h):
        return bytes.fromhex(h)
    return s.encode()

def set_giaddr(bootp_payload: bytes, giaddr: str) -> bytes:
    if len(bootp_payload) < BOOTP_FIXED_LEN:
        return bootp_payload
    ipb = socket.inet_aton(giaddr)
    if bootp_payload[BOOTP_GIADDR_OFFSET:BOOTP_GIADDR_OFFSET + 4] != b"\x00\x00\x00\x00":
        return bootp_payload
    return (
        bootp_payload[:BOOTP_GIADDR_OFFSET]
        + ipb
        + bootp_payload[BOOTP_GIADDR_OFFSET + 4:]
    )


def checksum16(data: bytes) -> int:
    if len(data) % 2 == 1:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) + data[i + 1]
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def udp_checksum_ipv4(ip_hdr: bytes, udp_hdr: bytes, payload: bytes) -> int:
    src = ip_hdr[12:16]
    dst = ip_hdr[16:20]
    proto = ip_hdr[9:10]
    udp_len = udp_hdr[4:6]
    pseudo = src + dst + b"\x00" + proto + udp_len
    chk_data = pseudo + udp_hdr[:6] + b"\x00\x00" + payload
    return checksum16(chk_data)


def fix_ipv4_udp_checksum(pkt: bytes, zero_udp: bool = False) -> bytes:
    if len(pkt) < ETH_HDR_LEN:
        return pkt
    eth_type = struct.unpack("!H", pkt[12:14])[0]
    if eth_type != ETH_P_IP:
        return pkt
    ip_off = ETH_HDR_LEN
    vihl = pkt[ip_off]
    ihl = (vihl & 0x0F) * 4
    if ihl < IPV4_MIN_IHL * 4:
        return pkt
    if len(pkt) < ip_off + ihl + UDP_HDR_LEN:
        return pkt
    if pkt[ip_off + 9] != UDP_PROTO:
        return pkt

    udp_off = ip_off + ihl
    udp_len = struct.unpack("!H", pkt[udp_off + 4 : udp_off + 6])[0]
    if len(pkt) < udp_off + udp_len:
        return pkt

    ip_hdr = bytearray(pkt[ip_off : ip_off + ihl])
    ip_hdr[10:12] = b"\x00\x00"
    ip_hdr[10:12] = struct.pack("!H", checksum16(bytes(ip_hdr)))

    udp_hdr = bytearray(pkt[udp_off : udp_off + UDP_HDR_LEN])
    payload = pkt[udp_off + UDP_HDR_LEN : udp_off + udp_len]
    if zero_udp:
        udp_hdr[6:8] = b"\x00\x00"
    else:
        udp_hdr[6:8] = b"\x00\x00"
        udp_hdr[6:8] = struct.pack("!H", udp_checksum_ipv4(bytes(ip_hdr), bytes(udp_hdr), payload))

    return pkt[:ip_off] + bytes(ip_hdr) + bytes(udp_hdr) + payload + pkt[udp_off + udp_len :]


def build_option82(circuit_id: bytes, remote_id: bytes) -> bytes:
    # RFC 3046: Relay Agent Information option (82) with sub-options.
    sub1 = bytes([DHCP_RELAY_SUBOPT_CIRCUIT_ID, len(circuit_id)]) + circuit_id
    sub2 = bytes([DHCP_RELAY_SUBOPT_REMOTE_ID, len(remote_id)]) + remote_id
    data = sub1 + sub2
    # print("Circuit ID:", sub1)
    if len(data) > 255:
        data = data[:255]
    return bytes([DHCP_OPTION_RELAY_AGENT, len(data)]) + data


def parse_options(opts: bytes) -> list[tuple[int, bytes]]:
    out = []
    i = 0
    while i < len(opts):
        code = opts[i]
        if code == DHCP_OPTION_PAD:
            i += 1
            continue
        if code == DHCP_OPTION_END:
            break
        if i + 1 >= len(opts):
            break
        ln = opts[i + 1]
        data = opts[i + 2 : i + 2 + ln]
        out.append((code, data))
        i += 2 + ln
    return out


def rebuild_options(opts: list[tuple[int, bytes]], opt82: bytes) -> bytes:
    out = bytearray()
    # Strip any existing Option 82 and append a fresh one.
    for code, data in opts:
        if code == DHCP_OPTION_RELAY_AGENT:
            continue
        if code in (DHCP_OPTION_PAD, DHCP_OPTION_END):
            continue
        out.extend(bytes([code, len(data)]) + data)
    out.extend(opt82)
    out.extend(bytes([DHCP_OPTION_END]))
    return bytes(out)


def handle_packet(
    pkt: bytes,
    iface: str,
    uplink_mac: bytes | None,
    dst_mac: bytes | None,
    remote_id: bytes,
    circuit_id_map: dict[str, bytes],
    default_circuit_id: bytes | None,
    giaddr: str | None,
) -> bytes | None:
    # Only handle DHCP client->server (UDP 68->67) IPv4 packets.
    if len(pkt) < ETH_HDR_LEN:
        return None
    eth_type = struct.unpack("!H", pkt[12:14])[0]
    if eth_type != ETH_P_IP:
        return None

    ip_off = ETH_HDR_LEN
    vihl = pkt[ip_off]
    ihl = (vihl & 0x0F) * 4
    if ihl < IPV4_MIN_IHL * 4:
        return None
    if len(pkt) < ip_off + ihl + UDP_HDR_LEN:
        return None
    if pkt[ip_off + 9] != UDP_PROTO:
        return None

    udp_off = ip_off + ihl
    src_port, dst_port, udp_len, _ = struct.unpack("!HHHH", pkt[udp_off : udp_off + 8])
    if src_port != DHCP_CLIENT_PORT or dst_port != DHCP_SERVER_PORT:
        return None
    if len(pkt) < udp_off + udp_len:
        return None

    payload = pkt[udp_off + 8 : udp_off + udp_len]
    if len(payload) < BOOTP_FIXED_LEN + len(DHCP_MAGIC):
        return None
    magic = payload[BOOTP_FIXED_LEN : BOOTP_FIXED_LEN + len(DHCP_MAGIC)]
    if magic != DHCP_MAGIC:
        return None

    options = payload[BOOTP_FIXED_LEN + len(DHCP_MAGIC) :]
    opt_list = parse_options(options)
    circuit_id = circuit_id_map.get(iface, default_circuit_id or iface.encode())
    opt82 = build_option82(circuit_id, remote_id)
    new_opts = rebuild_options(opt_list, opt82)
    new_payload = payload[: BOOTP_FIXED_LEN + len(DHCP_MAGIC)] + new_opts
    if giaddr:
        new_payload = set_giaddr(new_payload, giaddr)

    new_udp_len = UDP_HDR_LEN + len(new_payload)
    new_ip_len = ihl + new_udp_len

    # Update IPv4 and UDP lengths, then fix checksums.
    ip_hdr = bytearray(pkt[ip_off : ip_off + ihl])
    ip_hdr[2:4] = struct.pack("!H", new_ip_len)
    ip_hdr[10:12] = b"\x00\x00"
    ip_hdr[10:12] = struct.pack("!H", checksum16(bytes(ip_hdr)))

    udp_hdr = bytearray(pkt[udp_off : udp_off + UDP_HDR_LEN])
    udp_hdr[4:6] = struct.pack("!H", new_udp_len)
    udp_hdr[6:8] = b"\x00\x00"

    # Rewrite L2 src/dst for uplink egress if provided.
    dst = pkt[0:6]
    src = pkt[6:12]
    if uplink_mac:
        src = uplink_mac
    if dst_mac:
        dst = dst_mac

    eth_hdr = dst + src + struct.pack("!H", ETH_P_IP)
    udp_hdr[6:8] = struct.pack("!H", udp_checksum_ipv4(bytes(ip_hdr), bytes(udp_hdr), new_payload))
    return eth_hdr + ip_hdr + udp_hdr + new_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--access", action="append", required=True)
    parser.add_argument("--uplink", required=True)
    parser.add_argument("--remote-id", default="OLT-1")
    parser.add_argument("--circuit-id", default=None)
    parser.add_argument("--circuit-id-map", action="append", default=[])
    parser.add_argument("--giaddr", default=None)
    parser.add_argument("--dst-mac", default=None)
    parser.add_argument("--src-mac", default=None)
    args = parser.parse_args()

    remote_id = parse_remote_id(args.remote_id)
    default_circuit_id = args.circuit_id.encode() if args.circuit_id else None
    circuit_id_map: dict[str, bytes] = {}
    for item in args.circuit_id_map:
        if "=" not in item:
            continue
        iface, value = item.split("=", 1)
        iface = iface.strip()
        if iface:
            circuit_id_map[iface] = value.encode()
    dst_mac = mac_to_bytes(args.dst_mac) if args.dst_mac else None
    src_mac = mac_to_bytes(args.src_mac) if args.src_mac else None

    recv_socks = []
    for iface in args.access + [args.uplink]:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        s.bind((iface, 0))
        recv_socks.append((s, iface))

    send_uplink = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    send_uplink.bind((args.uplink, 0))

    send_access = {}
    down_access = {}
    for iface in args.access:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        s.bind((iface, 0))
        send_access[iface] = s
        d = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        d.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        d.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        d.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, iface.encode())
        d.bind(("0.0.0.0", DHCP_SERVER_PORT))
        down_access[iface] = d

    mac_table = {}

    last_log = 0
    while True:
        rlist, _, _ = select.select([s for s, _ in recv_socks], [], [], 1.0)
        for s in rlist:
            pkt, addr = s.recvfrom(65535)
            iface = next(i for sock, i in recv_socks if sock == s)
            if len(addr) >= 3 and addr[2] == PACKET_OUTGOING:
                continue

            if iface == args.uplink:
                # Only relay DHCP server->client traffic; regular traffic is routed by kernel.
                out = fix_ipv4_udp_checksum(pkt, zero_udp=True)
                if len(out) < ETH_HDR_LEN:
                    continue
                eth_type = struct.unpack("!H", out[12:14])[0]
                if eth_type != ETH_P_IP:
                    continue
                ip_off = ETH_HDR_LEN
                ihl = (out[ip_off] & 0x0F) * 4
                if len(out) < ip_off + ihl + UDP_HDR_LEN or out[ip_off + 9] != UDP_PROTO:
                    continue
                udp_off = ip_off + ihl
                src_port, dst_port = struct.unpack("!HH", out[udp_off : udp_off + 4])
                if src_port != DHCP_SERVER_PORT:
                    continue
                udp_len = struct.unpack("!H", out[udp_off + 4 : udp_off + 6])[0]
                if len(out) < udp_off + udp_len or udp_len < UDP_HDR_LEN:
                    continue
                payload = out[udp_off + UDP_HDR_LEN : udp_off + udp_len]
                dst_mac = out[0:6]
                out_iface = mac_table.get(dst_mac)
                if out_iface and out_iface in send_access:
                    down_access[out_iface].sendto(payload, ("255.255.255.255", DHCP_CLIENT_PORT))
                else:
                    for send_sock in down_access.values():
                        send_sock.sendto(payload, ("255.255.255.255", DHCP_CLIENT_PORT))
                continue

            out = handle_packet(
                pkt,
                iface,
                src_mac,
                dst_mac,
                remote_id,
                circuit_id_map,
                default_circuit_id,
                args.giaddr,
            )
            if out:
                send_uplink.send(fix_ipv4_udp_checksum(out))
            else:
                continue

            src_mac = pkt[6:12]
            mac_table[src_mac] = iface

            now = time.time()
            if now - last_log > 1:
                last_log = now


if __name__ == "__main__":
    main()
