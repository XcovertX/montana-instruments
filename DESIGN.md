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

## Timing & Data Integrity

## Outage Tolerance / Replay

## Diagnostics

## Safe Startup & Shutdown

## Security & Firmware Updates

## Future Extensions