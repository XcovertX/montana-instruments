import asyncio
import argparse
import json
import os
import time
import random
from pathlib import Path
from typing import Dict, Any
from util import get_monotonic_ms, get_wall_ms

PERIOD_10hz_s = 0.1



class Node:
    def __init__(self, node_id: str, host: str, port: int, workdir: Path):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.workdir = workdir

    async def make_sample(self) -> Dict[str, Any]:
        # Simple random walk signals
        temp = 25.0 + random.gauss(0, 0.1) + random.choice([0.0, 0.0, 0.5]) * (random.random() < 0.01)
        hum = 40.0 + random.gauss(0, 0.15)
        vib = 0.1 + abs(random.gauss(0, 0.02))
        msg = {
            "type": "telemetry",
            "node_id": self.node_id,
            "ts_mono_ms": get_monotonic_ms(),
            "ts_wall_ms": get_wall_ms(),
            "metrics": {"temp_c": round(temp, 3), "hum_pct": round(hum, 3), "vib_g": round(vib, 4)},
        }
        return msg


    async def sample_loop(self):
        while True:
            start = time.perf_counter()
            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(0.0, PERIOD_10hz_s - elapsed))

    def tx_loop(self):
        pass

    def rx_loop(self):
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