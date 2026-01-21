import json
import os
from datetime import datetime, timezone

FILE_PATH = "signal_state.json"

def save_state_atomic(active, sig_type=None, sl=0, tp=0, entry=0, reason="", opened_at_ts=0):
    """Save state Atomic dengan parameter yang jelas (Named Args)"""
    state = {
        "active": active,
        "type": sig_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "reason": str(reason),
        "opened_at_candle_ts": int(opened_at_ts),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, FILE_PATH)

def check_signal_status(high, low, current_ts):
    if not os.path.exists(FILE_PATH): return None
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return None

    if not state.get("active") or not state.get("sl"): return None

    # Expiry 4 jam (14400 detik)
    if current_ts - state["opened_at_candle_ts"] > 14400:
        return "EXPIRED"

    # Hit Detection
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    elif state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
