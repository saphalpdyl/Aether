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

RADIUS_CLIENTS_TEMPLATE_PATH = ROOT / "docker/radius/raddb/clients.conf.j2"
RADIUS_CLIENTS_OUTPUT_PATH = ROOT / "docker/radius/raddb/clients.conf"

NGINX_CONF_TEMPLATE_PATH = ROOT / "docker/nginx/nginx.conf.j2"
NGINX_CONF_OUTPUT_PATH = ROOT / "docker/nginx/nginx.conf"


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
        "bng_id": bng_id,
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
        "uplink_ip": _cidr_ip(str(uplink_cidr)),
        "uplink_default_gw": str(uplink_gw),
        "bng_route_subnet": str(subnet),
        "bng_route_next_hop": str(bng_route_next_hop),
        "subnet_prefix": _cidr_prefix(str(subnet)),
    }


def _parse_shared_services(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten shared.services into a dict with Python-friendly keys and sensible defaults."""
    def _svc(name: str) -> dict:
        v = raw.get(name)
        return v if isinstance(v, dict) else {}

    kea         = _svc("kea")
    radius      = _svc("radius")
    radius_pg   = _svc("radius-pg")
    dhcp_pg     = _svc("dhcp-pg")
    redis       = _svc("redis")
    oss_pg      = _svc("oss-pg")
    bng_ingestor = _svc("bng-ingestor")
    frontend    = _svc("frontend")
    backend     = _svc("backend")
    simulator   = _svc("simulator")
    nginx       = _svc("nginx")

    return {
        "kea_ip":           str(kea.get("ip",           "198.18.0.3")),
        "kea_ctrl_port":    str(kea.get("ctrl-port",    "6772")),
        "radius_ip":        str(radius.get("ip",        "198.18.0.2")),
        "radius_pg_ip":     str(radius_pg.get("ip",     "198.18.0.6")),
        "dhcp_pg_ip":       str(dhcp_pg.get("ip",       "198.18.0.4")),
        "redis_ip":         str(redis.get("ip",         "198.18.0.10")),
        "oss_pg_ip":        str(oss_pg.get("ip",        "198.18.0.11")),
        "bng_ingestor_ip":  str(bng_ingestor.get("ip", "198.18.0.12")),
        "frontend_ip":      str(frontend.get("ip",      "198.18.0.20")),
        "backend_ip":       str(backend.get("ip",       "198.18.0.21")),
        "backend_port":     str(backend.get("port",     "8000")),
        "simulator_ip":     str(simulator.get("ip",     "198.18.0.22")),
        "simulator_port":   str(simulator.get("port",   "8000")),
        "nginx_ip":         str(nginx.get("ip",         "198.18.0.23")),
    }


def _normalize_bng(raw: dict[str, Any], idx: int, services_cfg: dict[str, Any]) -> dict[str, Any]:
    bng_id = _require(raw, "bng-id", f"bngs[{idx}]")
    if not isinstance(bng_id, str) or not bng_id.strip():
        raise ConfigError(f"bngs[{idx}].bng-id must be a non-empty string")

    topo = _require(raw, "topology", f"bngs[{idx}]")
    iface = _require(topo, "interfaces", f"bngs[{idx}].topology")
    ipv4 = _require(topo, "ipv4", f"bngs[{idx}].topology")

    for key in ["subscriber", "upstream", "dhcp-uplink"]:
        _require(iface, key, f"bngs[{idx}].topology.interfaces")

    for key in ["subscriber-cidr", "upstream-cidr", "dhcp-uplink-cidr", "default-gw", "nat-source-cidr"]:
        _require(ipv4, key, f"bngs[{idx}].topology.ipv4")

    # services section is optional — all fields derived from shared.services with optional overrides
    svc_overrides = topo.get("services") or {}
    if not isinstance(svc_overrides, dict):
        raise ConfigError(f"bngs[{idx}].topology.services must be a mapping when provided")
    nas_ip = svc_overrides.get("nas-ip") or _cidr_ip(str(ipv4["dhcp-uplink-cidr"]))
    services = {
        "nas-ip":           nas_ip,
        "dhcp-server-ip":   svc_overrides.get("dhcp-server-ip",  services_cfg["kea_ip"]),
        "radius-server-ip": svc_overrides.get("radius-server-ip", services_cfg["radius_ip"]),
        "redis-host":       svc_overrides.get("redis-host",       services_cfg["redis_ip"]),
        "oss-api-url":      svc_overrides.get("oss-api-url",
                                f"http://{services_cfg['backend_ip']}:{services_cfg['backend_port']}"),
        "kea-ctrl-url":     svc_overrides.get("kea-ctrl-url",
                                f"http://{services_cfg['kea_ip']}:{services_cfg['kea_ctrl_port']}"),
        "radius-client-secret": svc_overrides.get("radius-client-secret", "testing123"),
    }

    access_nodes_raw = _require(raw, "access-nodes", f"bngs[{idx}]")
    if not isinstance(access_nodes_raw, list) or not access_nodes_raw:
        raise ConfigError(f"bngs[{idx}].access-nodes must be a non-empty list")
    access_nodes = [_normalize_access_node(item, bng_id, i) for i, item in enumerate(access_nodes_raw, start=1)]

    env_overrides = raw.get("environment") or {}
    if not isinstance(env_overrides, dict):
        raise ConfigError(f"bngs[{idx}].environment must be a mapping when provided")

    return {
        "bng_id": bng_id,
        "bng_node_name": bng_id,
        "subscriber_iface": str(iface["subscriber"]),
        "upstream_iface": str(iface["upstream"]),
        "dhcp_uplink_iface": str(iface["dhcp-uplink"]),
        "subscriber_cidr": str(ipv4["subscriber-cidr"]),
        "upstream_cidr": str(ipv4["upstream-cidr"]),
        "upstream_ip": _cidr_ip(str(ipv4["upstream-cidr"])),
        "dhcp_uplink_cidr": str(ipv4["dhcp-uplink-cidr"]),
        "default_gw": str(ipv4["default-gw"]),
        "nat_source_cidr": str(ipv4["nat-source-cidr"]),
        "services": {str(k): str(v) for k, v in services.items()},
        "environment": {str(k): str(v) for k, v in env_overrides.items()},
        "access_nodes": access_nodes,
    }


def load_and_validate_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("Top-level config must be a mapping")

    shared_raw = raw.get("shared") or {}
    if not isinstance(shared_raw, dict):
        raise ConfigError("config.shared must be a mapping when provided")

    upstream_shared = shared_raw.get("upstream") or {}
    if not isinstance(upstream_shared, dict):
        raise ConfigError("config.shared.upstream must be a mapping when provided")
    mgmt_shared = shared_raw.get("mgmt") or {}
    if not isinstance(mgmt_shared, dict):
        raise ConfigError("config.shared.mgmt must be a mapping when provided")

    upstream_cfg = {
        "wan-node-name": str(upstream_shared.get("wan-node-name", "wan")),
        "upstream-node-name": str(upstream_shared.get("upstream-node-name", "upstream")),
        "internet-iface": str(upstream_shared.get("internet-iface", "eth11")),
        "internet-macvlan-parent": str(upstream_shared.get("internet-macvlan-parent", "enp1s0")),
        "mgmt-ip-cidr": str(upstream_shared.get("mgmt-ip-cidr", "198.18.0.254/24")),
        "mgmt-nat-source-cidr": str(upstream_shared.get("mgmt-nat-source-cidr", "198.18.0.0/24")),
    }

    services_raw = shared_raw.get("services") or {}
    if not isinstance(services_raw, dict):
        raise ConfigError("config.shared.services must be a mapping when provided")
    services_cfg = _parse_shared_services(services_raw)

    mgmt_cfg = {
        "node-name": str(mgmt_shared.get("node-name", "mgmt")),
        "static-endpoints": mgmt_shared.get(
            "static-endpoints",
            [
                "upstream:eth2",
                "kea:eth1",
                "radius:eth1",
                "radius_pg:eth1",
                "dhcp_pg:eth1",
                "redis:eth1",
                "oss_pg:eth1",
                "bng_ingestor:eth1",
                "frontend:eth1",
                "backend:eth1",
            ],
        ),
    }
    if not isinstance(mgmt_cfg["static-endpoints"], list) or not all(
        isinstance(x, str) and ":" in x for x in mgmt_cfg["static-endpoints"]
    ):
        raise ConfigError("config.shared.mgmt.static-endpoints must be a list of '<node>:<iface>' strings")

    bngs_raw = _require(raw, "bngs", "config")
    if not isinstance(bngs_raw, list) or not bngs_raw:
        raise ConfigError("config.bngs must be a non-empty list")

    bngs = [_normalize_bng(item, i, services_cfg) for i, item in enumerate(bngs_raw)]

    seen_bng: set[str] = set()
    seen_remote: set[str] = set()
    seen_container: set[str] = set()
    seen_subnets: set[str] = set()

    for bng in bngs:
        if bng["bng_id"] in seen_bng:
            raise ConfigError(f"Duplicate bng-id: {bng['bng_id']}")
        seen_bng.add(bng["bng_id"])

        for node in bng["access_nodes"]:
            if node["remote_id"] in seen_remote:
                raise ConfigError(f"Duplicate remote-id across all BNGs: {node['remote_id']}")
            if node["container_name"] in seen_container:
                raise ConfigError(f"Duplicate access node container-name: {node['container_name']}")
            if node["dhcp_subnet"] in seen_subnets:
                raise ConfigError(f"Duplicate DHCP subnet across access nodes: {node['dhcp_subnet']}")
            seen_remote.add(node["remote_id"])
            seen_container.add(node["container_name"])
            seen_subnets.add(node["dhcp_subnet"])

    # Shared upstream eth1 model: all BNG upstream IPs must be on the same network + gateway.
    first_up = ipaddress.ip_interface(bngs[0]["upstream_cidr"])
    first_net = first_up.network
    first_gw = bngs[0]["default_gw"]
    for bng in bngs[1:]:
        up = ipaddress.ip_interface(bng["upstream_cidr"])
        if up.network != first_net:
            raise ConfigError(
                f"All BNG upstream-cidr must be in same network (shared upstream:eth1). "
                f"'{bng['bng_id']}' has {up.network}, expected {first_net}"
            )
        if bng["default_gw"] != first_gw:
            raise ConfigError(
                f"All BNG default-gw must match shared upstream gateway ({first_gw}); "
                f"'{bng['bng_id']}' has {bng['default_gw']}"
            )

    return {
        "bngs": bngs,
        "upstream_network": str(first_net),
        "upstream_default_gw": first_gw,
        "upstream_prefix": first_net.prefixlen,
        "shared": {
            "upstream": upstream_cfg,
            "mgmt": mgmt_cfg,
            "services": services_cfg,
        },
    }


def build_render_context(cfg: dict[str, Any]) -> dict[str, Any]:
    shared_upstream = cfg["shared"]["upstream"]
    shared_mgmt = cfg["shared"]["mgmt"]
    host_nodes: list[dict[str, str]] = []
    access_nodes: list[dict[str, Any]] = []
    agg_nodes: list[dict[str, str]] = []
    bng_nodes: list[dict[str, Any]] = []

    links: list[dict[str, str]] = []

    all_access_nodes: list[dict[str, Any]] = []
    radius_clients: list[dict[str, str]] = []
    radius_clients_by_ip: dict[str, dict[str, str]] = {}

    mgmt_links: list[str] = []

    for bng_idx, bng in enumerate(cfg["bngs"], start=1):
        agg_name = f"agg-{bng['bng_id']}"
        agg_nodes.append({"name": agg_name})

        # Access nodes + auto-hosts + links
        for access_idx, node in enumerate(bng["access_nodes"], start=1):
            node_ctx = dict(node)
            node_ctx["agg_name"] = agg_name
            node_ctx["agg_iface"] = f"eth{access_idx}"
            node_ctx["wait_clause"] = " && ".join(
                f"ip link show eth{i} >/dev/null 2>&1" for i in range(1, node["iface_count"] + 1)
            )
            node_ctx["up_clause"] = " && ".join(f"ip link set eth{i} up" for i in range(1, node["iface_count"] + 1))
            node_ctx["bridge_attach_clause"] = " && ".join(
                f"ip link set {iface} master br0" for iface in node["subscriber_ifaces"]
            )
            node_ctx["circuit_id_map"] = ",".join(
                f"{iface}=1/0/{_parse_iface_index(iface, node['remote_id'])}" for iface in node["subscriber_ifaces"]
            )
            access_nodes.append(node_ctx)
            all_access_nodes.append(node_ctx)

            links.append({
                "a": f"{node['container_name']}:{node['uplink_iface']}",
                "b": f"{agg_name}:{node_ctx['agg_iface']}",
            })

            for iface in node["subscriber_ifaces"]:
                host_name = f"h-{node['remote_id']}-{iface}"
                host_nodes.append(
                    {
                        "name": host_name,
                        "mac": _deterministic_mac(f"{bng['bng_id']}/{node['remote_id']}/{iface}"),
                    }
                )
                links.append({"a": f"{host_name}:eth1", "b": f"{node['container_name']}:{iface}"})

        # BNG env and exec
        bng_env: dict[str, str] = {
            "BNG_IDENTIFIER": bng["bng_id"],
            "BNG_SUBSCRIBER_IFACE": bng["subscriber_iface"],
            "BNG_UPLINK_IFACE": bng["upstream_iface"],
            "BNG_DHCP_UPLINK_IFACE": bng["dhcp_uplink_iface"],
            "BNG_SUBSCRIBER_IP_CIDR": bng["subscriber_cidr"],
            "BNG_UPLINK_IP_CIDR": bng["upstream_cidr"],
            "BNG_DHCP_UPLINK_IP_CIDR": bng["dhcp_uplink_cidr"],
            "BNG_DEFAULT_GW": bng["default_gw"],
            "BNG_NAT_SOURCE_CIDR": bng["nat_source_cidr"],
            "BNG_DHCP_SERVER_IP": bng["services"]["dhcp-server-ip"],
            "BNG_RADIUS_SERVER_IP": bng["services"]["radius-server-ip"],
            "BNG_NAS_IP": bng["services"]["nas-ip"],
            "BNG_REDIS_HOST": bng["services"]["redis-host"],
            "BNG_OSS_API_URL": bng["services"]["oss-api-url"],
            "BNG_KEA_CTRL_URL": bng["services"]["kea-ctrl-url"],
        }
        for i, node in enumerate(bng["access_nodes"], start=1):
            bng_env[f"BNG_RELAY{i}_SUBNET_CIDR"] = node["bng_route_subnet"]
            bng_env[f"BNG_RELAY{i}_NEXT_HOP"] = node["bng_route_next_hop"]
        bng_env.update(bng["environment"])

        bng_exec = [
            (
                f"sh -c \"for i in $(seq 1 50); do ip link show {bng['subscriber_iface']} >/dev/null 2>&1 && "
                f"ip link show {bng['upstream_iface']} >/dev/null 2>&1 && "
                f"ip link show {bng['dhcp_uplink_iface']} >/dev/null 2>&1 && break; sleep 0.2; done; "
                "PYTHONUNBUFFERED=1 python3 -u /opt/bng/bng_main.py --bng-id $BNG_IDENTIFIER "
                ">>/proc/1/fd/1 2>>/proc/1/fd/2 &\""
            ),
            "sh -c \"coad >/proc/1/fd/1 2>/proc/1/fd/2 &\"",
            "sh -c \"iperf3 -s -D\"",
            "sh -c \"ip link set eth0 down || true\"",
            f"tc qdisc add dev {bng['subscriber_iface']} root handle 1: htb r2q 100 default 9999",
            f"tc class add dev {bng['subscriber_iface']} parent 1: classid 1:1 htb rate 1gbit",
            f"tc class add dev {bng['subscriber_iface']} parent 1:1 classid 1:9999 htb rate 1gbit",
            f"tc qdisc add dev {bng['upstream_iface']} root handle 1: htb r2q 100 default 9999",
            f"tc class add dev {bng['upstream_iface']} parent 1: classid 1:1 htb rate 1gbit",
            f"tc class add dev {bng['upstream_iface']} parent 1:1 classid 1:9999 htb rate 1gbit",
        ]

        bng_nodes.append({"name": bng["bng_node_name"], "env": bng_env, "exec": bng_exec})

        nas_ip = bng["services"]["nas-ip"]
        secret = bng["services"].get("radius-client-secret", "testing123")
        existing = radius_clients_by_ip.get(nas_ip)
        if existing and existing["secret"] != secret:
            raise ConfigError(
                f"Conflicting RADIUS client secret for NAS IP {nas_ip}: "
                f"{existing['bng_id']} vs {bng['bng_id']}"
            )
        if not existing:
            entry = {"bng_id": bng["bng_id"], "ipaddr": nas_ip, "secret": secret}
            radius_clients_by_ip[nas_ip] = entry
            radius_clients.append(entry)

        # agg -> bng subscriber side link
        links.append(
            {
                "a": f"{agg_name}:eth{len(bng['access_nodes']) + 1}",
                "b": f"{bng['bng_node_name']}:{bng['subscriber_iface']}",
            }
        )

        # bng -> wan shared upstream link
        links.append(
            {
                "a": f"{bng['bng_node_name']}:{bng['upstream_iface']}",
                "b": f"{shared_upstream['wan-node-name']}:eth{bng_idx}",
            }
        )

        # bng -> mgmt link
        mgmt_links.append(f"{bng['bng_node_name']}:{bng['dhcp_uplink_iface']}")

    # wan -> upstream link on next port after all bngs
    links.append(
        {
            "a": f"{shared_upstream['wan-node-name']}:eth{len(cfg['bngs']) + 1}",
            "b": f"{shared_upstream['upstream-node-name']}:eth1",
        }
    )

    # mgmt links with dynamic ports
    mgmt_port = 1
    for endpoint in mgmt_links:
        links.append({"a": endpoint, "b": f"{shared_mgmt['node-name']}:eth{mgmt_port}"})
        mgmt_port += 1

    for endpoint in shared_mgmt["static-endpoints"]:
        links.append({"a": endpoint, "b": f"{shared_mgmt['node-name']}:eth{mgmt_port}"})
        mgmt_port += 1

    # upstream internet macvlan
    links.append(
        {
            "a": f"{shared_upstream['upstream-node-name']}:{shared_upstream['internet-iface']}",
            "b": f"macvlan:{shared_upstream['internet-macvlan-parent']}",
        }
    )

    mgmt_ip_cidr = cfg["shared"]["upstream"]["mgmt-ip-cidr"]
    return {
        "bngs": cfg["bngs"],
        "host_nodes": host_nodes,
        "access_nodes": access_nodes,
        "agg_nodes": agg_nodes,
        "bng_nodes": bng_nodes,
        "links": links,
        "mgmt_port_count": mgmt_port,
        "all_access_nodes": all_access_nodes,
        "radius_clients": radius_clients,
        "shared": cfg["shared"],
        "upstream_default_gw": cfg["upstream_default_gw"],
        "upstream_prefix": cfg["upstream_prefix"],
        "services": cfg["shared"]["services"],
        "mgmt_gw": _cidr_ip(mgmt_ip_cidr),
        "mgmt_prefix": _cidr_prefix(mgmt_ip_cidr),
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
    render_to_file(RADIUS_CLIENTS_TEMPLATE_PATH, RADIUS_CLIENTS_OUTPUT_PATH, ctx, env)
    render_to_file(NGINX_CONF_TEMPLATE_PATH, NGINX_CONF_OUTPUT_PATH, ctx, env)



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

    for path in [TOPOLOGY_TEMPLATE_PATH, KEA_TEMPLATE_PATH, OSS_SEED_TEMPLATE_PATH, RADIUS_CLIENTS_TEMPLATE_PATH, NGINX_CONF_TEMPLATE_PATH]:
        if not path.exists():
            print(f"Config error: template file not found: {path}")
            return 1

    generate(cfg)
    print(f"Rendered {TOPOLOGY_OUTPUT_PATH} from {TOPOLOGY_TEMPLATE_PATH}")
    print(f"Rendered {KEA_OUTPUT_PATH} from {KEA_TEMPLATE_PATH}")
    print(f"Rendered {OSS_SEED_OUTPUT_PATH} from {OSS_SEED_TEMPLATE_PATH}")
    print(f"Rendered {RADIUS_CLIENTS_OUTPUT_PATH} from {RADIUS_CLIENTS_TEMPLATE_PATH}")
    print(f"Rendered {NGINX_CONF_OUTPUT_PATH} from {NGINX_CONF_TEMPLATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
