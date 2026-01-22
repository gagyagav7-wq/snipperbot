import json
import os
import time
from datetime import datetime, timezone

# --- ABSOLUTE PATH (Anti Nyasar) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_PATH = os.path.join(BASE_DIR, "signal_state.json")

def save_state_atomic(active, sig_type=None, sl=0.0, tp=0.0, entry=0.0, reason="", candle_ts=0):
    """Save state dengan Audit Bersih (Clean data jika active=False)"""
    now_wall = int(time.time())
    
    # Kuncian Audit: Jika tidak aktif, semua data numerik di-nol-kan
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
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, FILE_PATH)

def check_signal_status(high, low):
    """Cek status dengan Self-Healing (Auto-Quarantine file korup)"""
    if not os.path.exists(FILE_PATH): 
        return "NONE"
        
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except Exception as e:
        # FAIL-SAFE: Rename file korup biar gak stuck selamanya
        timestamp = int(time.time())
        corrupt_name = f"{FILE_PATH}.corrupt.{timestamp}"
        try:
            os.rename(FILE_PATH, corrupt_name)
            print(f"🚨 STATE CORRUPT: File renamed to {corrupt_name}. System Locked temporarily.")
        except:
            print("🚨 CRITICAL: Cannot rename corrupt state file!")
        
        # Return STILL_OPEN sekali ini saja biar aman, next loop bakal bikin file baru/baca "NONE"
        return "STILL_OPEN"

    if not state.get("active"): 
        return "NONE"

    # --- GUARD VALIDITAS DATA ---
    if state.get("type") not in ["BUY", "SELL"]: return "NONE"
    if not state.get("sl") or not state.get("tp"): return "STILL_OPEN"

    # --- EXPIRY (Double Clock) ---
    if int(time.time()) - state.get("opened_at_wall_ts", 0) > 14400: # 4 Jam
        return "EXPIRED"

    # --- HIT DETECTION ---
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    elif state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
