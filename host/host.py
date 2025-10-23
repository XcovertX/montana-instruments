import asyncio
import argparse
import random
import json
from pathlib import Path

class ClientState:
    def __init__(self):
        self.high_ack = -1
        self.node_id = None

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, args) -> None:
    peer = writer.get_extra_info("peername")
    state = ClientState()
    last_cfg_push = 0.0

    
async def main():
    parser = argparse.ArgumentParser(description="MI Diagnostics Host")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()
    print(f"Starting server on {args.bind}:{args.port}")

    server = await asyncio.start_server(lambda r, w: handle_client(r, w, args), host=args.bind, port=args.port)
    addr = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"[HOST] Listening on {addr}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())