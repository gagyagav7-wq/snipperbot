import json
import os

FILE_PATH = "trade_state.json"

def save_state(active, signal_type=None, sl=0, tp=0):
    """Menyimpan status trade aktif ke file JSON"""
    state = {
        "active": active,
        "type": signal_type,
        "sl": float(sl),
        "tp": float(tp)
    }
    with open(FILE_PATH, "w") as f:
        json.dump(state, f, indent=4)

def check_trade_status(current_bid, current_ask, high, low):
    """Mengecek apakah SL/TP sudah tersentuh"""
    if not os.path.exists(FILE_PATH):
        return None

    try:
        with open(FILE_PATH, "r") as f:
            state = json.load(f)
    except:
        return None

    if not state.get("active"):
        return None

    # Logika Cek SL/TP
    if state["type"] == "BUY":
        if high >= state["tp"]: return "TP_HIT"
        if low <= state["sl"]: return "SL_HIT"
    
    if state["type"] == "SELL":
        if low <= state["tp"]: return "TP_HIT"
        if high >= state["sl"]: return "SL_HIT"
            
    return "STILL_OPEN"
