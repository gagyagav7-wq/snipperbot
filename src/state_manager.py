import json
import os
import time
from datetime import datetime, timezone

FILE_PATH = "signal_state.json"

def save_state_atomic(active, sig_type=None, sl=0, tp=0, entry=0, reason="", candle_ts=0):
    """Save state Atomic dengan Wall-Clock Time untuk Expiry yang aman"""
    state = {
        "active": active,
        "type": sig_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "reason": str(reason),
        "opened_at_candle_ts": int(candle_ts),
        "opened_at_wall_ts": int(time.time()), # Jam PC (Anti broker jump)
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, FILE_PATH)

def check_signal_status(high, low, current_candle_ts):
    """Cek status dengan return string eksplisit (Anti Ambigu)"""
    if not os.path.exists(FILE_PATH): return "NONE"
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return "NONE"

    if not state.get("active"): return "NONE"

    # --- 1. DOUBLE-CLOCK EXPIRY (4 Jam / 14400 Detik) ---
    # Cek berdasarkan Jam PC (Wall time) lebih aman dari broker jump
    if int(time.time()) - state.get("opened_at_wall_ts", 0) > 14400:
        return "EXPIRED"

    # --- 2. HIT DETECTION ---
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    elif state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
