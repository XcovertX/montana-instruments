import asyncio
import argparse
import json
import os
import time
import random
from pathlib import Path
from typing import Dict, Any
from common.protocol import read_json, send_json
from common.utils import PERIOD_10hz_s, get_monotonic_ms, get_wall_ms
from node.anomaly import ZScore
from node.config import NodeConfig
from node.diagnostics import run_diagnostics
from node.ring_buffer import RingBuffer
from node.wal import WAL

class Node:
    def __init__(self, node_id: str, host: str, port: int, workdir: Path, cfg: NodeConfig):
        self.node_id    = node_id
        self.host       = host
        self.port       = port
        self.workdir    = workdir
        self.seq        = 0
        self.high_acked = -1
        self.config     = cfg
        self.buf        = RingBuffer(cfg.buffer_max)
        self.wal        = WAL(workdir / f"{node_id}.wal")
        self.z_temp     = ZScore()
        self.z_hum      = ZScore()
        self.z_vib      = ZScore()
        self.degraded   = False

    def make_sample(self) -> Dict[str, Any]:
        # Simple random walk signals
        temp = 25.0 + random.gauss(0, 0.1) + random.choice([0.0, 0.0, 0.5]) * (random.random() < 0.01)
        hum = 40.0 + random.gauss(0, 0.15)
        vib = 0.1 + abs(random.gauss(0, 0.02))
        self.z_temp.update(temp)
        self.z_hum.update(hum)
        self.z_vib.update(vib)
        z_any = max(abs(self.z_temp.z(temp)), abs(self.z_hum.z(hum)), abs(self.z_vib.z(vib)))
        anomaly = z_any > self.config.anomaly_z
        d = run_diagnostics()
        msg = {
            "type": "telemetry",
            "node_id": self.node_id,
            "ts_mono_ms": get_monotonic_ms(),
            "ts_wall_ms": get_wall_ms(),
            "seq": self.seq,
            "metrics": {
                "temp_c":  round(temp, 3),
                "hum_pct": round(hum, 3),
                "vib_g":   round(vib, 4)
                },
            "anomaly": anomaly,
            "diagnostics": d,
            "degraded": self.degraded,
        }
        return msg


    async def sample_loop(self):
        while True:
            start = time.perf_counter()
            msg = self.make_sample()
            self.buf.append(msg)
            self.wal.append(msg)
            self.seq += 1
            # backpressure: if buffer is near full, mark degraded
            self.degraded = len(self.buf) > int(self.config.buffer_max * 0.8)
            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(0.0, PERIOD_10hz_s - elapsed))

    async def tx_loop(self):
        backoff = 0.5  # Initial backoff for reconnect
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                print(f"[{self.node_id}] Connected to host {self.host}:{self.port}")
                # On connect, try to replay from WAL first
                for rec in self.wal.read_all():
                    if rec.get("seq", -1) > self.high_acked:
                        await send_json(writer, rec)
                        await self._drain_until_ack(reader, writer)

                # Normal streaming
                while True:
                    async for _ in self._send_buffered(writer, reader):
                        pass
                    await asyncio.sleep(0.001)
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
                print(f"[{self.node_id}] Connection lost; retrying...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5.0)

    async def _send_buffered(self, writer, reader):
        # Send any buffered frames with seq > high_acked
        for rec in self.buf.iter_from(0):
                if rec["seq"] > self.high_acked:
                    await send_json(writer, rec)
                    await self._drain_until_ack(reader, writer)
                    yield True                                  

    async def _drain_until_ack(self, reader, writer):
        # Drain messages from host until an ACK (also process config updates)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            reader._transport.set_read_buffer_limits(1<<20)
            try:
                reader._transport   # touch to ensure exists
            except Exception:
                return              # Exit if transport missing
            reader.at_eof()         # Check EOF
            reader_pending = reader._buffer if hasattr(reader, "_buffer") else b""  # Pending buffer
            # Non-blocking-ish wait
            try:  # Touch loop for pylint
                reader._loop  # touch to keep pylint quiet
            except Exception:  # Ignore errors
                pass  # No-op
            # Use wait_for with small timeout to avoid blocking
            try:  # Try to read JSON
                msg = await asyncio.wait_for(read_json(reader), timeout=0.05)  # Read message
            except asyncio.TimeoutError:  # Timeout
                return  # Exit on timeout
            if not msg:  # No message
                return  # Exit if no message
            if msg.get("type") == "ack":  # ACK message
                ack = int(msg.get("ack_seq", -1))  # ACK sequence
                if ack > self.high_acked:  # Update high_acked
                    self.high_acked = ack  # Set new high_acked
                    # Compact WAL to keep it small
                    self.wal.compact_up_to(self.high_acked)  # Compact WAL
                return  # Exit after ACK
            if msg.get("type") == "config_update":  # Config update message
                cfg = msg.get("config", {})  # New config
                if "anomaly_z" in cfg:  # Update anomaly threshold
                    self.config.anomaly_z = float(cfg["anomaly_z"])  # Set anomaly threshold
                if "window" in cfg:  # Window size update
                    # window not used directly here (Welford is unbounded), but we'd reset if it shrinks
                    pass  # No-op
                if "buffer_max" in cfg:  # Buffer size update
                    self.config.buffer_max = int(cfg["buffer_max"])  # Set buffer size
                # Send confirmation back
                await send_json(writer, {  # Send config applied message
                    "type": "config_applied",  # Message type
                    "node_id": self.node_id,  # Node identifier
                    "cfg_version_applied": msg.get("cfg_version", 0),  # Config version
                    "ts_wall_ms": int(time.time()*1000)  # Timestamp
                })  # End send config applied
                continue  # Continue waiting for ACK

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