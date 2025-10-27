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
        self.node_id    = node_id                         # Node identifier
        self.host       = host                            # Host address
        self.port       = port                            # Host port
        self.workdir    = workdir                         # Working directory
        self.seq        = 0                               # Sequence number for messages
        self.high_acked = -1                              # Highest acknowledged sequence
        self.config     = cfg                             # Node configuration
        self.buf        = RingBuffer(cfg.buffer_max)      # Telemetry buffer
        self.wal        = WAL(workdir / f"{node_id}.wal") # Write-ahead log file
        self.z_temp     = ZScore()                        # Z-score for temperature
        self.z_hum      = ZScore()                        # Z-score for humidity
        self.z_vib      = ZScore()                        # Z-score for vibration
        self.degraded   = False                           # Degraded state flag

    def make_sample(self) -> Dict[str, Any]:
        # Simple random walk signals
        temp = 25.0 + random.gauss(0, 0.1) + random.choice([0.0, 0.0, 0.5]) * (random.random() < 0.01)   # Simulate temperature
        hum = 40.0 + random.gauss(0, 0.15)                                 # Simulate humidity
        vib = 0.1 + abs(random.gauss(0, 0.02))                             # Simulate vibration
        self.z_temp.update(temp)                                           # Update temperature anomaly
        self.z_hum.update(hum)                                             # Update humidity anomaly
        self.z_vib.update(vib)                                             # Update vibration anomaly
        z_any = max(abs(self.z_temp.z(temp)), abs(self.z_hum.z(hum)), abs(self.z_vib.z(vib)))  # Max anomaly score
        anomaly = z_any > self.config.anomaly_z                            # Anomaly detected?
        d = run_diagnostics()                                              # Run diagnostics
        msg = {                                                            # Telemetry message
            "type": "telemetry",                                           # Message type
            "node_id": self.node_id,                                       # Node identifier
            "ts_mono_ms": get_monotonic_ms(),                              # Monotonic timestamp
            "ts_wall_ms": get_wall_ms(),                                   # Wall timestamp
            "seq": self.seq,                                               # Sequence number
            "metrics": {
                "temp_c":  round(temp, 3),                                 # Temperature
                "hum_pct": round(hum, 3),                                  # Humidity
                "vib_g":   round(vib, 4)                                   # Vibration
                },
            "anomaly": anomaly,                                            # Anomaly flag
            "diagnostics": d,                                              # Diagnostics result
            "degraded": self.degraded,                                     # Degraded state
        }
        return msg                                                         # Return telemetry message


    async def sample_loop(self):
        while True:                                                        # Main sample loop
            start = time.perf_counter()                                    # Start timer
            msg = self.make_sample()                                       # Create sample
            self.buf.append(msg)                                           # Add to buffer
            self.wal.append(msg)                                           # Add to WAL
            self.seq += 1                                                  # Increment sequence
            # backpressure: if buffer is near full, mark degraded
            self.degraded = len(self.buf) > int(self.config.buffer_max * 0.8)  # Mark degraded if buffer is near full
            elapsed = time.perf_counter() - start                          # Time taken
            await asyncio.sleep(max(0.0, PERIOD_10hz_s - elapsed))         # Sleep for remainder of period

    async def tx_loop(self):
        backoff = 0.5                                                      # Initial backoff for reconnect
        while True:                                                        # Main transmit loop
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)  # Open connection
                print(f"[{self.node_id}] Connected to host {self.host}:{self.port}") # Log connection
                # On connect, try to replay from WAL first
                for rec in self.wal.read_all():                            # Replay WAL records
                    if rec.get("seq", -1) > self.high_acked:               # Only send unacknowledged
                        await send_json(writer, rec)                       # Send record
                        await self._drain_until_ack(reader, writer)        # Wait for ACK

                # Normal streaming
                while True:                                                # Streaming loop
                    async for _ in self._send_buffered(writer, reader):    # Send buffered records
                        pass                                               # No-op, just yield
                    await asyncio.sleep(0.001)                             # Small sleep to avoid busy loop
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError):# Handle connection errors
                print(f"[{self.node_id}] Connection lost; retrying...")    # Log retry
                await asyncio.sleep(backoff)                               # Wait before retry
                backoff = min(backoff * 2, 5.0)                            # Exponential backoff

    async def _send_buffered(self, writer, reader):
        # Send any buffered frames with seq > high_acked
        for rec in self.buf.iter_from(0):                                  # Iterate buffer
            if rec["seq"] > self.high_acked:                               # Only send new records
                await send_json(writer, rec)                               # Send record
                await self._drain_until_ack(reader, writer)                # Wait for ACK
                yield True                                                 # Indicate sent

    async def _drain_until_ack(self, reader, writer):
        # Drain messages from host until an ACK (also process config updates)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            try:
                reader._transport                                       # touch to ensure exists
            except Exception:
                return                                                  # Exit if transport missing
            reader.at_eof()                                             # Check EOF
            reader_pending = reader._buffer if hasattr(reader, "_buffer") else b""  # Pending buffer
            # Non-blocking-ish wait
            try:                                                        # Touch loop for pylint
                reader._loop                                            # touch to keep pylint quiet
            except Exception:                                           # Ignore errors
                pass
            # Use wait_for with small timeout to avoid blocking
            try:                                                        # Try to read JSON
                msg = await asyncio.wait_for(read_json(reader), timeout=0.05)
            except asyncio.TimeoutError:
                return                                                  # Exit on timeout
            if not msg:
                return                                                  # Exit if no message
            if msg.get("type") == "ack": 
                ack = int(msg.get("ack_seq", -1))                       # ACK sequence
                if ack > self.high_acked:                               # Update high_acked
                    self.high_acked = ack                               # Set new high_acked
                    # Compact WAL to keep it small
                    self.wal.compact_up_to(self.high_acked)
                return                                                  # Exit after ACK
            if msg.get("type") == "config_update":                      # Config update message
                cfg = msg.get("config", {})                             # New config
                if "anomaly_z" in cfg:                                  # Update anomaly threshold
                    self.config.anomaly_z = float(cfg["anomaly_z"])     # Set anomaly threshold
                if "window" in cfg:                                     # Window size update
                    pass
                if "buffer_max" in cfg:                                 # Buffer size update
                    self.config.buffer_max = int(cfg["buffer_max"])     # Set buffer size
                # Send confirmation back
                await send_json(writer, {                               # Send config applied message
                    "type": "config_applied",                           # Message type
                    "node_id": self.node_id,                            # Node identifier
                    "cfg_version_applied": msg.get("cfg_version", 0),   # Config version
                    "ts_wall_ms": int(time.time()*1000)                 # Timestamp
                })                                                      # End send config applied
                continue                                                # Continue waiting for ACK

async def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="MI Diagnostics Node")
    parser.add_argument("--id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--workdir", default="./node_data")
    args = parser.parse_args()

    # Ensure workdir exists
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    # Create and run node
    node = Node(args.id, args.host, args.port, workdir, NodeConfig())
    # Start tasks
    tasks = [
        asyncio.create_task(node.sample_loop()),
        asyncio.create_task(node.tx_loop()),
    ]
    try:
        await asyncio.gather(*tasks) # Run tasks concurrently
    except asyncio.CancelledError:
        pass
if __name__ == "__main__":
    asyncio.run(main())