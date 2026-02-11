import asyncio
import json
from typing import Any


async def handle_coad_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    command_queue: asyncio.Queue[tuple[str, dict[str, Any]]],
) -> None:
    """Bridge CoA IPC requests into the single-writer command queue."""
    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=3.0)
        if not data:
            writer.close()
            await writer.wait_closed()
            return

        request = json.loads(data.decode())
        loop = asyncio.get_running_loop()
        response_future: asyncio.Future[dict[str, Any]] = loop.create_future()
        await command_queue.put(("coad_request", {"request": request, "response_future": response_future}))
        response = await asyncio.wait_for(response_future, timeout=5.0)

        writer.write(json.dumps(response).encode())
        await writer.drain()
    except Exception as e:
        try:
            writer.write(json.dumps({"success": False, "error": str(e)}).encode())
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()
        await writer.wait_closed()
