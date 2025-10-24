import time

# Time utility functions

PERIOD_10hz_s = 0.1

def get_monotonic_ms() -> int:
    return int(time.monotonic() * 1000)

def get_wall_ms() -> int:
    return int(time.time() * 1000)