
import json
import os
import time
from datetime import datetime, timezone

# --- ABSOLUTE PATH SETUP ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_PATH = os.path.join(BASE_DIR, "signal_state.json")

def save_state_atomic(active, sig_type=None, sl=0, tp=0, entry=0, reason="", candle_ts=0):
    """Save state Atomic dengan Wall-Clock Time"""
    state = {
        "active": active,
        "type": sig_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "reason": str(reason),
        "opened_at_candle_ts": int(candle_ts),
        "opened_at_wall_ts": int(time.time()),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, FILE_PATH)

def check_signal_status(high, low):
    """Cek status dengan Fail-Safe: Rusak = Lock (STILL_OPEN)"""
    if not os.path.exists(FILE_PATH): 
        return "NONE"
        
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except Exception:
        # FAIL-SAFE: Jika file corrupt, kunci sistem (jangan biarkan entry baru)
        print("🚨 STATE CORRUPT: Locking system for safety!")
        return "STILL_OPEN"

    if not state.get("active"): 
        return "NONE"

    # --- GUARD SL/TP & TYPE ---
    if state.get("type") not in ["BUY", "SELL"]: return "NONE"
    if not state.get("sl") or not state.get("tp"): return "STILL_OPEN"

    # --- EXPIRY (Jam PC) ---
    if int(time.time()) - state.get("opened_at_wall_ts", 0) > 14400:
        return "EXPIRED"

    # --- HIT DETECTION ---
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    elif state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
