import json
import os
import time
from datetime import datetime, timezone

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_PATH = os.path.join(BASE_DIR, "signal_state.json")

def save_state_atomic(active, sig_type=None, sl=0.0, tp=0.0, entry=0.0, reason="", candle_ts=0):
    now_wall = int(time.time())
    state = {
        "active": bool(active),
        "type": sig_type if active else None,
        "entry": float(entry) if active else 0.0,
        "sl": float(sl) if active else 0.0,
        "tp": float(tp) if active else 0.0,
        "reason": str(reason) if active else "",
        "opened_at_candle_ts": int(candle_ts) if active else 0,
        "opened_at_wall_ts": now_wall if active else 0,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    temp_file = FILE_PATH + ".tmp"
    try:
        with open(temp_file, "w") as f:
            json.dump(state, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, FILE_PATH)
        return True
    except Exception as e:
        print(f"🚨 STATE WRITE FAILED: {e}")
        return False

def check_signal_status(high, low, current_bid=0, current_ask=0):
    if not os.path.exists(FILE_PATH): return "NONE"
    
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except:
        # Fail-Safe Lock
        ts = int(time.time())
        try: os.rename(FILE_PATH, f"{FILE_PATH}.corrupt.{ts}")
        except: pass
        return "STILL_OPEN"

    if not state.get("active"): return "NONE"

    # --- TYPE GUARD (Patch Baru) ---
    stype = state.get("type")
    if stype not in ["BUY", "SELL"]: 
        return "NONE" # Data korup/hantu, anggap kosong

    # --- EXPIRY CHECK ---
    if int(time.time()) - state.get("opened_at_wall_ts", 0) > 14400:
        return "EXPIRED"

    sl = state.get("sl", 0)
    tp = state.get("tp", 0)
    
    if not sl or not tp: return "STILL_OPEN" 

    # --- 1. REALTIME CHECK (Partial Tick) ---
    if stype == "BUY" and current_bid > 0:
        if current_bid >= tp: return "TP_HIT"
        if current_bid <= sl: return "SL_HIT"
            
    elif stype == "SELL" and current_ask > 0:
        if current_ask <= tp: return "TP_HIT"
        if current_ask >= sl: return "SL_HIT"

    # --- 2. CANDLE CHECK (Backup) ---
    if stype == "BUY":
        if high >= tp: return "TP_HIT"
        if low <= sl: return "SL_HIT"
    elif stype == "SELL":
        if low <= tp: return "TP_HIT"
        if high >= sl: return "SL_HIT"
            
    return "STILL_OPEN"
