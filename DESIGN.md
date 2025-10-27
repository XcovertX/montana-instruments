# Design Overview

## Goals
Provide a small, reliable system for distributed telemetry with anomaly detection, diagnostics, runtime configuration, outage tolerance with replay, bounded memory, and safe start/stop. 

Keep mechanisms simple, testable and observable.

## Subsystems
### Host
- TCP server
- Periodic broadcast
- Fault injection for demonstrating replay

### Node
- Sample @10Hz -> Rolling z-score anomaly -> Diagnostics
- Serialize to JSON -> Ring buffer (RAM) + Write-Ahead Log (WAL, file)
- TX queue over TCP -> Host
- Config listener 

## Dataflow
Sensors -> Node Sampler -> Anomaly/Diag -> Ring+WAL -> TCP -> Host -> Log, ACK -> Node compact WAL

## Key Decisions & Trade-offs
- **Protocol:** newline-delimited JSON for readability/time-boxed challenge. Trade-off: verbosity; mitigated by line-by-line streaming.
- **Durability:** RAM ring buffer for speed; tiny WAL for crash/outage persistence. WAL compaction after ACK to bound disk.
- **Ordering & Integrity:** `seq` per node; host ACKs the highest contiguous `seq`. Records include both **monotonic** and **wall** timestamps.
- **Anomaly Detection:** Rolling z-score (Welford) per metric (O(1) update). Threshold `|z|>z_thresh` (default 3.0). Easy to tune via config.
- **Backpressure:** When ring approaches capacity, mark `degraded=true` and prioritize transmission. Future: dynamic downsampling.
- **Runtime Config:** `config_update` carries version; node applies atomically and replies `config_applied` with `cfg_version_applied`.

## Timing & Data Integrity

## Outage Tolerance / Replay

## Diagnostics

## Safe Startup & Shutdown

## Security & Firmware Updates

## Future Extensions