#!/usr/bin/env python3
import argparse
import json
import time
import socket
import struct
import select

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
DHCP_RELAY_SUBOPT_RELAY_ID = 12

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


def parse_opt82(data: bytes) -> tuple[bytes | None, bytes | None, bytes | None]:
    circuit_id = None
    remote_id = None
    relay_id = None
    i = 0
    while i + 1 < len(data):
        code = data[i]
        ln = data[i + 1]
        val = data[i + 2 : i + 2 + ln]
        if code == DHCP_RELAY_SUBOPT_CIRCUIT_ID:
            circuit_id = val
        elif code == DHCP_RELAY_SUBOPT_REMOTE_ID:
            remote_id = val
        elif code == DHCP_RELAY_SUBOPT_RELAY_ID:
            relay_id = val
        i += 2 + ln
    return circuit_id, remote_id, relay_id


def build_option82(
    circuit_id: bytes | None, remote_id: bytes | None, relay_id: bytes | None
) -> bytes:
    parts = []
    if circuit_id is not None:
        parts.append(bytes([DHCP_RELAY_SUBOPT_CIRCUIT_ID, len(circuit_id)]) + circuit_id)
    if remote_id is not None:
        parts.append(bytes([DHCP_RELAY_SUBOPT_REMOTE_ID, len(remote_id)]) + remote_id)
    if relay_id is not None:
        parts.append(bytes([DHCP_RELAY_SUBOPT_RELAY_ID, len(relay_id)]) + relay_id)
    data = b"".join(parts)
    if len(data) > 255:
        data = data[:255]
    return bytes([DHCP_OPTION_RELAY_AGENT, len(data)]) + data


def checksum16(data: bytes) -> int:
    if len(data) % 2 == 1:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) + data[i + 1]
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def rebuild_options(opts: list[tuple[int, bytes]], opt82: bytes) -> bytes:
    out = bytearray()
    for code, data in opts:
        if code == DHCP_OPTION_RELAY_AGENT:
            continue
        if code in (DHCP_OPTION_PAD, DHCP_OPTION_END):
            continue
        out.extend(bytes([code, len(data)]) + data)
    out.extend(opt82)
    out.extend(bytes([DHCP_OPTION_END]))
    return bytes(out)


def set_giaddr(payload: bytes, giaddr: str) -> bytes:
    # giaddr is at bytes 24..28 of BOOTP header.
    return payload[:24] + socket.inet_aton(giaddr) + payload[28:]


def decode_dhcp_payload(payload: bytes, src_port: int, dst_port: int):
    """Decode DHCP from UDP payload (BOOTP message)"""
    if len(payload) < BOOTP_FIXED_LEN + len(DHCP_MAGIC):
        return None
    if payload[BOOTP_FIXED_LEN : BOOTP_FIXED_LEN + len(DHCP_MAGIC)] != DHCP_MAGIC:
        return None

    opts = payload[BOOTP_FIXED_LEN + len(DHCP_MAGIC) :]
    opt_list = parse_options(opts)

    msg_type = None
    circuit_id = None
    remote_id = None
    relay_id = None
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
            circuit_id, remote_id, relay_id = parse_opt82(data)

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
        "relay_id": relay_id,
        "src_port": src_port,
        "dst_port": dst_port,
        "xid": xid,
        "chaddr": chaddr,
        "ip": ip_addr,
        "requested_ip": requested_ip,
        "lease_time": lease_time,
        "expiry": expiry,
        "giaddr": giaddr,
        "payload": payload,
    }


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
        or (src_port == DHCP_SERVER_PORT and dst_port == DHCP_SERVER_PORT) # When SR Linux relays packetsm, its 67 -> 67
    ):
        return None
    if len(pkt) < udp_off + udp_len:
        return None

    payload = pkt[udp_off + UDP_HDR_LEN : udp_off + udp_len]
    return decode_dhcp_payload(payload, src_port, dst_port)


