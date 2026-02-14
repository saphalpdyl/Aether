import ipaddress
import re
import time
from dataclasses import dataclass
from typing import Dict, Tuple

from lib.services.traffic_shaper import BNGTrafficShaper
from lib.nftables.helpers import (
    nft_add_subscriber_rules,
    nft_allow_ip,
    nft_delete_rule_by_handle,
    nft_get_counter_by_handle,
    nft_list_chain_rules,
    nft_remove_ip,
)
from lib.radius.packet_builders import (
    build_access_request,
    build_acct_start,
    build_acct_stop,
    rad_acct_send_from_bng,
    rad_auth_send_from_bng,
)
from lib.radius.session import DHCPSession
from lib.services.event_dispatcher import BNGEventDispatcher

SessionKey = Tuple[str, str, str]
SessionMap = Dict[SessionKey, DHCPSession]
SessionsByIPMap = Dict[str, DHCPSession]
SessionsBySessionIDMap = Dict[str, DHCPSession]


@dataclass
class Tombstone:
    ip_at_stop: str
    latest_state_update_ts_at_stop: int
    stopped_at: float
    reason: str
    missing_seen: bool = False

@dataclass
class RadiusReplyResult:
    download_speed_kbit: int
    upload_speed_kbit: int
    download_burst_kbit: int
    upload_burst_kbit: int

TombstoneMap = Dict[SessionKey, Tombstone]

_OSS_VSA_RE = re.compile(r"Attr-26\.43242\.(\d+)\s*=\s*([^\s]+)")
_OSS_NAMED_RE = re.compile(r"OSS-(Download|Upload)-(Speed|Burst)\s*[:=]+\s*([^\s]+)", re.IGNORECASE)

def _parse_radius_int(token: str) -> int:
    t = token.strip().strip('"')
    if t.lower().startswith("0x"):
        return int(t, 16)
    return int(t, 10)


def parse_radius_reply_result(response_text: str) -> RadiusReplyResult | None:
    """
    Parse speed AVPs from radius output text.
    Supports:
      - Attr-26.43242.1 = 0x000186a0   (download)
      - Attr-26.43242.2 = 0x00007530   (upload)
      - OSS-Download-Speed := 100000
      - OSS-Upload-Speed := 30000
      - OSS-Download-Burst := 500
      - OSS-Upload-Burst := 150
    """
    download_kbit: int | None = None
    upload_kbit: int | None = None
    download_burst_kbit: int | None = None
    upload_burst_kbit: int | None = None

    for line in response_text.splitlines():
        m_vsa = _OSS_VSA_RE.search(line)
        if m_vsa:
            attr_type = int(m_vsa.group(1))
            try:
                value = _parse_radius_int(m_vsa.group(2))
            except Exception:
                continue
            if attr_type == 1:
                download_kbit = value
            elif attr_type == 2:
                upload_kbit = value
            elif attr_type == 3:
                download_burst_kbit = value
            elif attr_type == 4:
                upload_burst_kbit = value
            continue

        m_named = _OSS_NAMED_RE.search(line)
        if m_named:
            direction = m_named.group(1).lower()
            kind = m_named.group(2).lower()
            try:
                value = _parse_radius_int(m_named.group(3))
            except Exception:
                continue
            if direction == "download" and kind == "speed":
                download_kbit = value
            elif direction == "upload" and kind == "speed":
                upload_kbit = value
            elif direction == "download" and kind == "burst":
                download_burst_kbit = value
            elif direction == "upload" and kind == "burst":
                upload_burst_kbit = value

    if download_kbit is None or upload_kbit is None:
        return None

    return RadiusReplyResult(
        download_speed_kbit=download_kbit,
        upload_speed_kbit=upload_kbit,
        download_burst_kbit=download_burst_kbit,
        upload_burst_kbit=upload_burst_kbit,
    )

