import asyncio
import argparse
import json
import os
import time
import random
from pathlib import Path
from typing import Dict, Any
from common.utils import PERIOD_10hz_s, get_monotonic_ms, get_wall_ms
from node.anomaly import ZScore
from node.config import NodeConfig
from node.ring_buffer import RingBuffer
from node.wal import WAL

class Node:
    def __init__(self, node_id: str, host: str, port: int, workdir: Path, config: NodeConfig):
        self.node_id  = node_id
        self.host     = host
        self.port     = port
        self.workdir  = workdir
        self.seq      = 0
        self.config   = config
        self.buf      = RingBuffer(config.buffer_max)
        self.wal      = WAL(workdir / f"{node_id}.wal")
        self.z_temp   = ZScore()
        self.z_hum    = ZScore()
        self.z_vib    = ZScore()
        self.degraded = False

    async def make_sample(self) -> Dict[str, Any]:
        # Simple random walk signals
        temp = 25.0 + random.gauss(0, 0.1) + random.choice([0.0, 0.0, 0.5]) * (random.random() < 0.01)
        hum = 40.0 + random.gauss(0, 0.15)
        vib = 0.1 + abs(random.gauss(0, 0.02))
        self.z_temp.update(temp)
        self.z_hum.update(hum)
        self.z_vib.update(vib)
        z_any = max(abs(self.z_temp.z(temp)), abs(self.z_hum.z(hum)), abs(self.z_vib.z(vib)))
        anomaly = z_any > self.config.anomaly_z
        msg = {
            "type": "telemetry",
            "node_id": self.node_id,
            "ts_mono_ms": get_monotonic_ms(),
            "ts_wall_ms": get_wall_ms(),
            "seq": self.seq,
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

    node = Node(args.id, args.host, args.port, workdir, NodeConfig())

if __name__ == "__main__":
    asyncio.run(main())