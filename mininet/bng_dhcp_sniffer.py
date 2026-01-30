#!/usr/bin/env python3
import argparse
import json
import time
import socket
import struct

ETH_P_ALL = 0x0003
ETH_P_IP = 0x0800
UDP_PROTO = 17
ETH_HDR_LEN = 14
IPV4_MIN_IHL = 5
UDP_HDR_LEN = 8
BOOTP_FIXED_LEN = 236
DHCP_MAGIC = b"\x63\x82\x53\x63"

DHCP_OPTION_PAD = 0
DHCP_OPTION_END = 255
DHCP_OPTION_MESSAGE_TYPE = 53
DHCP_OPTION_REQUESTED_IP = 50
DHCP_OPTION_LEASE_TIME = 51
DHCP_OPTION_RELAY_AGENT = 82
DHCP_RELAY_SUBOPT_CIRCUIT_ID = 1
DHCP_RELAY_SUBOPT_REMOTE_ID = 2

DHCP_CLIENT_PORT = 68
DHCP_SERVER_PORT = 67

DHCP_MSG_DISCOVER = 1
DHCP_MSG_OFFER = 2
DHCP_MSG_REQUEST = 3
DHCP_MSG_DECLINE = 4
DHCP_MSG_ACK = 5
DHCP_MSG_NAK = 6
DHCP_MSG_RELEASE = 7
DHCP_MSG_INFORM = 8


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


def parse_opt82(data: bytes) -> tuple[bytes | None, bytes | None]:
    circuit_id = None
    remote_id = None
    i = 0
    while i + 1 < len(data):
        code = data[i]
        ln = data[i + 1]
        val = data[i + 2 : i + 2 + ln]
        if code == DHCP_RELAY_SUBOPT_CIRCUIT_ID:
            circuit_id = val
        elif code == DHCP_RELAY_SUBOPT_REMOTE_ID:
            remote_id = val
        i += 2 + ln
    return circuit_id, remote_id


def decode_dhcp(pkt: bytes):
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
    if not (
        (src_port == DHCP_CLIENT_PORT and dst_port == DHCP_SERVER_PORT)
        or (src_port == DHCP_SERVER_PORT and dst_port == DHCP_CLIENT_PORT)
    ):
        return None
    if len(pkt) < udp_off + udp_len:
        return None

    payload = pkt[udp_off + UDP_HDR_LEN : udp_off + udp_len]
    if len(payload) < BOOTP_FIXED_LEN + len(DHCP_MAGIC):
        return None
    if payload[BOOTP_FIXED_LEN : BOOTP_FIXED_LEN + len(DHCP_MAGIC)] != DHCP_MAGIC:
        return None

    opts = payload[BOOTP_FIXED_LEN + len(DHCP_MAGIC) :]
    opt_list = parse_options(opts)

    msg_type = None
    circuit_id = None
    remote_id = None
    requested_ip = None
    lease_time = None
    for code, data in opt_list:
        if code == DHCP_OPTION_MESSAGE_TYPE and data:
            msg_type = data[0]
        elif code == DHCP_OPTION_REQUESTED_IP and len(data) == 4:
            requested_ip = socket.inet_ntoa(data)
        elif code == DHCP_OPTION_LEASE_TIME and len(data) == 4:
            lease_time = struct.unpack("!I", data)[0]
        elif code == DHCP_OPTION_RELAY_AGENT:
            circuit_id, remote_id = parse_opt82(data)

    if circuit_id is None and remote_id is None:
        return None

    xid = struct.unpack("!I", payload[4:8])[0]
    ciaddr = socket.inet_ntoa(payload[12:16])
    yiaddr = socket.inet_ntoa(payload[16:20])
    giaddr = socket.inet_ntoa(payload[24:28])
    chaddr = payload[28:34]

    ip_addr = yiaddr if yiaddr != "0.0.0.0" else ciaddr
    expiry = None
    if msg_type == DHCP_MSG_ACK and lease_time is not None:
        expiry = int(time.time() + lease_time)
    return {
        "msg_type": msg_type,
        "circuit_id": circuit_id,
        "remote_id": remote_id,
        "src_port": src_port,
        "dst_port": dst_port,
        "xid": xid,
        "chaddr": chaddr,
        "ip": ip_addr,
        "requested_ip": requested_ip,
        "lease_time": lease_time,
        "expiry": expiry,
        "giaddr": giaddr,
    }


def _encode_event(info: dict) -> dict:
    out = dict(info)
    if isinstance(out.get("circuit_id"), (bytes, bytearray)):
        out["circuit_id"] = out["circuit_id"].decode(errors="replace")
    if isinstance(out.get("remote_id"), (bytes, bytearray)):
        out["remote_id"] = out["remote_id"].decode(errors="replace")
    if isinstance(out.get("chaddr"), (bytes, bytearray)):
        out["chaddr"] = out["chaddr"].hex()
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iface", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Minimal standalone mode: just decode and print events.
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    sock.bind((args.iface, 0))
    while True:
        pkt, _ = sock.recvfrom(65535)
        info = decode_dhcp(pkt)
        if info:
            info["event"] = "dhcp"
            if args.json:
                print(json.dumps(_encode_event(info)), flush=True)
            else:
                print(info, flush=True)


if __name__ == "__main__":
    main()
