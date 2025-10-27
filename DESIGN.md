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
- Uniqueness & order via `seq`.
- `ts_mono_ms` for ordering within a node even if wall clock jumps.
- Optional CRC/hash can be added per record; omitted for brevity in prototype.

## Outage Tolerance / Replay
- On disconnect, node continues sampling to ring + WAL.
- On reconnect, node replays any WAL records with `seq > high_acked`.
- After ACK, WAL compacts to bound disk usage.

## Diagnostics
- Simple placeholder checks (`rail_low` simulation). Structured `diagnostics` block included per record to make logs actionable.

## Safe Startup & Shutdown
- At startup, node replays any WAL content to restore state.
- Sampling and transmission loops are independent; reconnection uses exponential backoff.
- Final heartbeat could be emitted on SIGTERM (future enhancement).

## Potential Security & Firmware Updates
- **A/B Partitions + Atomic Switch:** New firmware staged to inactive slot; bootloader flips only after signature + version check.
- **Signed Images & Secure Boot:** ECC/Ed25519 signatures; boot ROM/secure boot verifies before execute.
- **Anti-rollback:** Monotonic version counter in secure storage. Reject images with lower version.
- **Health Checks & Rollback:** Post-boot watchdog; on failure, revert to previous slot.
- **Transport Security:** mTLS for node↔host; image fetched over TLS with pinning. (Not implemented in prototype for time.)

## Potential Future Extensions
- Switch to length-prefixed binary frames and **TLS/mTLS**.
- Prometheus exporter on host; Grafana dashboards.
- On-node health LED & local metrics page.
- Unit/integration tests (pytest) and CI.