def decode_dhcp_with_reason(pkt: bytes):
    if len(pkt) < ETH_HDR_LEN:
        return None, "short_eth"
    eth_type = struct.unpack("!H", pkt[12:14])[0]
    if eth_type != ETH_P_IP:
        return None, f"eth_type_{eth_type:#x}"
    ip_off = ETH_HDR_LEN
    vihl = pkt[ip_off]
    ihl = (vihl & 0x0F) * 4
    if ihl < IPV4_MIN_IHL * 4:
        return None, "bad_ihl"
    if len(pkt) < ip_off + ihl + UDP_HDR_LEN:
        return None, "short_ip"
    if pkt[ip_off + 9] != UDP_PROTO:
        return None, "not_udp"
    udp_off = ip_off + ihl
    src_port, dst_port, udp_len, _ = struct.unpack("!HHHH", pkt[udp_off : udp_off + 8])
    if not (
        (src_port == DHCP_CLIENT_PORT and dst_port == DHCP_SERVER_PORT)
        or (src_port == DHCP_SERVER_PORT and dst_port == DHCP_CLIENT_PORT)
        or (src_port == DHCP_SERVER_PORT and dst_port == DHCP_SERVER_PORT) # When SR Linux relays packetsm, its 67 -> 67
    ):
        return None, f"ports_{src_port}_{dst_port}"
    if len(pkt) < udp_off + udp_len:
        return None, "short_udp"
    payload = pkt[udp_off + UDP_HDR_LEN : udp_off + udp_len]
    if len(payload) < BOOTP_FIXED_LEN + len(DHCP_MAGIC):
        return None, "short_bootp"
    if payload[BOOTP_FIXED_LEN : BOOTP_FIXED_LEN + len(DHCP_MAGIC)] != DHCP_MAGIC:
        return None, "bad_magic"
    result = decode_dhcp(pkt)
    if result:
        # Add IP header src/dst for filtering
        result["src_ip"] = socket.inet_ntoa(pkt[ip_off + 12 : ip_off + 16])
        result["dst_ip"] = socket.inet_ntoa(pkt[ip_off + 16 : ip_off + 20])
    return result, "ok"


def _encode_event(info: dict) -> dict:
    out = dict(info)
    out.pop("payload", None)
    if isinstance(out.get("circuit_id"), (bytes, bytearray)):
        out["circuit_id"] = out["circuit_id"].decode(errors="replace")
    if isinstance(out.get("remote_id"), (bytes, bytearray)):
        out["remote_id"] = out["remote_id"].decode(errors="replace")
    if isinstance(out.get("relay_id"), (bytes, bytearray)):
        out["relay_id"] = out["relay_id"].decode(errors="replace")
    if isinstance(out.get("chaddr"), (bytes, bytearray)):
        out["chaddr"] = out["chaddr"].hex()
    return out


def emit_event(info: dict, emit_json: bool):
    """Emit DHCP event to stdout"""
    event_info = dict(info)
    event_info["event"] = "dhcp"
    event_info.pop("payload", None)
    
    if emit_json:
        print(json.dumps(_encode_event(event_info)), flush=True)
    else:
        print(event_info, flush=True)


