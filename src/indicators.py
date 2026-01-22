import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from datetime import datetime, timezone

# --- KONFIGURASI SCALPER (USD ABSOLUTE) ---
TARGET_SL_MIN_USD = 3.0  # SL $3
TARGET_SL_MAX_USD = 5.0  # SL $5
MAX_SPREAD_USD    = 0.50 # Spread max $0.50
RR_RATIO          = 1.2  
MAX_TP_USD        = 8.0  

def find_quality_ob(df):
    if len(df) < 100: return None, None
    subset = df.tail(100).copy()
    atr = ta.atr(subset['High'], subset['Low'], subset['Close'], length=14)
    subset['ATR'] = atr
    
    ob_bull = None
    ob_bear = None
    
    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        if pd.isna(current_atr) or current_atr <= 0: continue
        
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: 
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] > subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i]) 
                break 

    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        if pd.isna(current_atr) or current_atr <= 0: continue

        if subset['Close'].iloc[i] > subset['Open'].iloc[i]:
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] < subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i])
                break

    return ob_bull, ob_bear

def get_swing_structure(df):
    """Cari Swing High/Low M15 buat konteks Elliott Wave"""
    # Simple Pivot High/Low (length 5 kiri kanan)
    # Ini berat kalau pakai pandas_ta pivot, kita pake rolling max/min aja yang cepet
    # atau ambil High/Low absolut 20 candle terakhir
    recent_high = df['High'].tail(20).max()
    recent_low = df['Low'].tail(20).min()
    return recent_high, recent_low

