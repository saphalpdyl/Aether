import psutil
import time

from lib.services.event_dispatcher import BNGEventDispatcher

class BNGHealthTracker:
    def __init__(self, bng_id: str, event_dispatcher: BNGEventDispatcher):
        self.bng_id = bng_id
        self.event_dispatcher = event_dispatcher

    def check_health(self):
        # Check CPU and memory usage
        cpu_usage = psutil.cpu_percent(interval=1)
        mem_max = psutil.virtual_memory().total / (1024 * 1024)
        mem_used = psutil.virtual_memory().used / (1024 * 1024)

        return cpu_usage, mem_used, mem_max


    def _dispatch(self, cpu_usage: float, mem_usage: float, mem_max: float):
        # Dispatch health status update
        self.event_dispatcher.dispatch_bng_health_update(
            cpu_usage=cpu_usage,
            mem_usage=mem_usage,
            mem_max=mem_max,
        )
    def check_and_dispatch(self):
        cpu_usage, mem_used, mem_max = self.check_health()
        self._dispatch(
            cpu_usage=cpu_usage,
            mem_usage=mem_used,
            mem_max=mem_max
        )
