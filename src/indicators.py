import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from datetime import datetime, timezone

# --- KONFIGURASI SCALPER (USD ABSOLUTE) ---
# TARGET: 30-50 Pips Scalping Gold
# Definisi umum Scalper Indo: 1 Pip = $0.10, 10 Pips = $1.00
# Jadi 30 Pips = Pergerakan harga $3.00
TARGET_SL_MIN_USD = 3.0  
TARGET_SL_MAX_USD = 5.0  
RR_RATIO          = 1.2  
MAX_TP_USD        = 8.0  
MAX_SPREAD_USD    = 0.50 # Maksimal spread 50 cents ($0.50). Lebih dari ini SKIP.

def find_quality_ob(df):
    """Mencari Order Block Valid dengan Displacement & ATR Guard"""
    if len(df) < 100: return None, None
    subset = df.tail(100).copy()
    atr = ta.atr(subset['High'], subset['Low'], subset['Close'], length=14)
    subset['ATR'] = atr
    
    ob_bull = None
    ob_bear = None
    
    # Loop Mundur
    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        # GUARD: Skip jika ATR NaN (Data belum cukup)
        if pd.isna(current_atr) or current_atr <= 0: continue
        
        # BULLISH OB
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: 
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] > subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i]) 
                break 

    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        if pd.isna(current_atr) or current_atr <= 0: continue

        # BEARISH OB
        if subset['Close'].iloc[i] > subset['Open'].iloc[i]:
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] < subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i])
                break

    return ob_bull, ob_bear