def decode_bytes(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


async def install_rules_and_baseline(s: DHCPSession, ip: str, mac: str, iface: str) -> None:
    try:
        up_handle, down_handle = await nft_add_subscriber_rules(ip=ip, mac=mac, sub_if=iface)
        s.nft_up_handle = up_handle
        s.nft_down_handle = down_handle

        snapshot = await nft_list_chain_rules()
        base_up_bytes, base_up_pkts = nft_get_counter_by_handle(snapshot, up_handle) or (0, 0)
        base_down_bytes, base_down_pkts = nft_get_counter_by_handle(snapshot, down_handle) or (0, 0)
        s.base_up_bytes = base_up_bytes
        s.base_down_bytes = base_down_bytes
        s.base_up_pkts = base_up_pkts
        s.base_down_pkts = base_down_pkts
    except Exception as e:
        print(f"Failed to install nftables rules for mac={mac} ip={ip}: {e}")


async def authorize_session(
    s: DHCPSession,
    ip: str,
    mac: str,
    iface: str,
    radius_server_ip: str,
    radius_secret: str,
    nas_ip: str,
    nas_port_id: str,
    ensure_rules: bool = False,
    *,
    traffic_shaper: BNGTrafficShaper,
) -> str | None:
    access_request_pkt = build_access_request(s, nas_ip=nas_ip, nas_port_id=nas_port_id)
    access_request_response = await rad_auth_send_from_bng(
        access_request_pkt, server_ip=radius_server_ip, secret=radius_secret
    )

    if not access_request_response or not access_request_response.strip():
        raise RuntimeError("RADIUS Access-Request returned empty response")

    response_text = access_request_response.strip()
    print(
        f"RADIUS Access-Request response user={s.relay_id}/{s.remote_id}/{s.circuit_id}: "
        f"{response_text}"
    )

    if re.search(r"No reply from server", response_text, re.IGNORECASE):
        raise RuntimeError("RADIUS Access-Request got no reply from server")

    if re.search(r"Access-Reject", response_text):
        s.auth_state = "REJECTED"
        return "REJECTED"

    if re.search(r"Access-Accept", response_text):
        if ensure_rules and (s.nft_up_handle is None or s.nft_down_handle is None):
            await install_rules_and_baseline(s, ip, mac, iface)

        # QoS
        parsed_policy = parse_radius_reply_result(response_text)
        if parsed_policy:
            print(
                f"Parsed RADIUS policy: download={parsed_policy.download_speed_kbit}kbit "
                f"upload={parsed_policy.upload_speed_kbit}kbit "
                f"download_burst={parsed_policy.download_burst_kbit}kbit "
                f"upload_burst={parsed_policy.upload_burst_kbit}kbit"
            )

            qos_success = await traffic_shaper.add_traffic_shaping_rule(
                ip=ip,
                upload_speed_kbit=parsed_policy.upload_speed_kbit,
                download_speed_kbit=parsed_policy.download_speed_kbit,
                download_burst_kbit=parsed_policy.download_burst_kbit,
                upload_burst_kbit=parsed_policy.upload_burst_kbit,
            )

            if not qos_success:
                print(f"Failed to apply QoS for session mac={mac} ip={ip}")


        s.auth_state = "AUTHORIZED"
        if ip:
            try:
                ip_clean = str(ip).replace("\x00", "")
                ipaddress.ip_address(ip_clean)
                await nft_allow_ip(ip_clean)
            except Exception:
                print(f"Skip nft allow: invalid ip={ip!r}")

        acct_start_pkt = build_acct_start(s, nas_ip=nas_ip, nas_port_id=nas_port_id)
        await rad_acct_send_from_bng(acct_start_pkt, server_ip=radius_server_ip, secret=radius_secret)

        print(f"RADIUS Acct-Start sent for mac={s.mac} ip={s.ip}")
        return "AUTHORIZED"

    raise RuntimeError(f"RADIUS Access-Request unexpected response: {response_text}")


async def get_counters_for_session(s: DHCPSession, nftables_snapshot=None) -> Tuple[int, int, int, int]:
    if nftables_snapshot is None:
        nftables_snapshot = await nft_list_chain_rules()

    up_bytes, up_pkts = 0, 0
    down_bytes, down_pkts = 0, 0

    if s.nft_up_handle is not None:
        up_bytes, up_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_up_handle) or (0, 0)
    if s.nft_down_handle is not None:
        down_bytes, down_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_down_handle) or (0, 0)

    total_in_octets = max(0, up_bytes - s.base_up_bytes)
    total_out_octets = max(0, down_bytes - s.base_down_bytes)
    total_in_pkts = max(0, up_pkts - s.base_up_pkts)
    total_out_pkts = max(0, down_pkts - s.base_down_pkts)

    return total_in_octets, total_out_octets, total_in_pkts, total_out_pkts


