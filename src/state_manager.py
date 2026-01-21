import json
import os
import uuid

FILE_PATH = "trade_state.json"

def save_state_atomic(active, sig_type=None, sl=0, tp=0, entry=0, reason=""):
    """Simpan state pakai metode temp-rename (Atomic)"""
    state = {
        "id": str(uuid.uuid4())[:8],
        "active": active,
        "type": sig_type,
        "entry": float(entry),
        "sl": float(sl),
        "tp": float(tp),
        "reason": reason
    }
    
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno()) # Paksa tulis ke disk
    
    os.replace(temp_file, FILE_PATH)

def check_trade_status(high, low):
    """Cek apakah harga High/Low candle menyentuh SL/TP di memori"""
    if not os.path.exists(FILE_PATH): return None
    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return None

    if not state.get("active"): return None

    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    
    if state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
