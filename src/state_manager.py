import json
import os
from datetime import datetime, timezone

FILE_PATH = "signal_state.json"

def save_state_atomic(active, sig_type=None, sl=0, tp=0, entry=0, candle_ts=0):
    """Save state dengan metode Atomic (Anti-Korup)"""
    state = {
        "active": active,
        "type": sig_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "opened_at_candle_ts": int(candle_ts),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, FILE_PATH)

def check_signal_status(last_closed_bar_high, last_closed_bar_low, current_candle_ts):
    if not os.path.exists(FILE_PATH): return None
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return None

    if not state.get("active") or not state.get("sl"): return None

    # --- 1. CEK EXPIRE BERDASARKAN CANDLE (4 JAM = 14400 DETIK) ---
    if current_candle_ts - state["opened_at_candle_ts"] > 14400:
        save_state_atomic(active=False)
        return "EXPIRED"

    # --- 2. CEK HIT DETECTION ---
    if state["type"] == "BUY":
        if last_closed_bar_high >= state["tp"]: return "TP_HIT"
        if last_closed_bar_low <= state["sl"]: return "SL_HIT"
    elif state["type"] == "SELL":
        if last_closed_bar_low <= state["tp"]: return "TP_HIT"
        if last_closed_bar_high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
