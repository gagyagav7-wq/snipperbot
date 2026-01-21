# src/indicators.py (FULL UPDATE - PATCHED & ROBUST)
import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime

# --- KONFIGURASI ---
WIB = pytz.timezone('Asia/Jakarta')
SESSION_START = 14  
SESSION_END = 23    

# Strategy Config
MAX_SPREAD = 35         
SAFE_DIST_POINTS = 200  # <-- FIX: Udah didefinisikan
ATR_SL_MULT = 1.5       
RR_RATIO = 2.0          
MIN_BODY_ATR = 0.3      
BUFFER_STOP_LEVEL = 10  
MIN_ABS_STOP_DIST = 50  # <-- FIX: Jarak minimal absolut (antisipasi stop_level 0)

def calculate_rules(data_pack):
    # 0. SAFEGUARD CONTRACT
    contract = {
        "signal": "NO",
        "reason": "Initializing...",
        "setup": {},
        "timestamp": None,
        "tick": {},
        "df_5m": pd.DataFrame(),
        "meta": {"spread": 0, "session": False}
    }

    # 1. CRITICAL DATA VALIDATION
    if not data_pack or 'tick' not in data_pack:
        contract["reason"] = "Data Empty"
        return contract

    tick = data_pack['tick']
    # Guard Point/Digits
    if not tick.get('point') or tick.get('point') <= 0 or tick.get('digits') is None:
        contract["reason"] = "CRITICAL: Invalid Point/Digits"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    
    # FIX: Guard History Missing
    hist = data_pack.get('history', {})
    if hist.get('pdh') is None or hist.get('pdl') is None:
        contract["reason"] = "History Data (PDH/PDL) Missing"
        return contract

    contract["df_5m"] = df_5m
    contract["tick"] = tick

    # FIX: Guard Data Length (Sekarang server kirim 300, jadi aman cek 200)
    if len(df_5m) < 60 or len(df_15m) < 200:
        contract["reason"] = f"Not Enough Data (M15 has {len(df_15m)} bars)"
        return contract

    # 2. INDICATOR CALCULATION
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)

    last_5m = df_5m.iloc[-1]
    prev_5m = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    # Guard NaN Indicators
    if pd.isna(last_5m['ATR']) or pd.isna(last_15m['EMA_200']):
        contract["reason"] = "Indicators Calculating (NaN)..."
        return contract

    # 3. TIMEZONE & SESSION (Strict Epoch)
    try:
        ts = last_5m.name
        # FIX: Paksa Epoch UTC Aware dulu
        if isinstance(ts, (int, float)):
            utc_time = pd.to_datetime(ts, unit='s', utc=True)
        else:
            # Fallback kalau index bukan int (walau harusnya int dari server)
            utc_time = pd.to_datetime(ts).tz_localize('UTC') if ts.tzinfo is None else ts

        wib_time = utc_time.astimezone(WIB)
        contract["timestamp"] = wib_time
        
        if not (SESSION_START <= wib_time.hour < SESSION_END):
            contract["meta"]["session"] = False
            contract["reason"] = f"Outside Killzone ({wib_time.hour:02d}:00)"
            return contract
            
        contract["meta"]["session"] = True
    except Exception as e:
        contract["reason"] = f"Timezone Error: {e}"
        return contract

    # 4. SPREAD FILTER
    spread = tick.get('spread', 999)
    contract["meta"]["spread"] = spread
    if spread > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Spread {spread} > {MAX_SPREAD}"
        return contract

    # 5. TREND & PATTERN
    # Strong Trend
    bull_trend = (last_15m['Close'] > last_15m['EMA_50']) and (last_15m['EMA_50'] > last_15m['EMA_200'])
    bear_trend = (last_15m['Close'] < last_15m['EMA_50']) and (last_15m['EMA_50'] < last_15m['EMA_200'])

    # Pattern Quality
    body = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    # FIX: Re-Add RSI Filter
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['Close'] > prev_5m['High']) and \
                  (last_5m['RSI'] < 70) # <-- RSI Guard

    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > prev_5m['Close']) and \
                  (last_5m['Close'] < prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['Close'] < prev_5m['Low']) and \
                  (last_5m['RSI'] > 30) # <-- RSI Guard

    # 6. EXECUTION LOGIC
    point = tick['point']
    digits = tick['digits']
    
    def to_points(val): return val / point

    # Validasi Stop Level (FIX: Add Hard Floor 50 points)
    stop_level_pts = tick.get('stop_level', 0)
    min_sl_dist_pts = stop_level_pts + spread + BUFFER_STOP_LEVEL
    if min_sl_dist_pts < MIN_ABS_STOP_DIST: 
        min_sl_dist_pts = MIN_ABS_STOP_DIST

    # -- BUY --
    if bull_engulf and bull_trend:
        dist_pdh_pts = to_points(hist['pdh'] - tick['ask'])
        if 0 < dist_pdh_pts < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDH ({int(dist_pdh_pts)} pts)"
            return contract

        entry = tick['ask']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        # Guard SL Distance
        if to_points(sl_dist_raw) < min_sl_dist_pts:
            sl_dist_raw = min_sl_dist_pts * point
        
        sl = entry - sl_dist_raw
        tp = entry + (sl_dist_raw * RR_RATIO)
        
        contract["signal"] = "BUY"
        contract["reason"] = "Bullish Engulfing + Trend"
        contract["setup"] = {
            "action": "BUY",
            "entry": round(entry, digits),
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "atr": round(last_5m['ATR'], digits)
        }

    # -- SELL --
    elif bear_engulf and bear_trend:
        dist_pdl_pts = to_points(tick['bid'] - hist['pdl'])
        if 0 < dist_pdl_pts < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDL ({int(dist_pdl_pts)} pts)"
            return contract

        entry = tick['bid']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        # Guard SL Distance
        if to_points(sl_dist_raw) < min_sl_dist_pts:
            sl_dist_raw = min_sl_dist_pts * point

        sl = entry + sl_dist_raw
        tp = entry - (sl_dist_raw * RR_RATIO)
        
        contract["signal"] = "SELL"
        contract["reason"] = "Bearish Engulfing + Trend"
        contract["setup"] = {
            "action": "SELL",
            "entry": round(entry, digits),
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "atr": round(last_5m['ATR'], digits)
        }
    
    else:
        contract["reason"] = "No Setup"

    return contract
