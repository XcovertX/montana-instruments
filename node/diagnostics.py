import random

def run_diagnostics() -> dict:
    # Simulate a basic diagnostic - rail voltage check
    rail_ok = random.random() > 0.02   # 2% chance of false diag
    return {
        "diag_ok": rail_ok,
        "diag_reason": "" if rail_ok else "rail_low"
    }