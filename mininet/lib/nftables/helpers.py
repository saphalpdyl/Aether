import json
import subprocess
from typing import Tuple


def _cmd(command: str) -> str:
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.stdout or ""

# nftables helpers
def nft_list_chain_rules():
    out = _cmd("nft -j list chain inet bngacct sess")
    print("nft list chain output:", out)

    try:

        if not out or not out.strip():
            return {}

        return json.loads(out)

    except json.JSONDecodeError as e:
        print(f"INSIDE Failed to parse nftables JSON output: {e} with output: {out}")
        return {}

def nft_find_rule_handle(nft_json: dict, comment_match: str):
    for item in nft_json.get("nftables", []):
        rule = item.get("rule")
        if not rule:
            continue

        # Check for correct table and chain
        if rule.get("table") != "bngacct" or rule.get("chain") != "sess":
            continue

        comment = rule.get("comment", None);
        if comment == comment_match:
            return rule.get("handle", None)

    return None

def nft_add_subscriber_rules(
    ip: str,
    mac: str,
    sub_if: str = "eth0", # if = interface
    # NOTE: We have eth0 as the default iface because we want to measure on subscriber facing interface 
    #   We could have measured on eth1 ( upstream facing ) but that would not capture traffic that is dropped by BNG itself
):
    mac_l = mac.lower()

    # Upload counter rule
    _cmd(
        f"nft \'add rule inet bngacct sess iif \"{sub_if}\" ip saddr {ip} counter "
        f"comment \"sub;mac={mac_l};dir=up;ip={ip}\"\'"
    )

    # Download counter rule
    _cmd(
        f"nft \'add rule inet bngacct sess oif \"{sub_if}\" ip daddr {ip} counter "
        f"comment \"sub;mac={mac_l};dir=down;ip={ip}\"\'"
    )

    nftables_data = nft_list_chain_rules()
    up_rule_handle = nft_find_rule_handle(nftables_data, f"sub;mac={mac_l};dir=up;ip={ip}")
    down_rule_handle = nft_find_rule_handle(nftables_data, f"sub;mac={mac_l};dir=down;ip={ip}")

    if up_rule_handle is None or down_rule_handle is None:
        raise RuntimeError("Failed to add nftables rules for subscriber")

    return up_rule_handle, down_rule_handle

def nft_delete_rule_by_handle(handle: int):
    _cmd(f"nft delete rule inet bngacct sess handle {handle} 2>/dev/null || true")


def nft_get_counter_by_handle(nftables_json, handle: int) -> Tuple[int, int] | None:
    for item in nftables_json.get("nftables", []):
        rule = item.get("rule")
        if not rule:
            continue

        if rule.get("table") != "bngacct" or rule.get("chain") != "sess":
            continue

        if rule.get("handle") != handle:
            continue

        expr = rule.get("expr", [])
        for e in expr:
            counter = e.get("counter", None)
            if counter:
                return counter.get("bytes", 0), counter.get("packets", 0)

    return None

def nft_allow_mac(mac: str):
    m = mac.lower()
    _cmd(f"nft add element inet aether_auth authed_macs {{ {m} }}")

def nft_remove_mac(mac: str):
    m = mac.lower()
    _cmd(f"nft delete element inet aether_auth authed_macs {{ {m} }}")
