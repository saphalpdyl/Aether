from typing import Tuple
from dataclasses import dataclass
import asyncio

@dataclass
class BNGTrafficShaperConfig:
    bandwidth_limit: int # kbit
    bng_id: str
    bng_instance_id: str
    subscriber_facing_interface: str
    uplink_interface: str
    debug_mode: bool = False

class BNGTrafficShaper:
    def __init__(self, config: BNGTrafficShaperConfig):
        self.config = config

    def _generate_handle_with_ip(self, ip: str) -> Tuple[bool, int, str]:
        # a.b.c.d, handle = c * 256 + d
        octets = ip.split('.')
        if len(octets) != 4:
            return False, -1, "invalid IP address format"

        try:
            c = int(octets[2])
            d = int(octets[3])

            handle = int(c) * 256 + int(d)

            return True, handle, ""
        except Exception as e:
            return False, -1, f"error parsing IP address: {str(e)}"

    async def _cmd(self, cmd: str) -> str | None:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode() if stdout else None

        if self.config.debug_mode:
            print(f"Executed command: {cmd}")
            if output:
                print(f"Command output: {output}")

        return output

    async def add_traffic_shaping_rule(
            self,
            *,
            ip: str,
            upload_speed_kbit: int, # Egress for uplink interface | Shaping
            download_speed_kbit: int, # Egress for subscriber interface | Shaping
            download_burst_kbit: int, # Burst size for shaping (optional)
            upload_burst_kbit: int, # Burst size for shaping (optional)
    ) -> bool:
        success, handle, error = self._generate_handle_with_ip(ip)
        if not success:
            print(f"Error generating handle for IP {ip}: {error}")
            return False

        if self.config.debug_mode:
            print(f"Adding traffic shaping rule for IP {ip} with handle {handle}")

        handle = str(handle)
        download_iface = self.config.subscriber_facing_interface
        upload_iface = self.config.uplink_interface
        # Keep burst values practical and avoid invalid zero/negative values.
        download_burst_kbit = max(1, int(download_burst_kbit))
        upload_burst_kbit = max(1, int(upload_burst_kbit))

        # For egress on subscriber interface (download shaping)
        await self._cmd(
            f"tc class replace dev {download_iface} parent 1:1 classid 1:{handle} "
            f"htb rate {download_speed_kbit}kbit ceil {download_speed_kbit}kbit "
            f"burst {download_burst_kbit}kbit cburst {download_burst_kbit}kbit"
        )
        await self._cmd(
            f"tc qdisc replace dev {download_iface} parent 1:{handle} handle {handle}: sfq perturb 10"
        )
        await self._cmd(
            f"tc filter replace dev {download_iface} parent 1: protocol ip pref {handle} "
            f"u32 match ip dst {ip}/32 flowid 1:{handle}"
        )

        # For egress on uplink interface (upload shaping)
        await self._cmd(
            f"tc class replace dev {upload_iface} parent 1:1 classid 1:{handle} "
            f"htb rate {upload_speed_kbit}kbit ceil {upload_speed_kbit}kbit "
            f"burst {upload_burst_kbit}kbit cburst {upload_burst_kbit}kbit"
        )
        await self._cmd(
            f"tc qdisc replace dev {upload_iface} parent 1:{handle} handle {handle}: sfq perturb 10"
        )
        await self._cmd(
            f"tc filter replace dev {upload_iface} parent 1: protocol ip pref {handle} "
            f"u32 match ip src {ip}/32 flowid 1:{handle}"
        )

        return True

    async def remove_traffic_shaping_rule(self, *, ip: str) -> bool:
        success, handle, error = self._generate_handle_with_ip(ip)
        if not success:
            print(f"Error generating handle for IP {ip}: {error}")
            return False

        handle = str(handle)
        download_iface = self.config.subscriber_facing_interface
        upload_iface = self.config.uplink_interface

        # Delete filters first, then child qdisc and class (both interfaces).
        await self._cmd(
            f"tc filter del dev {download_iface} parent 1: protocol ip pref {handle} || true"
        )
        await self._cmd(
            f"tc filter del dev {upload_iface} parent 1: protocol ip pref {handle} || true"
        )
        await self._cmd(
            f"tc qdisc del dev {download_iface} parent 1:{handle} handle {handle}: || true"
        )
        await self._cmd(
            f"tc qdisc del dev {upload_iface} parent 1:{handle} handle {handle}: || true"
        )
        await self._cmd(f"tc class del dev {download_iface} classid 1:{handle} || true")
        await self._cmd(f"tc class del dev {upload_iface} classid 1:{handle} || true")

        return True
