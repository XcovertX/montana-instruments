import time

# Time utility functions
def get_monotonic_ms() -> int:
    return int(time.monotonic() * 1000)

def get_wall_ms() -> int:
    return int(time.time() * 1000)