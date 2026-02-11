"""
Compatibility entrypoint for the BNG runtime.

The implementation is split across focused modules:
- bng_loop.py: runtime orchestration and single-writer command loop
- bng_dhcp.py: DHCP event handling and lease reconciliation
- bng_session.py: session/radius/nftables primitives
- bng_coad.py: CoA IPC bridge
"""

from lib.services.bng_loop import bng_event_loop

__all__ = ["bng_event_loop"]
