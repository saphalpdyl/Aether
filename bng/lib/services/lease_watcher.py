import time
import os 
import threading
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileSystemEvent

from lib.constants import DHCP_LEASE_FILE_PATH

class LeaseObserver(FileSystemEventHandler):
    def __init__(self, on_change: Callable) -> None:
        self.on_change = on_change
        self._timer = None

    def _trigger(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(1.0, self.on_change)
        self._timer.start()

    def on_created(self, event: FileSystemEvent) -> None:
        if event.src_path == DHCP_LEASE_FILE_PATH:
            self._trigger()

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.src_path == DHCP_LEASE_FILE_PATH:
            self._trigger()

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.dest_path == DHCP_LEASE_FILE_PATH:
            self._trigger()
