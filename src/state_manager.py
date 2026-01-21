import json
import os
import uuid
from datetime import datetime

FILE_PATH = "trade_state.json"

def save_state_atomic(active, signal_type=None, sl=0, tp=0, entry=0, reason=""):
    """Menyimpan state secara Atomic (tulis ke file temp lalu rename)"""
    state = {
        "id": str(uuid.uuid4())[:8], # ID Unik buat audit
        "active": active,
        "type": signal_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason
    }
    
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno()) # Paksa nulis ke disk
    
    os.replace(temp_file, FILE_PATH) # Rename (Atomic)

def check_trade_status(high, low):
    """Cek TP/SL berdasarkan High/Low candle yang sudah CLOSED"""
    if not os.path.exists(FILE_PATH): return None

    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return None

    if not state.get("active"): return None

    # Hit Detection
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    
    if state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
