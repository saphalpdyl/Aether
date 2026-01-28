from typing import Dict, Tuple
import time

from mininet.node import Host

from lib.secrets import __RADIUS_SECRET
from lib.nftables.helpers import nft_list_chain_rules , nft_get_counter_by_handle
from lib.radius.packet_builders import build_acct_interim, rad_acct_send_from_bng
from lib.radius.session import DHCPSession
from lib.constants import IDLE_GRACE_AFTER_CONNECT, MARK_IDLE_GRACE_SECONDS

def radius_handle_interim_updates(
        bng: Host, 
        sessions: Dict[Tuple[str,str], DHCPSession],
        radius_server_ip: str ="192.0.2.2",
        radius_secret: str = __RADIUS_SECRET,
        nas_ip: str="192.0.2.1",
        nas_port_id: str="bng-eth0"):
    now = time.time()
    try:
        nftables_snapshot = nft_list_chain_rules(bng)
    except Exception as e:
        print(f"Failed to get nftables snapshot for Interim-Update: {e}")
        return

    for key, s in sessions.items():
        try:
            if s.status == "EXPIRED":
                continue

            up_bytes, up_pkts = 0, 0
            down_bytes, down_pkts = 0, 0

            if s.nft_up_handle is not None:
                up_bytes, up_pkts = nft_get_counter_by_handle(nftables_snapshot, s.nft_up_handle) or (0,0)
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
            rad_acct_send_from_bng(bng, pkt, server_ip=radius_server_ip, secret=radius_secret)
            s.last_interim = now
            print(f"RADIUS Acct-Interim sent for mac={s.mac} ip={s.ip}")
        except Exception as e:
            print(f"RADIUS Acct-Interim failed for mac={s.mac} ip={s.ip}: {e}")

