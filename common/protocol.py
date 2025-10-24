import asyncio
import json
from typing import Any, Dict, Optional

async def send_json(writer: asyncio.StreamWriter, obj: Dict[str, Any]) -> None:
    data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    writer.write(data)
    await writer.drain()

async def read_json(reader: asyncio.StreamReader, *, limit: int = 1_000_000) -> Optional[Dict[str, Any]]:
    try:
        line = await reader.readline()
        if not line:
            return None
        if len(line) > limit:
            # Truncate to avoid memory abuse
            line = line[:limit]
        return json.loads(line.decode("utf-8").strip())
    except json.JSONDecodeError:
        return None