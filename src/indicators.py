import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime

# --- KONFIGURASI STRATEGI ---
WIB = pytz.timezone('Asia/Jakarta')
SESSION_START = 14  
SESSION_END = 23    

MAX_SPREAD = 35         
SAFE_DIST_POINTS = 200  
ATR_SL_MULT = 1.5       
RR_RATIO = 2.0          
MIN_BODY_ATR = 0.3      

# Risk Config
BUFFER_STOP_LEVEL = 10  
MIN_ABS_STOP_DIST = 50 
ABNORMAL_LEVEL_THRESHOLD = 100 # Kalau Freeze/Stop Level > 100 points, market lagi gila. SKIP.

def calculate_rules(data_pack):
    contract = {
        "signal": "NO",
        "reason": "Init",
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
    point = tick.get('point')
    digits = tick.get('digits')
    
    # [GUARD] Invalid Tick Data / Market Glitch
    if tick.get('bid', 0) <= 0 or tick.get('ask', 0) <= 0:
        contract["reason"] = "Market Closed (Tick 0)"
        return contract

    if point is None or point <= 0:
        contract["reason"] = "Invalid Point Value"
        return contract
        
    if digits is None or digits < 1: # XAUUSD minimal digits 2
        contract["reason"] = "Invalid Digits"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    hist = data_pack.get('history', {})
    
    # Guard History
    if hist.get('pdh') is None or hist.get('pdl') is None:
        contract["reason"] = "History Missing"
        return contract

    contract["df_5m"] = df_5m
    contract["tick"] = tick

    # Guard Data Length
    if len(df_5m) < 60 or len(df_15m) < 200:
        contract["reason"] = "Not Enough Bars"
        return contract

    # 2. INDICATORS
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)

    last_5m = df_5m.iloc[-1]
    prev_5m = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    if pd.isna(last_5m['ATR']) or pd.isna(last_15m['EMA_200']):
        contract["reason"] = "Indicators Loading..."
        return contract

    # 3. TIMEZONE (Epoch UTC -> WIB)
    try:
        ts = last_5m.name
        if isinstance(ts, (int, float)):
            utc_time = pd.to_datetime(ts, unit='s', utc=True)
        else:
            utc_time = pd.to_datetime(ts).tz_localize('UTC') if ts.tzinfo is None else ts

        wib_time = utc_time.astimezone(WIB)
        contract["timestamp"] = wib_time
        
        if not (SESSION_START <= wib_time.hour < SESSION_END):
            contract["meta"]["session"] = False
            contract["reason"] = f"Outside Killzone ({wib_time.hour:02d}:00)"
            return contract
        contract["meta"]["session"] = True
    except Exception as e:
        contract["reason"] = f"Time Error: {e}"
        return contract

    # 4. MARKET CONDITION FILTERS
    spread = tick.get('spread', 999)
    stop_level = tick.get('stop_level', 0)
    freeze_level = tick.get('freeze_level', 0)
    
    contract["meta"]["spread"] = spread

    # [GUARD] Abnormal Broker Conditions
    if stop_level > ABNORMAL_LEVEL_THRESHOLD or freeze_level > ABNORMAL_LEVEL_THRESHOLD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Broker Restriction High (Stop: {stop_level}, Freeze: {freeze_level})"
        return contract

    if spread > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"High Spread: {spread}"
        return contract

    # 5. STRATEGY (Strong Trend + Confirm)
    bull_trend = (last_15m['Close'] > last_15m['EMA_50']) and (last_15m['EMA_50'] > last_15m['EMA_200'])
    bear_trend = (last_15m['Close'] < last_15m['EMA_50']) and (last_15m['EMA_50'] < last_15m['EMA_200'])

    body = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['Close'] > prev_5m['High']) and \
                  (last_5m['RSI'] < 70)

    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > prev_5m['Close']) and \
                  (last_5m['Close'] < prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['Close'] < prev_5m['Low']) and \
                  (last_5m['RSI'] > 30)

    # 6. EXECUTION LOGIC
    def to_points(val): return val / point

    # Minimum SL Distance = StopLvl + FreezeLvl + Spread + Buffer
    min_dist_req = stop_level + freeze_level + spread + BUFFER_STOP_LEVEL
    min_sl_dist_pts = max(min_dist_req, MIN_ABS_STOP_DIST)

    # -- BUY --
    if bull_engulf and bull_trend:
        dist_pdh_pts = to_points(hist['pdh'] - tick['ask'])
        if 0 < dist_pdh_pts < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDH ({int(dist_pdh_pts)} pts)"
            return contract

        entry = tick['ask']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        # SL Guard: Lebarin SL kalau kekecilan
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
        
        # SL Guard
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
