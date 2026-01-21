import json
import os
import uuid
from datetime import datetime

FILE_PATH = "trade_state.json"

def save_state_atomic(active, sig_type=None, sl=0, tp=0, entry=0, reason="", opened_at=None):
    """Menyimpan state secara Atomic dengan Audit Trail lengkap"""
    state = {
        "id": str(uuid.uuid4())[:8] if active else "NONE",
        "active": active,
        "type": sig_type,
        "entry": float(entry) if entry else 0,
        "sl": float(sl) if sl else 0,
        "tp": float(tp) if tp else 0,
        "opened_at": str(opened_at) if opened_at else "NONE",
        "reason": reason,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    temp_file = FILE_PATH + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    
    os.replace(temp_file, FILE_PATH)

def check_trade_status(high, low):
    """Cek nasib trade berdasarkan High/Low dari bar yang sudah CLOSED"""
    if not os.path.exists(FILE_PATH): return None

    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except: return None

    # Guard: Kalau state gak aktif atau data SL/TP gak valid, anggap kosong
    if not state.get("active") or state.get("sl") == 0:
        return None

    # Logic Hit Detection (Gunakan harga High/Low)
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    
    if state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
