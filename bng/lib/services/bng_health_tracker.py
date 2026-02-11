import asyncio
import psutil

from lib.services.event_dispatcher import BNGEventDispatcher

class BNGHealthTracker:
    def __init__(self, bng_id: str, event_dispatcher: BNGEventDispatcher):
        self.bng_id = bng_id
        self.event_dispatcher = event_dispatcher

    async def check_health(self):
        loop = asyncio.get_running_loop()
        def _sync_check():
            cpu_usage = psutil.cpu_percent(interval=1)
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
