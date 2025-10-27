
# MI Diagnostics Challenge
A distributed telemetry and diagnostics system with anomaly detection, replay/outage tolerance, and runtime configuration.

## Quick Start Instructions

1. **Install Python 3.10+** 
2. **Start the host server:**
	```sh
	python -m host.host --port 9000 --push-config-every-s 15 --ack-delay-ms 50 --faults --drop-prob 0.01
	```
3. **Start one or more nodes:**
	```sh
	python -m node.node --id N1 --host 127.0.0.1 --port 9000
	python -m node.node --id N2 --host 127.0.0.1 --port 9000 --workdir ./node2_data
	```
4. **Observe output:** Nodes will connect, send telemetry, and handle diagnostics and anomaly detection.

## What to Observe
- **Seq/ACK**: The host logs JSON Lines per node in `host/logs/N1.jsonl`. Sequence numbers increase monotonically.
- **Outage replay**: Stop the host; nodes buffer to a ring + WAL. Restart the host; nodes replay from last **ack** with no gaps.
- **Telemetry streaming:** Each node samples data at 10Hz, detects anomalies, and sends JSON telemetry to the host.
- **Config updates**: Every ~15s the host sends a `config_update` (e.g., change anomaly `anomaly_z`). Nodes apply and confirm with `config_applied`.
- **Anomaly detection:** Rolling z-score is used to flag outliers in temperature, humidity, and vibration.
- **Diagnostics**: Node includes a simple `diagnostics` block and toggles `degraded=true` when buffer nears capacity.

## Mapping to Requirements
- **Reliable timing & data integrity**: `seq`, `ts_mono_ms`, `ts_wall_ms` in `node/node.py`; host verifies monotonic `seq` by ACKing high-watermark.
- **Detect and log anomalies & diagnostics**: `node/anomaly.py`, `node/diagnostics.py`; host logs per-node JSONL.
- **Handle outages & replay**: `node/ring_buffer.py`, `node/wal.py`, reconnect logic in `node/node.py`.
- **Efficient memory**: Bounded ring buffer with backpressure flag `degraded` in `node/node.py`.
- **Config updates at runtime**: Host sends `config_update`; node applies and replies `config_applied`.
- **Runtime varying board count**: Host accepts multiple connections concurrently; run `N1`, `N2`, etc.
- **Safe startup/shutdown**: WAL ensures crash persistence; on reconnect, replay from `ack` and compact WAL.
- **Robust, secure firmware updates (design)**: See `DESIGN.md` for A/B partitions, signed images, secure boot, and rollback strategy.

## Testing
The system includes fault injection parameters to simulate realistic network conditions:
	```sh
	--faults --drop-prob 0.01 --ack-delay-ms 100
	```

## Notes
- **Subsystems:** See `DESIGN.md` for architecture details.
- **Extensibility:** The system is modular; add new metrics, diagnostics, or host features as needed.
- **Testing:** Fault injection and replay can be demonstrated by disconnecting nodes or using host options.
