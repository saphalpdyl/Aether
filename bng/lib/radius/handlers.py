from typing import Dict, Tuple
import time

from lib.services.event_dispatcher import BNGEventDispatcher
from lib.secrets import __RADIUS_SECRET
from lib.nftables.helpers import nft_list_chain_rules , nft_get_counter_by_handle
from lib.radius.packet_builders import build_acct_interim, rad_acct_send_from_bng
from lib.radius.session import DHCPSession
from lib.constants import IDLE_GRACE_AFTER_CONNECT, MARK_IDLE_GRACE_SECONDS

async def radius_handle_interim_updates(
    sessions: Dict[Tuple[str,str,str], DHCPSession],
    radius_server_ip: str ="192.0.2.2",
    radius_secret: str = __RADIUS_SECRET,
    nas_ip: str="192.0.2.1",
    nas_port_id: str="eth0",
    event_dispatcher: BNGEventDispatcher | None = None,
):
    now = time.time()
    try:
        if sessions is None or len(sessions) == 0:
            return
        nftables_snapshot = await nft_list_chain_rules()
    except Exception as e:
        print(f"Failed to get nftables snapshot for Interim-Update: {e}")
        return

    for key, s in sessions.items():
        try:
            if s.status == "EXPIRED":
                continue

            if s.auth_state != "AUTHORIZED":
                continue

            up_bytes, up_pkts = 0, 0
            down_bytes, down_pkts = 0, 0

            print(f"Process up handles: {s.nft_up_handle}, down handle: {s.nft_down_handle} for session mac={s.mac} ip={s.ip}")
            if s.nft_up_handle is not None:
                up_bytes, up_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_up_handle) or (0,0)
                print(f"Got up bytes: {up_bytes}, up pkts: {up_pkts} for session mac={s.mac} ip={s.ip}")
            if s.nft_down_handle is not None:
                down_bytes, down_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_down_handle) or (0,0)

            total_in_octets = max(0, up_bytes - s.base_up_bytes)
            total_out_octets = max(0, down_bytes - s.base_down_bytes)
            total_in_pkts = max(0, up_pkts - s.base_up_pkts)
            total_out_pkts = max(0, down_pkts - s.base_down_pkts)

            # Check for idle session
            prev_in = s.last_up_bytes or 0
            prev_out = s.last_down_bytes or 0
            if (total_in_octets != prev_in) or (total_out_octets != prev_out):
                s.last_traffic_seen_ts = now

            # Edge case: If we have never seen any traffic, check for idle based on first seen time
            if s.last_traffic_seen_ts is None and (now - s.first_seen) >= IDLE_GRACE_AFTER_CONNECT:
                print(f"Session idle due to no traffic after connect: mac={s.mac} ip={s.ip}")
                s.last_idle_ts = now
                s.last_traffic_seen_ts = now
                s.status = "IDLE"

            # If we have seen traffic before, check for idle based on last traffic seen
            if s.last_traffic_seen_ts is not None:
                if total_in_octets == (s.last_up_bytes or 0) and total_out_octets == (s.last_down_bytes or 0):
                    idle_time = now - s.last_traffic_seen_ts
                    if idle_time >= MARK_IDLE_GRACE_SECONDS and s.status != "IDLE":
                        print(f"Session idle due to inactivity: mac={s.mac} ip={s.ip}")
                        s.last_idle_ts = now
                        s.status = "IDLE"
                else:
                    s.status = "ACTIVE"

            s.last_up_bytes = total_in_octets
            s.last_down_bytes = total_out_octets

            pkt = build_acct_interim(s, nas_ip=nas_ip, nas_port_id=nas_port_id,
                input_bytes=total_in_octets,
                output_bytes=total_out_octets,
                input_pkts=total_in_pkts,
                output_pkts=total_out_pkts,
            )
            await rad_acct_send_from_bng(pkt, server_ip=radius_server_ip, secret=radius_secret)
            s.last_interim = now

            if event_dispatcher:
                await event_dispatcher.dispatch_session_update(
                    s,
                    input_octets=total_out_octets,
                    output_octets=total_in_octets,
                    input_packets=total_out_pkts,
                    output_packets=total_in_pkts,
                )
            print(f"RADIUS Acct-Interim sent for mac={s.mac} ip={s.ip}")
        except Exception as e:
            print(f"RADIUS Acct-Interim failed for mac={s.mac} ip={s.ip}: {e}")
