import json
import os
from datetime import datetime, timedelta

FILE_PATH = "signal_state.json"

def save_signal_state(active, sig_type=None, sl=0, tp=0, entry=0, candle_time=None):
    state = {
        "active": active,
        "type": sig_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "candle_time": str(candle_time),
        "created_at": datetime.now().isoformat()
    }
    with open(FILE_PATH, "w") as f:
        json.dump(state, f, indent=4)

def check_signal_status(high, low):
    if not os.path.exists(FILE_PATH): return None
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return None

    # --- GUARD KETAT ---
    if not state.get("active"): return None
    if state.get("type") not in ["BUY", "SELL"]: return None
    if not state.get("sl") or not state.get("tp"): return None

    # --- FITUR EXPIRE 4 JAM ---
    created_at = datetime.fromisoformat(state["created_at"])
    if datetime.now() - created_at > timedelta(hours=4):
        print("⏰ Signal Expired (4 Hours Passed). Unlocking...")
        save_signal_state(active=False)
        return "EXPIRED"

    # Hit Detection
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    elif state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
