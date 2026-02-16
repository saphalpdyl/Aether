#!/usr/bin/env python3
"""Generate lab artifacts from a single config YAML using Jinja2 templates."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROOT = Path(__file__).resolve().parent.parent

CONFIG_DEFAULT_PATH = ROOT / "aether.config.yaml"

TOPOLOGY_TEMPLATE_PATH = ROOT / "containerlab/topology.yaml.j2"
TOPOLOGY_OUTPUT_PATH = ROOT / "containerlab/topology.yml"

KEA_TEMPLATE_PATH = ROOT / "bng/conf/kea-dhcp4.conf.j2"
KEA_OUTPUT_PATH = ROOT / "bng/conf/kea-dhcp4.conf"

OSS_SEED_TEMPLATE_PATH = ROOT / "docker/oss-pg/init/02-oss-schema.sql.j2"
OSS_SEED_OUTPUT_PATH = ROOT / "docker/oss-pg/init/02-oss-schema.sql"


class ConfigError(ValueError):
    pass


def _require(obj: dict[str, Any], key: str, path: str) -> Any:
    if key not in obj:
        raise ConfigError(f"Missing required key: {path}.{key}")
    return obj[key]


def _parse_iface_index(name: str, ctx: str) -> int:
    if not isinstance(name, str) or not name.startswith("eth"):
        raise ConfigError(f"{ctx}: invalid interface name '{name}', expected ethN")
    suffix = name[3:]
    if not suffix.isdigit() or int(suffix) <= 0:
        raise ConfigError(f"{ctx}: invalid interface name '{name}', expected ethN")
    return int(suffix)


def _cidr_ip(cidr: str) -> str:
    return str(ipaddress.ip_interface(cidr).ip)


def _cidr_prefix(cidr_or_subnet: str) -> int:
    return ipaddress.ip_network(cidr_or_subnet, strict=False).prefixlen


def _deterministic_mac(seed: str) -> str:
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    b = bytearray(digest[:6])
    b[0] = (b[0] | 0x02) & 0xFE
    return ":".join(f"{x:02x}" for x in b)


def _normalize_access_node(raw: dict[str, Any], bng_id: str, idx: int) -> dict[str, Any]:
    node_cfg = _require(raw, "node-config", f"bngs[{bng_id}].access-nodes[{idx}]")

    remote_id = _require(node_cfg, "remote-id", f"access-nodes[{idx}].node-config")
    if not isinstance(remote_id, str) or not remote_id.strip():
        raise ConfigError(f"access-nodes[{idx}].node-config.remote-id must be a non-empty string")

    container_name = node_cfg.get("container-name") or remote_id

    topo = _require(node_cfg, "topology", f"access-nodes[{idx}].node-config")
    iface_cfg = _require(topo, "interfaces", f"access-nodes[{idx}].node-config.topology")
    iface_count = int(_require(iface_cfg, "count", f"access-nodes[{idx}].node-config.topology.interfaces"))
    if iface_count < 2:
        raise ConfigError(f"access node '{remote_id}': interface count must be >= 2")

    uplink_iface = _require(iface_cfg, "uplink-iface", f"access-nodes[{idx}].node-config.topology.interfaces")
    uplink_idx = _parse_iface_index(uplink_iface, f"access node '{remote_id}' uplink-iface")
    if uplink_idx > iface_count:
        raise ConfigError(
            f"access node '{remote_id}': uplink-iface {uplink_iface} is outside declared count={iface_count}"
        )

    subscriber_ifaces = iface_cfg.get("subscriber-ifaces")
    if subscriber_ifaces is None:
        subscriber_ifaces = [f"eth{i}" for i in range(1, iface_count + 1) if i != uplink_idx]
    if not subscriber_ifaces:
        raise ConfigError(f"access node '{remote_id}': subscriber-ifaces cannot be empty")

    normalized_sub_ifaces: list[str] = []
    seen_sub_ifaces: set[str] = set()
    for iface in subscriber_ifaces:
        i = _parse_iface_index(iface, f"access node '{remote_id}' subscriber-ifaces")
        if i > iface_count:
            raise ConfigError(
                f"access node '{remote_id}': subscriber iface {iface} is outside declared count={iface_count}"
            )
        if iface == uplink_iface:
            raise ConfigError(f"access node '{remote_id}': subscriber iface cannot equal uplink-iface ({iface})")
        if iface in seen_sub_ifaces:
            raise ConfigError(f"access node '{remote_id}': duplicate subscriber iface '{iface}'")
        seen_sub_ifaces.add(iface)
        normalized_sub_ifaces.append(iface)

    dhcp = _require(node_cfg, "dhcp", f"access-nodes[{idx}].node-config")
    dhcp_v4 = _require(dhcp, "ipv4", f"access-nodes[{idx}].node-config.dhcp")
    dhcp_addr = _require(dhcp_v4, "addr", f"access-nodes[{idx}].node-config.dhcp.ipv4")
    dhcp_subnet = _require(dhcp_v4, "subnet", f"access-nodes[{idx}].node-config.dhcp.ipv4")
    pool_start = _require(dhcp_v4, "pool-start", f"access-nodes[{idx}].node-config.dhcp.ipv4")
    pool_end = _require(dhcp_v4, "pool-end", f"access-nodes[{idx}].node-config.dhcp.ipv4")

    subnet = ipaddress.ip_network(dhcp_subnet, strict=False)
    if ipaddress.ip_address(dhcp_addr) not in subnet:
        raise ConfigError(f"access node '{remote_id}': dhcp addr {dhcp_addr} not in subnet {dhcp_subnet}")
    if ipaddress.ip_address(pool_start) not in subnet or ipaddress.ip_address(pool_end) not in subnet:
        raise ConfigError(f"access node '{remote_id}': DHCP pool must be inside subnet {dhcp_subnet}")

    uplink = _require(node_cfg, "uplink", f"access-nodes[{idx}].node-config")
    uplink_cidr = _require(uplink, "ipv4-cidr", f"access-nodes[{idx}].node-config.uplink")
    uplink_gw = _require(uplink, "default-gw", f"access-nodes[{idx}].node-config.uplink")

    bng_route = _require(node_cfg, "bng-route", f"access-nodes[{idx}].node-config")
    bng_route_subnet = _require(bng_route, "subnet", f"access-nodes[{idx}].node-config.bng-route")
    bng_route_next_hop = _require(bng_route, "next-hop", f"access-nodes[{idx}].node-config.bng-route")

    if str(ipaddress.ip_network(bng_route_subnet, strict=False)) != str(subnet):
        raise ConfigError(
            f"access node '{remote_id}': bng-route.subnet {bng_route_subnet} must match dhcp subnet {dhcp_subnet}"
        )

    return {
        "container_name": str(container_name),
        "remote_id": remote_id,
        "iface_count": iface_count,
        "subscriber_ifaces": normalized_sub_ifaces,
        "uplink_iface": uplink_iface,
        "dhcp_addr": str(dhcp_addr),
        "dhcp_subnet": str(subnet),
        "pool_start": str(pool_start),
        "pool_end": str(pool_end),
        "uplink_cidr": str(uplink_cidr),
        "uplink_default_gw": str(uplink_gw),
        "bng_route_subnet": str(subnet),
        "bng_route_next_hop": str(bng_route_next_hop),
    }


def load_and_validate_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("Top-level config must be a mapping")

    bngs = _require(raw, "bngs", "config")
    if not isinstance(bngs, list) or not bngs:
        raise ConfigError("config.bngs must be a non-empty list")
    if len(bngs) != 1:
        raise ConfigError("Current generator supports exactly one BNG entry")

    bng = bngs[0]
    if not isinstance(bng, dict):
        raise ConfigError("bngs[0] must be a mapping")

    bng_id = _require(bng, "bng-id", "bngs[0]")
    if not isinstance(bng_id, str) or not bng_id.strip():
        raise ConfigError("bngs[0].bng-id must be a non-empty string")

    topo = _require(bng, "topology", "bngs[0]")
    iface = _require(topo, "interfaces", "bngs[0].topology")
    ipv4 = _require(topo, "ipv4", "bngs[0].topology")
    services = _require(topo, "services", "bngs[0].topology")

    sub_iface = _require(iface, "subscriber", "bngs[0].topology.interfaces")
    up_iface = _require(iface, "upstream", "bngs[0].topology.interfaces")
    dhcp_up_iface = _require(iface, "dhcp-uplink", "bngs[0].topology.interfaces")

    sub_cidr = _require(ipv4, "subscriber-cidr", "bngs[0].topology.ipv4")
    up_cidr = _require(ipv4, "upstream-cidr", "bngs[0].topology.ipv4")
    dhcp_up_cidr = _require(ipv4, "dhcp-uplink-cidr", "bngs[0].topology.ipv4")
    default_gw = _require(ipv4, "default-gw", "bngs[0].topology.ipv4")
    nat_source_cidr = _require(ipv4, "nat-source-cidr", "bngs[0].topology.ipv4")

    for key in [
        "dhcp-server-ip",
        "radius-server-ip",
        "nas-ip",
        "redis-host",
        "oss-api-url",
        "kea-ctrl-url",
    ]:
        _require(services, key, "bngs[0].topology.services")

    access_nodes_raw = _require(bng, "access-nodes", "bngs[0]")
    if not isinstance(access_nodes_raw, list) or not access_nodes_raw:
        raise ConfigError("bngs[0].access-nodes must be a non-empty list")
    if len(access_nodes_raw) > 2:
        raise ConfigError("Current BNG entrypoint supports at most 2 access node routes")

    access_nodes = [_normalize_access_node(item, str(bng_id), i) for i, item in enumerate(access_nodes_raw, start=1)]

    seen_remote: set[str] = set()
    seen_container: set[str] = set()
    seen_subnets: set[str] = set()
    for node in access_nodes:
        if node["remote_id"] in seen_remote:
            raise ConfigError(f"Duplicate remote-id: {node['remote_id']}")
        if node["container_name"] in seen_container:
            raise ConfigError(f"Duplicate access node container-name: {node['container_name']}")
        if node["dhcp_subnet"] in seen_subnets:
            raise ConfigError(f"Duplicate DHCP subnet across access nodes: {node['dhcp_subnet']}")
        seen_remote.add(node["remote_id"])
        seen_container.add(node["container_name"])
        seen_subnets.add(node["dhcp_subnet"])

    env_overrides = bng.get("environment") or {}
    if not isinstance(env_overrides, dict):
        raise ConfigError("bngs[0].environment must be a mapping when provided")

    return {
        "bng_id": str(bng_id),
        "bng_node_name": str(bng_id),
        "subscriber_iface": str(sub_iface),
        "upstream_iface": str(up_iface),
        "dhcp_uplink_iface": str(dhcp_up_iface),
        "subscriber_cidr": str(sub_cidr),
        "upstream_cidr": str(up_cidr),
        "dhcp_uplink_cidr": str(dhcp_up_cidr),
        "default_gw": str(default_gw),
        "nat_source_cidr": str(nat_source_cidr),
        "services": services,
        "environment": {str(k): str(v) for k, v in env_overrides.items()},
        "access_nodes": access_nodes,
    }


def _relay_exec(node: dict[str, Any]) -> list[str]:
    iface_list = [f"eth{i}" for i in range(1, node["iface_count"] + 1)]
    wait_clause = " && ".join(f"ip link show {iface} >/dev/null 2>&1" for iface in iface_list)
    up_clause = " && ".join(f"ip link set {iface} up" for iface in iface_list)

    cmds = [
        f"sh -c \"for i in $(seq 1 50); do {wait_clause} && break; sleep 0.2; done\"",
    ]

    subscriber_ifaces = node["subscriber_ifaces"]
    if len(subscriber_ifaces) > 1:
        cmds.extend(
            [
                "sh -c \"ip link add br0 type bridge 2>/dev/null || true\"",
                f"sh -c \"{up_clause}\"",
                "sh -c \"" + " && ".join(f"ip link set {iface} master br0" for iface in subscriber_ifaces) + "\"",
                "sh -c \"ip link set br0 up\"",
                f"sh -c \"ip addr replace {node['dhcp_addr']}/{_cidr_prefix(node['dhcp_subnet'])} dev br0\"",
            ]
        )
    else:
        sub = subscriber_ifaces[0]
        cmds.extend(
            [
                f"sh -c \"{up_clause}\"",
                f"sh -c \"ip addr replace {node['dhcp_addr']}/{_cidr_prefix(node['dhcp_subnet'])} dev {sub}\"",
            ]
        )

    cmds.extend(
        [
            f"sh -c \"ip addr replace {node['uplink_cidr']} dev {node['uplink_iface']}\"",
            f"sh -c \"ip route replace default via {node['uplink_default_gw']} dev {node['uplink_iface']}\"",
            "sh -c \"sysctl -w net.ipv4.ip_forward=1 || true\"",
            "sh -c \"ip link set eth0 down || true\"",
        ]
    )

    return cmds


def build_render_context(cfg: dict[str, Any]) -> dict[str, Any]:
    access_nodes = []
    hosts = []
    host_links = []

    for idx, node in enumerate(cfg["access_nodes"], start=1):
        n = dict(node)
        n["agg_iface"] = f"eth{idx}"
        n["relay_exec"] = _relay_exec(node)
        n["uplink_ip"] = _cidr_ip(node["uplink_cidr"])
        n["subnet_prefix"] = _cidr_prefix(node["dhcp_subnet"])
        n["circuit_id_map"] = ",".join(
            f"{iface}=1/0/{_parse_iface_index(iface, node['remote_id'])}" for iface in node["subscriber_ifaces"]
        )

        access_nodes.append(n)

        for iface in node["subscriber_ifaces"]:
            host_name = f"h-{node['remote_id']}-{iface}"
            host_mac = _deterministic_mac(f"{cfg['bng_id']}/{node['remote_id']}/{iface}")
            hosts.append(
                {
                    "name": host_name,
                    "mac": host_mac,
                    "access_container": node["container_name"],
                    "access_iface": iface,
                }
            )
            host_links.append({"host": f"{host_name}:eth1", "access": f"{node['container_name']}:{iface}"})

    bng_env: dict[str, str] = {
        "BNG_IDENTIFIER": cfg["bng_id"],
        "BNG_SUBSCRIBER_IFACE": cfg["subscriber_iface"],
        "BNG_UPLINK_IFACE": cfg["upstream_iface"],
        "BNG_DHCP_UPLINK_IFACE": cfg["dhcp_uplink_iface"],
        "BNG_SUBSCRIBER_IP_CIDR": cfg["subscriber_cidr"],
        "BNG_UPLINK_IP_CIDR": cfg["upstream_cidr"],
        "BNG_DHCP_UPLINK_IP_CIDR": cfg["dhcp_uplink_cidr"],
        "BNG_DEFAULT_GW": cfg["default_gw"],
        "BNG_NAT_SOURCE_CIDR": cfg["nat_source_cidr"],
        "BNG_DHCP_SERVER_IP": cfg["services"]["dhcp-server-ip"],
        "BNG_RADIUS_SERVER_IP": cfg["services"]["radius-server-ip"],
        "BNG_NAS_IP": cfg["services"]["nas-ip"],
        "BNG_REDIS_HOST": cfg["services"]["redis-host"],
        "BNG_OSS_API_URL": cfg["services"]["oss-api-url"],
        "BNG_KEA_CTRL_URL": cfg["services"]["kea-ctrl-url"],
    }
    for idx, node in enumerate(access_nodes, start=1):
        bng_env[f"BNG_RELAY{idx}_SUBNET_CIDR"] = node["bng_route_subnet"]
        bng_env[f"BNG_RELAY{idx}_NEXT_HOP"] = node["bng_route_next_hop"]
    bng_env.update(cfg["environment"])

    bng_exec = [
        (
            f"sh -c \"for i in $(seq 1 50); do ip link show {cfg['subscriber_iface']} >/dev/null 2>&1 && "
            f"ip link show {cfg['upstream_iface']} >/dev/null 2>&1 && "
            f"ip link show {cfg['dhcp_uplink_iface']} >/dev/null 2>&1 && break; sleep 0.2; done; "
            "PYTHONUNBUFFERED=1 python3 -u /opt/bng/bng_main.py --bng-id $BNG_IDENTIFIER "
            ">>/proc/1/fd/1 2>>/proc/1/fd/2 &\""
        ),
        "sh -c \"coad >/proc/1/fd/1 2>/proc/1/fd/2 &\"",
        "sh -c \"iperf3 -s -D\"",
        "sh -c \"ip link set eth0 down || true\"",
        f"tc qdisc add dev {cfg['subscriber_iface']} root handle 1: htb r2q 100 default 9999",
        f"tc class add dev {cfg['subscriber_iface']} parent 1: classid 1:1 htb rate 1gbit",
        f"tc class add dev {cfg['subscriber_iface']} parent 1:1 classid 1:9999 htb rate 1gbit",
        f"tc qdisc add dev {cfg['upstream_iface']} root handle 1: htb r2q 100 default 9999",
        f"tc class add dev {cfg['upstream_iface']} parent 1: classid 1:1 htb rate 1gbit",
        f"tc class add dev {cfg['upstream_iface']} parent 1:1 classid 1:9999 htb rate 1gbit",
    ]

    upstream_exec = [
        "apk add --no-cache iptables dhcpcd curl iperf3 ethtool",
        "dhcpcd eth11",
        "sleep 5",
        "sysctl -w net.ipv4.ip_forward=1",
        "ip link set eth1 up",
        "ip link set eth2 up",
        f"ip addr add {cfg['default_gw']}/{_cidr_prefix(cfg['upstream_cidr'])} dev eth1",
        "ip addr add 198.18.0.254/24 dev eth2",
        "iptables -t nat -A POSTROUTING -s 198.18.0.0/24 -o eth11 -j MASQUERADE",
    ]
    bng_uplink_ip = _cidr_ip(cfg["upstream_cidr"])
    for node in access_nodes:
        upstream_exec.append(f"iptables -t nat -A POSTROUTING -s {node['dhcp_subnet']} -o eth11 -j MASQUERADE")
    for node in access_nodes:
        upstream_exec.append(f"ip route replace {node['dhcp_subnet']} via {bng_uplink_ip}")
    upstream_exec.extend(
        [
            "sh -c \"ip link set eth0 down || true\"",
            "sh -c \"iperf3 -s -D\"",
        ]
    )

    agg_bng_iface = f"eth{len(access_nodes) + 1}"

    return {
        "bng": cfg,
        "bng_env": bng_env,
        "bng_exec": bng_exec,
        "upstream_exec": upstream_exec,
        "hosts": hosts,
        "host_links": host_links,
        "access_nodes": access_nodes,
        "agg_bng_iface": agg_bng_iface,
    }


def _make_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    env.filters["tojson"] = lambda v: json.dumps(v)
    return env


def render_to_file(template_path: Path, output_path: Path, context: dict[str, Any], env: Environment) -> None:
    rel = template_path.relative_to(ROOT)
    template = env.get_template(str(rel))
    output = template.render(**context)
    if not output.endswith("\n"):
        output += "\n"
    output_path.write_text(output, encoding="utf-8")


def generate(cfg: dict[str, Any]) -> None:
    env = _make_jinja_env()
    ctx = build_render_context(cfg)

    render_to_file(TOPOLOGY_TEMPLATE_PATH, TOPOLOGY_OUTPUT_PATH, ctx, env)
    render_to_file(KEA_TEMPLATE_PATH, KEA_OUTPUT_PATH, ctx, env)
    render_to_file(OSS_SEED_TEMPLATE_PATH, OSS_SEED_OUTPUT_PATH, ctx, env)



def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lab files from config YAML")
    parser.add_argument("command", choices=["validate", "generate"])
    parser.add_argument("--config", default=str(CONFIG_DEFAULT_PATH), help="Path to config YAML")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path

    try:
        cfg = load_and_validate_config(cfg_path)
    except (ConfigError, FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(f"Config error: {exc}")
        return 1

    if args.command == "validate":
        print(f"Config validation successful: {cfg_path}")
        return 0

    for path in [TOPOLOGY_TEMPLATE_PATH, KEA_TEMPLATE_PATH, OSS_SEED_TEMPLATE_PATH]:
        if not path.exists():
            print(f"Config error: template file not found: {path}")
            return 1

    generate(cfg)
    print(f"Rendered {TOPOLOGY_OUTPUT_PATH} from {TOPOLOGY_TEMPLATE_PATH}")
    print(f"Rendered {KEA_OUTPUT_PATH} from {KEA_TEMPLATE_PATH}")
    print(f"Rendered {OSS_SEED_OUTPUT_PATH} from {OSS_SEED_TEMPLATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