def calculate_rules(data):
    # 1. PREP DATA & INTEGRITY CHECKS
    # Pastikan data wajib ada
    if 'm5' not in data or data['m5'].empty:
        return {"signal": "WAIT", "reason": "Data M5 Empty", "setup": {}, "timestamp": None}
    
    # Ambil Tick Data Realtime
    tick = data.get('tick', {})
    meta = data.get('meta', {})
    
    bid = float(tick.get('bid', 0) or 0)
    ask = float(tick.get('ask', 0) or 0)
    
    # GUARD 1: Market Closed / Invalid Data
    if bid <= 0 or ask <= 0:
        return {"signal": "WAIT", "reason": "Invalid Tick (Market Closed?)", "setup": {}, "timestamp": None}

    # GUARD 2: Real Spread Check (Ask - Bid)
    real_spread_usd = abs(ask - bid)
    if real_spread_usd > MAX_SPREAD_USD:
        return {"signal": "WAIT", "reason": f"High Spread: ${real_spread_usd:.2f}", "setup": {}, "timestamp": None}

    # GUARD 3: Stale Feed (Data Basi)
    # Cek selisih waktu server MT5 vs waktu sekarang
    tick_time_msc = int(meta.get("tick_time_msc") or 0)
    now_ts = time.time()
    
    if tick_time_msc > 0:
        # Convert msc to seconds
        lag = now_ts - (tick_time_msc / 1000.0)
        if lag > 120: # Toleransi 2 menit (kalau VPS lag)
             return {"signal": "WAIT", "reason": f"Stale Data Lag: {lag:.1f}s", "setup": {}, "timestamp": None}

    # GUARD 4: Broker Chaos (Freeze/Stop Level abnormal)
    stop_level = int(tick.get("stop_level", 0) or 0)
    freeze_level = int(tick.get("freeze_level", 0) or 0)
    if stop_level > 200 or freeze_level > 200: # 200 points = $2.0 range (sangat abnormal)
        return {"signal": "WAIT", "reason": "Broker Chaos (High Stop/Freeze Level)", "setup": {}, "timestamp": None}


    # --- ANALYSIS BLOCK ---
    df_m5 = data['m5'].copy()
    last = df_m5.iloc[-1]
    prev = df_m5.iloc[-2]
    
    # 2. TREND FILTER (M15 PRIORITY)
    # Gunakan M15 untuk arah besar biar gak kegulung chop di M5
    trend = "NEUTRAL"
    if 'm15' in data and not data['m15'].empty:
        df_m15 = data['m15']
        ema_50 = ta.ema(df_m15['Close'], length=50).iloc[-1]
        ema_200 = ta.ema(df_m15['Close'], length=200).iloc[-1]
        trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
    else:
        # Fallback ke M5 kalau M15 belum load
        ema_50 = ta.ema(df_m5['Close'], length=50).iloc[-1]
        ema_200 = ta.ema(df_m5['Close'], length=200).iloc[-1]
        trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"

    # 3. ATR BUFFER
    atr_val = ta.atr(df_m5['High'], df_m5['Low'], df_m5['Close'], length=14).iloc[-1]
    if pd.isna(atr_val): atr_val = 1.0 # Fallback aman
    sweep_buffer = 0.2 * atr_val 

    # 4. SMC LOGIC (Execution di M5)
    ob_bull, ob_bear = find_quality_ob(df_m5)
    
    signal = "WAIT"
    reason = "Scanning..."
    
    # LOGIC BUY
    if trend == "BULLISH" and ob_bull:
        ob_low, ob_high = ob_bull
        # Retest Logic:
        # 1. Low masuk zona atau nyentuh
        touched = last['Low'] <= ob_high
        # 2. Low TIDAK tembus parah (di atas Low OB - buffer)
        held = last['Low'] >= (ob_low - sweep_buffer)
        # 3. Close mantul ke atas (Rejection)
        rejected = last['Close'] > ob_high
        
        if touched and held and rejected:
            signal = "BUY"
            reason = "SMC: Bullish OB Retest + M15 Trend Align"

    # LOGIC SELL
    if trend == "BEARISH" and ob_bear:
        ob_low, ob_high = ob_bear
        # Retest Logic
        touched = last['High'] >= ob_low
        held = last['High'] <= (ob_high + sweep_buffer)
        rejected = last['Close'] < ob_low
        
        if touched and held and rejected:
            signal = "SELL"
            reason = "SMC: Bearish OB Retest + M15 Trend Align"

    # --- EXECUTION BLOCK (MONEY MANAGEMENT) ---
    setup = {}
    sl_usd_dist = 0.0
    tp_usd_dist = 0.0

    if signal in ["BUY", "SELL"]:
        # Entry Realtime
        entry_price = ask if signal == "BUY" else bid
        
        # Hitung Jarak SL Mentah (berdasarkan Swing)
        if signal == "BUY":
            swing_low = min(last['Low'], prev['Low'])
            raw_sl_dist = entry_price - swing_low
        else:
            swing_high = max(last['High'], prev['High'])
            raw_sl_dist = swing_high - entry_price
        
        # CLAMPING JARAK SL ($3.0 - $5.0)
        final_sl_dist = max(TARGET_SL_MIN_USD, min(raw_sl_dist, TARGET_SL_MAX_USD))
        sl_usd_dist = final_sl_dist
        
        # Hitung TP dengan Cap Max
        raw_tp_dist = final_sl_dist * RR_RATIO
        final_tp_dist = min(raw_tp_dist, MAX_TP_USD)
        tp_usd_dist = final_tp_dist
        
        # Hitung Harga Akhir
        if signal == "BUY":
            sl_price = entry_price - final_sl_dist
            tp_price = entry_price + final_tp_dist
        else:
            sl_price = entry_price + final_sl_dist
            tp_price = entry_price - final_tp_dist

        setup = {
            "entry": entry_price,
            "sl": sl_price,
            "tp": tp_price
        }

    return {
        "signal": signal,
        "reason": reason,
        "setup": setup,
        "timestamp": last.name,
        "meta": {
            "indicators": {
                "trend_m15": trend,
                "atr_m5": atr_val,
                "ob_status": "Active" if (ob_bull or ob_bear) else "None"
            },
            "risk_audit": {
                "spread_usd": real_spread_usd,
                "sl_usd": sl_usd_dist,
                "tp_usd": tp_usd_dist
            },
            "spread": real_spread_usd,
            "price": last['Close']
        }
    }