async def terminate_session(
    s: DHCPSession,
    cause: str,
    radius_server_ip: str,
    radius_secret: str,
    nas_ip: str,
    nas_port_id: str,
    traffic_shaper: BNGTrafficShaper,
    nftables_snapshot=None,
    delete_rules: bool = True,
    event_dispatcher: BNGEventDispatcher | None = None,
) -> bool:
    try:
        if nftables_snapshot is None:
            nftables_snapshot = await nft_list_chain_rules()

        total_in_octets, total_out_octets, total_in_pkts, total_out_pkts = await get_counters_for_session(
            s, nftables_snapshot
        )

        if s.auth_state == "AUTHORIZED":
            # Remove QoS
            if s.ip:
                qos_success = await traffic_shaper.remove_traffic_shaping_rule( ip=s.ip )

                if not qos_success:
                    print(f"Failed to remove QoS for session mac={s.mac} ip={s.ip}")

            pkt = build_acct_stop(
                s,
                nas_ip=nas_ip,
                nas_port_id=nas_port_id,
                cause=cause,
                input_bytes=total_in_octets,
                output_bytes=total_out_octets,
                input_pkts=total_in_pkts,
                output_pkts=total_out_pkts,
            )
            await rad_acct_send_from_bng(pkt, server_ip=radius_server_ip, secret=radius_secret)
            s.auth_state = "PENDING_AUTH"

        if s.mac is not None and s.ip:
            try:
                ip_clean = str(s.ip).replace("\x00", "")
                ipaddress.ip_address(ip_clean)
                await nft_remove_ip(ip_clean)
            except Exception:
                print(f"Skip nft remove: invalid ip={s.ip!r}")

        if delete_rules:
            if s.nft_up_handle is not None:
                await nft_delete_rule_by_handle(s.nft_up_handle)
            if s.nft_down_handle is not None:
                await nft_delete_rule_by_handle(s.nft_down_handle)

        if event_dispatcher is not None:
            await event_dispatcher.dispatch_session_stop(
                s,
                input_octets=total_out_octets,
                output_octets=total_in_octets,
                input_packets=total_out_pkts,
                output_packets=total_in_pkts,
                terminate_cause=cause,
            )

        return True
    except Exception as e:
        print(f"RADIUS Acct-Stop failed for mac={s.mac} ip={s.ip}: {e}")
        return False


def remove_session_from_maps(
    s: DHCPSession,
    sessions: SessionMap,
    sessions_by_ip: SessionsByIPMap,
    sessions_by_session_id: SessionsBySessionIDMap,
    tombstones: TombstoneMap,
    bng_id: str,
    reason: str = "Admin-Reset",
) -> None:
    key = (bng_id, s.circuit_id, s.remote_id)
    sessions.pop(key, None)
    if s.ip:
        sessions_by_ip.pop(s.ip, None)
    sessions_by_session_id.pop(s.session_id, None)
    tombstones[key] = Tombstone(
        ip_at_stop=s.ip or "",
        latest_state_update_ts_at_stop=s.expiry or int(time.time()),
        stopped_at=time.time(),
        reason=reason,
        missing_seen=False,
    )
