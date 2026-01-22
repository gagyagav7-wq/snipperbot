import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from datetime import datetime, timezone

# --- KONFIGURASI SCALPER (USD ABSOLUTE) ---
TARGET_SL_MIN_USD = 3.0  
TARGET_SL_MAX_USD = 5.0  
MAX_SPREAD_USD    = 0.50 
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
        atr_next = subset['ATR'].iloc[i+1]
        if pd.isna(atr_next) or atr_next <= 0: continue
        
        # BULLISH
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: 
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] > subset['Open'].iloc[i+1] and body_next > (atr_next * 0.8):
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i]) 
                break 

    for i in range(len(subset)-4, 0, -1):
        atr_next = subset['ATR'].iloc[i+1]
        if pd.isna(atr_next) or atr_next <= 0: continue

        # BEARISH
        if subset['Close'].iloc[i] > subset['Open'].iloc[i]:
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] < subset['Open'].iloc[i+1] and body_next > (atr_next * 0.8):
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i])
                break

    return ob_bull, ob_bear

def get_market_structure(df, window=5):
    """
    Ekstrak Struktur Pivot M15 dengan Label (HH/HL/LH/LL).
    FIX: Support Outside Bar (If-If) & Anti-Spam (Epsilon).
    """
    if len(df) < (window * 2 + 10): return []
    
    pivots = []
    eps = 1e-5 # Toleransi float
    
    for i in range(window, len(df) - window):
        curr_high = df['High'].iloc[i]
        curr_low = df['Low'].iloc[i]
        
        # Window High/Low
        win_high = df['High'].iloc[i-window:i+window+1].max()
        win_low  = df['Low'].iloc[i-window:i+window+1].min()
        
        # FIX 1 & 2: Pakai IF-IF (bukan elif) dan Epsilon
        is_pivot_high = curr_high >= (win_high - eps)
        is_pivot_low  = curr_low <= (win_low + eps)
        
        if is_pivot_high:
            pivots.append({
                "index": i, "type": "High", 
                "price": float(curr_high), "time": str(df.index[i])
            })
            
        if is_pivot_low:
            pivots.append({
                "index": i, "type": "Low", 
                "price": float(curr_low), "time": str(df.index[i])
            })
    
    # Labeling Logic (HH, HL, LH, LL)
    highs = [p for p in pivots if p['type'] == 'High']
    lows = [p for p in pivots if p['type'] == 'Low']
    
    for i in range(len(highs)):
        label = "H"
        if i > 0:
            if highs[i]['price'] > highs[i-1]['price']: label = "HH"
            elif highs[i]['price'] < highs[i-1]['price']: label = "LH"
            else: label = "Equal H"
        highs[i]['label'] = label
        
    for i in range(len(lows)):
        label = "L"
        if i > 0:
            if lows[i]['price'] > lows[i-1]['price']: label = "HL"
            elif lows[i]['price'] < lows[i-1]['price']: label = "LL"
            else: label = "Equal L"
        lows[i]['label'] = label

    # Gabung, Urutkan, dan Ambil 5 Terakhir
    all_pivots = sorted(highs + lows, key=lambda x: x['index'])
    return all_pivots[-5:]

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
    timestamp = last.name

    # --- GUARD BLOCK ---
    if bid <= 0 or ask <= 0:
        return {"signal": "WAIT", "reason": "Invalid Tick", "setup": {}, "timestamp": timestamp}

    real_spread_usd = abs(ask - bid)
    if real_spread_usd > MAX_SPREAD_USD:
        return {"signal": "WAIT", "reason": f"High Spread: ${real_spread_usd:.2f}", "setup": {}, "timestamp": timestamp}

    # FIX 3: Stale Feed Audit (Raw + Clamped)
    tick_msc = int(meta.get("tick_time_msc") or 0)
    tick_sec = int(meta.get("tick_time") or 0)
    broker_ts = None
    if tick_msc > 0: broker_ts = tick_msc / 1000.0
    elif tick_sec > 0: broker_ts = float(tick_sec)
    
    warnings = []
    lag_raw = 0.0
    lag_clamped = 0.0
    
    if broker_ts:
        lag_raw = time.time() - broker_ts
        lag_clamped = max(0.0, lag_raw)
        
        if lag_raw < -2: 
             warnings.append(f"Clock Drift {lag_raw:.1f}s")
        
        if lag_clamped > 15: 
             return {"signal": "WAIT", "reason": f"Stale Feed: {lag_clamped:.1f}s", "setup": {}, "timestamp": timestamp}
    else:
        return {"signal": "WAIT", "reason": "No Broker TS", "setup": {}, "timestamp": timestamp}

    # Broker Chaos
    point = float(tick.get('point', 0.01) or 0.01)
    stop_usd = (int(tick.get("stop_level", 0) or 0)) * point
    if stop_usd > 2.0:
        return {"signal": "WAIT", "reason": "High Stop Level", "setup": {}, "timestamp": timestamp}

    # --- INDICATOR ANALYSIS ---
    trend = "NEUTRAL"
    m15_structure = []
    
    if 'm15' in data and not data['m15'].empty:
        df_m15 = data['m15']
        if len(df_m15) < 220: return {"signal": "WAIT", "reason": "M15 Warmup", "setup": {}, "timestamp": timestamp}
             
        ema_50 = ta.ema(df_m15['Close'], length=50).iloc[-1]
        ema_200 = ta.ema(df_m15['Close'], length=200).iloc[-1]
        if pd.isna(ema_50): return {"signal": "WAIT", "reason": "EMA NaN", "setup": {}, "timestamp": timestamp}
            
        trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
        m15_structure = get_market_structure(df_m15)
    else:
        return {"signal": "WAIT", "reason": "M15 Missing", "setup": {}, "timestamp": timestamp}

    atr_val = ta.atr(df_m5['High'], df_m5['Low'], df_m5['Close'], length=14).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0: return {"signal": "WAIT", "reason": "ATR NaN", "setup": {}, "timestamp": timestamp}
    sweep_buffer = 0.2 * atr_val 

    ob_bull, ob_bear = find_quality_ob(df_m5)
    
    signal = "WAIT"
    reason = "Scanning..."
    ob_used = None 
    
    # LOGIC BUY
    if trend == "BULLISH" and ob_bull:
        ob_low, ob_high = ob_bull
        touched = last['Low'] <= ob_high
        held = last['Low'] >= (ob_low - sweep_buffer)
        rejected = last['Close'] > ob_high
        near_ob = last['Close'] <= (ob_high + atr_val * 0.2) 
        
        if touched and held and rejected and near_ob:
            signal = "BUY"
            reason = "SMC: Bullish OB Retest + M15 Trend"
            ob_used = ob_bull

    # FIX 4: Defensive Coding (ELIF for SELL)
    elif trend == "BEARISH" and ob_bear:
        ob_low, ob_high = ob_bear
        touched = last['High'] >= ob_low
        held = last['High'] <= (ob_high + sweep_buffer)
        rejected = last['Close'] < ob_low
        near_ob = last['Close'] >= (ob_low - atr_val * 0.2)
        
        if touched and held and rejected and near_ob:
            signal = "SELL"
            reason = "SMC: Bearish OB Retest + M15 Trend"
            ob_used = ob_bear

    # --- EXECUTION ---
    setup = {}
    sl_usd_dist = 0.0
    tp_usd_dist = 0.0

    if signal in ["BUY", "SELL"]:
        entry_price = ask if signal == "BUY" else bid
        
        if signal == "BUY":
            ob_low_point = ob_used[0]
            structural_sl = ob_low_point - sweep_buffer
            raw_sl_dist = entry_price - structural_sl
        else:
            ob_high_point = ob_used[1]
            structural_sl = ob_high_point + sweep_buffer
            raw_sl_dist = structural_sl - entry_price
        
        if raw_sl_dist <= 0:
             return {"signal": "WAIT", "reason": "Invalid SL Distance", "setup": {}, "timestamp": timestamp}

        if raw_sl_dist > TARGET_SL_MAX_USD:
             return {"signal": "WAIT", "reason": f"Structure Too Wide (${raw_sl_dist:.2f})", "setup": {}, "timestamp": timestamp}

        final_sl_dist = max(TARGET_SL_MIN_USD, raw_sl_dist)
        sl_usd_dist = final_sl_dist
        
        if real_spread_usd > (final_sl_dist * 0.15):
             return {"signal": "WAIT", "reason": "Spread too expensive", "setup": {}, "timestamp": timestamp}
        
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

    export_meta = {
        "indicators": {
            "trend_m15": trend,
            "atr_m5": atr_val,
            "ob_status": "Active" if (ob_bull or ob_bear) else "None",
            "m15_structure": m15_structure 
        },
        "risk_audit": {
            "spread_usd": real_spread_usd,
            "sl_usd": sl_usd_dist,
            "tp_usd": tp_usd_dist,
            "warnings": warnings,
            "tick_lag_sec_raw": lag_raw, # Audit Drift
            "tick_lag_sec": lag_clamped  # Audit Safety
        },
        "warnings": warnings, 
        "spread": real_spread_usd,
        "tick_lag_sec": lag_clamped,
        "candle": {
            "close": float(last['Close']),
            "high": float(last['High']),
            "low": float(last['Low']),
            "time": str(timestamp)
        }
    }

    return {
        "signal": signal,
        "reason": reason,
        "setup": setup,
        "timestamp": timestamp,
        "meta": export_meta
    }