def relay_loop(
    client_if: str,
    uplink_if: str,
    server_ip: str,
    giaddr: str,
    remote_id: str | None,
    relay_id: str | None,
    src_ip: str,
    src_mac: bytes | None,
    dst_mac: bytes | None,
    emit_json: bool,
    log_path: str | None,
    bng_id: str,
):
    logf = open(log_path, "a") if log_path else None
    def log(msg: str):
        if logf:
            logf.write(msg + "\n")
            logf.flush()

    # Filter at socket level to only IPv4 frames.
    raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_IP))
    raw.bind((client_if, 0))

    raw_uplink = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_IP))
    raw_uplink.bind((uplink_if, 0))

    uplink_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    uplink_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    uplink_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, uplink_if.encode())
    # Bind to 0.0.0.0 - SO_BINDTODEVICE restricts to uplink_if, kernel picks src IP
    uplink_sock.bind(("0.0.0.0", DHCP_SERVER_PORT))

    reply_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reply_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    reply_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, uplink_if.encode())
    reply_sock.bind(("0.0.0.0", DHCP_SERVER_PORT))

    down_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    down_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    down_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    down_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, client_if.encode())
    down_sock.bind(("0.0.0.0", DHCP_SERVER_PORT))

    while True:
        rlist, _, _ = select.select([raw, raw_uplink, reply_sock], [], [], 1.0)
        for s in rlist:
            if s is raw:
                # Client -> Server packets (including relay-to-server 67->67)
                pkt, _ = raw.recvfrom(65535)
                info, reason = decode_dhcp_with_reason(pkt)
                if not info:
                    log(f"drop: decode_dhcp none reason={reason}")
                    continue
                if info.get("dst_port") != DHCP_SERVER_PORT:
                    continue
                # Ignore server responses being routed out this interface (prevents loop)
                if info.get("src_ip") == server_ip:
                    continue
                
                log(
                    "rx client msg_type={msg_type} xid={xid} src_port={src_port} dst_port={dst_port} "
                    "circuit_id={circuit_id} remote_id={remote_id}".format(
                        msg_type=info.get("msg_type"),
                        xid=info.get("xid"),
                        src_port=info.get("src_port"),
                        dst_port=info.get("dst_port"),
                        circuit_id=info.get("circuit_id"),
                        remote_id=info.get("remote_id"),
                    )
                )
                
                # Emit event for client packet
                emit_event(info, emit_json)

                # Require Option 82 from access switch (circuit_id and remote_id)
                if info.get("circuit_id") is None and info.get("remote_id") is None:
                    log("drop: missing option82 from access switch")
                    continue

                payload = info.get("payload")
                if not payload:
                    log("drop: missing payload")
                    continue
                
                # Get the EXISTING circuit_id and remote_id from the packet (from access switch)
                # These should be PRESERVED
                existing_circuit_id = info.get("circuit_id")
                existing_remote_id = info.get("remote_id")
                
                # Build NEW Option 82 with:
                # - circuit_id: from access switch (preserve)
                # - remote_id: from access switch (preserve) OR CLI override if specified
                # - relay_id: from CLI args (add)
                final_remote_id = remote_id.encode() if remote_id else existing_remote_id
                relayid = bng_id.encode() if relay_id else None
                
                opt82 = build_option82(existing_circuit_id, final_remote_id, relayid)
                
                log(f"building opt82: circuit_id={existing_circuit_id} remote_id={final_remote_id} relay_id={relayid}")
                
                # Rebuild options (removes old Option 82, adds new one)
                opt_list = parse_options(payload[BOOTP_FIXED_LEN + len(DHCP_MAGIC) :])
                new_opts = rebuild_options(opt_list, opt82)
                new_payload = payload[: BOOTP_FIXED_LEN + len(DHCP_MAGIC)] + new_opts
                # Preserve existing giaddr if already set by upstream relay (e.g., SRL).
                if info.get("giaddr") in (None, "0.0.0.0"):
                    new_payload = set_giaddr(new_payload, giaddr)

                uplink_sock.sendto(new_payload, (server_ip, DHCP_SERVER_PORT))
                log("forwarded to server")
                
            elif s is raw_uplink:
                # Server -> Relay packets via raw uplink (catches traffic not destined to local IP)
                pkt, _ = raw_uplink.recvfrom(65535)
                info, reason = decode_dhcp_with_reason(pkt)
                if not info:
                    log(f"drop: decode_dhcp none reason={reason}")
                    continue
                if info.get("src_port") != DHCP_SERVER_PORT:
                    continue
                data = info.get("payload")
                if not data:
                    continue
                log(f"rx server msg_type={info.get('msg_type')} xid={info.get('xid')}")
                emit_event(info, emit_json)

                if info.get("giaddr") and info.get("giaddr") != "0.0.0.0":
                    down_sock.sendto(data, (info.get("giaddr"), DHCP_SERVER_PORT))
                    log(f"forwarded to relay giaddr={info.get('giaddr')}")
                else:
                    down_sock.sendto(data, ("255.255.255.255", DHCP_CLIENT_PORT))
                    log("forwarded to clients")

            elif s is reply_sock:
                # Server -> Relay packets (UDP socket receives DHCP replies)
                data, _ = reply_sock.recvfrom(65535)
                
                # Parse the DHCP payload (data is just the UDP payload)
                info = decode_dhcp_payload(data, DHCP_SERVER_PORT, DHCP_SERVER_PORT)
                if info:
                    log(f"rx server msg_type={info.get('msg_type')} xid={info.get('xid')}")
                    # Emit event for server packet
                    emit_event(info, emit_json)
                
                # Forward server replies:
                # - If giaddr is set, unicast to relay agent (giaddr) on port 67.
                # - Otherwise broadcast to clients on port 68.
                if info and info.get("giaddr") and info.get("giaddr") != "0.0.0.0":
                    down_sock.sendto(data, (info.get("giaddr"), DHCP_SERVER_PORT))
                    log(f"forwarded to relay giaddr={info.get('giaddr')}")
                else:
                    down_sock.sendto(data, ("255.255.255.255", DHCP_CLIENT_PORT))
                    log("forwarded to clients")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-if", required=True)
    parser.add_argument("--uplink-if", required=True)
    parser.add_argument("--server-ip", required=True)
    parser.add_argument("--giaddr", required=True)
    parser.add_argument("--remote-id", default=None, help="Override remote-id from access switch (optional)")
    parser.add_argument("--relay-id", default=None, help="Add relay-id sub-option 12 (optional)")
    parser.add_argument("--src-ip", required=True)
    parser.add_argument("--src-mac", default=None)
    parser.add_argument("--dst-mac", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--log", default=None)
    parser.add_argument("--bng-id", required=True, help="BNG identifier for distributed deployment")
    args = parser.parse_args()

    src_mac = bytes.fromhex(args.src_mac.replace(":", "")) if args.src_mac else None
    dst_mac = bytes.fromhex(args.dst_mac.replace(":", "")) if args.dst_mac else None

    relay_loop(
        args.client_if,
        args.uplink_if,
        args.server_ip,
        args.giaddr,
        args.remote_id,
        args.relay_id,
        args.src_ip,
        src_mac,
        dst_mac,
        args.json,
        args.log,
        args.bng_id,
    )


if __name__ == "__main__":
    main()
