import asyncio
import os
import psutil

from lib.services.event_dispatcher import BNGEventDispatcher

def _read_cgroup_memory():
    """Read memory usage and limit from cgroup files (v2 then v1 fallback)."""
    # cgroup v2
    cg2_max = "/sys/fs/cgroup/memory.max"
    cg2_cur = "/sys/fs/cgroup/memory.current"
    if os.path.exists(cg2_cur) and os.path.exists(cg2_max):
        mem_used = int(open(cg2_cur).read().strip()) / (1024 * 1024)
        raw_max = open(cg2_max).read().strip()
        if raw_max == "max":
            return None  # no limit set, fall back to psutil
        mem_max = int(raw_max) / (1024 * 1024)
        return mem_used, mem_max

    # cgroup v1
    cg1_limit = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
    cg1_usage = "/sys/fs/cgroup/memory/memory.usage_in_bytes"
    if os.path.exists(cg1_usage) and os.path.exists(cg1_limit):
        mem_used = int(open(cg1_usage).read().strip()) / (1024 * 1024)
        mem_max = int(open(cg1_limit).read().strip()) / (1024 * 1024)
        return mem_used, mem_max

    return None

class BNGHealthTracker:
    def __init__(self, bng_id: str, event_dispatcher: BNGEventDispatcher):
        self.bng_id = bng_id
        self.event_dispatcher = event_dispatcher

    async def check_health(self):
        loop = asyncio.get_running_loop()
        def _sync_check():
            cpu_usage = psutil.cpu_percent(interval=1)
            cgroup_mem = _read_cgroup_memory()
            if cgroup_mem is not None:
                mem_used, mem_max = cgroup_mem
            else:
                mem_max = psutil.virtual_memory().total / (1024 * 1024)
                mem_used = psutil.virtual_memory().used / (1024 * 1024)
            return cpu_usage, mem_used, mem_max
        return await loop.run_in_executor(None, _sync_check)

    async def _dispatch(self, cpu_usage: float, mem_usage: float, mem_max: float):
        await self.event_dispatcher.dispatch_bng_health_update(
            cpu_usage=cpu_usage,
            mem_usage=mem_usage,
            mem_max=mem_max,
        )

    async def check_and_dispatch(self):
        cpu_usage, mem_used, mem_max = await self.check_health()
        await self._dispatch(
            cpu_usage=cpu_usage,
            mem_usage=mem_used,
            mem_max=mem_max
        )
