from dataclasses import dataclass

@dataclass
class Config:
    anomaly_z: float = 3.0           # z-score threshold
    window: int = 120                # samples in rolling window (at 10 Hz -> 12 s)
    buffer_max: int = 5000           # max in-memory buffer entries before degraded/backpressure

DEFAULT_CONFIG = Config()
