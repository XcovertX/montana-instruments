from dataclasses import dataclass

@dataclass
class NodeConfig:
    anomaly_z: float = 3.0
    window: int = 120
    buffer_max: int = 5000
