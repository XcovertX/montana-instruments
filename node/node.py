import asyncio
import argparse
import json
import os
import time
import random
from pathlib import Path
from typing import Dict, Any

class Node:
    def __init__(self, node_id: str, host: str, port: int, workdir: Path):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.workdir = workdir

    def sample_loop(self):
        pass

async def main():
    parser = argparse.ArgumentParser(description="MI Diagnostics Node")
    parser.add_argument("--id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--workdir", default="./node_data")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    node = Node(args.id, args.host, args.port, workdir)

if __name__ == "__main__":
    asyncio.run(main())