def calculate_rules(data):
    # 1. PREP DATA
    if 'm5' not in data or data['m5'].empty:
        return {"signal": "WAIT", "reason": "Data Empty", "setup": {}, "timestamp": None}

    df_m5 = data['m5'].copy()
    tick = data.get('tick', {})
    meta = data.get('meta', {})
    
    bid = float(tick.get('bid', 0) or 0)
    ask = float(tick.get('ask', 0) or 0)
    
    last = df_m5.iloc[-1]
    prev = df_m5.iloc[-2]
    timestamp = last.name

    # --- GUARD BLOCK (LEVEL: BANK GRADE) ---
    
    # 1. Market Closed
    if bid <= 0 or ask <= 0:
        return {"signal": "WAIT", "reason": "Invalid Tick", "setup": {}, "timestamp": timestamp}

    # 2. Spread Guard (USD)
    point = float(tick.get('point', 0.01) or 0.01)
    spread_raw = float(tick.get('spread', 0) or 0)
    real_spread_usd = abs(ask - bid) # Pake Ask-Bid lebih jujur
    
    if real_spread_usd > MAX_SPREAD_USD:
        return {"signal": "WAIT", "reason": f"High Spread: ${real_spread_usd:.2f}", "setup": {}, "timestamp": timestamp}

    # 3. Stale Feed (Data Basi - Scalper Threshold: 15s)
    tick_msc = int(meta.get("tick_time_msc") or 0)
    tick_sec = int(meta.get("tick_time") or 0)
    
    broker_ts = None
    if tick_msc > 0: broker_ts = tick_msc / 1000.0
    elif tick_sec > 0: broker_ts = float(tick_sec)
    
    if broker_ts:
        lag = time.time() - broker_ts
        if lag > 15: # 15 Detik toleransi maksimal buat scalping
            return {"signal": "WAIT", "reason": f"Stale Feed: {lag:.1f}s Lag", "setup": {}, "timestamp": timestamp}
    else:
        # Kalau gak ada timestamp broker sama sekali, bahaya
        return {"signal": "WAIT", "reason": "No Broker Timestamp", "setup": {}, "timestamp": timestamp}

    # 4. Broker Chaos (USD Based)
    stop_lvl = int(tick.get("stop_level", 0) or 0)
    frz_lvl = int(tick.get("freeze_level", 0) or 0)
    
    stop_usd = stop_lvl * point
    frz_usd = frz_lvl * point
    
    if stop_usd > 2.0 or frz_usd > 2.0: # $2 limit abnormal
        return {"signal": "WAIT", "reason": f"Broker Chaos (StopLvl ${stop_usd:.1f})", "setup": {}, "timestamp": timestamp}

    # --- INDICATOR ANALYSIS ---
    
    # 1. TREND FILTER (M15)
    trend = "NEUTRAL"
    m15_high, m15_low = 0, 0
    
    if 'm15' in data and not data['m15'].empty:
        df_m15 = data['m15']
        
        # Guard Warmup M15
        if len(df_m15) < 220:
             return {"signal": "WAIT", "reason": "M15 Warming Up", "setup": {}, "timestamp": timestamp}
             
        ema_50 = ta.ema(df_m15['Close'], length=50).iloc[-1]
        ema_200 = ta.ema(df_m15['Close'], length=200).iloc[-1]
        
        if pd.isna(ema_50) or pd.isna(ema_200):
            return {"signal": "WAIT", "reason": "M15 EMA NaN", "setup": {}, "timestamp": timestamp}
            
        trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
        
        # Ambil Swing M15 buat AI (Elliott Wave Context)
        m15_high, m15_low = get_swing_structure(df_m15)
    else:
        # Fallback (Jangan entry kalau M15 mati)
        return {"signal": "WAIT", "reason": "M15 Data Missing", "setup": {}, "timestamp": timestamp}

    # 2. ATR & BUFFER (M5)
    atr_val = ta.atr(df_m5['High'], df_m5['Low'], df_m5['Close'], length=14).iloc[-1]
    
    # Guard ATR NaN
    if pd.isna(atr_val) or atr_val <= 0:
        return {"signal": "WAIT", "reason": "ATR Warming Up", "setup": {}, "timestamp": timestamp}
        
    sweep_buffer = 0.2 * atr_val 

    # 3. SMC LOGIC
    ob_bull, ob_bear = find_quality_ob(df_m5)
    
    signal = "WAIT"
    reason = "Scanning..."
    
    # LOGIC BUY
    if trend == "BULLISH" and ob_bull:
        ob_low, ob_high = ob_bull
        touched = last['Low'] <= ob_high
        held = last['Low'] >= (ob_low - sweep_buffer)
        rejected = last['Close'] > ob_high
        
        if touched and held and rejected:
            signal = "BUY"
            reason = "SMC: Bullish OB Retest + M15 Align"

    # LOGIC SELL
    if trend == "BEARISH" and ob_bear:
        ob_low, ob_high = ob_bear
        touched = last['High'] >= ob_low
        held = last['High'] <= (ob_high + sweep_buffer)
        rejected = last['Close'] < ob_low
        
        if touched and held and rejected:
            signal = "SELL"
            reason = "SMC: Bearish OB Retest + M15 Align"

    # --- EXECUTION & META EXPORT ---
    setup = {}
    sl_usd_dist = 0.0
    tp_usd_dist = 0.0

    if signal in ["BUY", "SELL"]:
        entry_price = ask if signal == "BUY" else bid
        
        if signal == "BUY":
            swing_low = min(last['Low'], prev['Low'])
            raw_sl_dist = entry_price - swing_low
        else:
            swing_high = max(last['High'], prev['High'])
            raw_sl_dist = swing_high - entry_price
        
        # CLAMP SL ($3 - $5)
        final_sl_dist = max(TARGET_SL_MIN_USD, min(raw_sl_dist, TARGET_SL_MAX_USD))
        sl_usd_dist = final_sl_dist
        
        raw_tp_dist = final_sl_dist * RR_RATIO
        final_tp_dist = min(raw_tp_dist, MAX_TP_USD)
        tp_usd_dist = final_tp_dist
        
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

    # Meta untuk Logger & AI
    export_meta = {
        "indicators": {
            "trend_m15": trend,
            "atr_m5": atr_val,
            "ob_status": "Active" if (ob_bull or ob_bear) else "None",
            # Kirim struktur M15 ke AI biar bisa baca Elliott Wave
            "m15_structure": {
                "recent_high": m15_high,
                "recent_low": m15_low,
                "current_price": last['Close']
            }
        },
        "risk_audit": {
            "spread_usd": real_spread_usd,
            "sl_usd": sl_usd_dist,
            "tp_usd": tp_usd_dist
        },
        "spread": real_spread_usd,
        # Candle Snapshot buat Logger
        "candle": {
            "close": float(last['Close']),
            "high": float(last['High']),
            "low": float(last['Low']),
            "time": str(timestamp)
        },
        # Forward Times
        "tick_time_msc": tick_msc,
        "tick_time": tick_sec,
        "server_time": meta.get("server_time")
    }

    return {
        "signal": signal,
        "reason": reason,
        "setup": setup,
        "timestamp": timestamp,
        "meta": export_meta
    }
