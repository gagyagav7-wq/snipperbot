import pandas as pd
import pandas_ta as ta
import pytz
import time
from datetime import datetime

# ==========================================
# ⚙️ KONFIGURASI SISTEM
# ==========================================
WIB = pytz.timezone('Asia/Jakarta')
SESSION_START = 14  
SESSION_END = 23    

# Safety & Risk
STALE_FEED_THRESHOLD     = 30   
CLOCK_DRIFT_LIMIT        = 30   
ABNORMAL_LEVEL_THRESHOLD = 100  
MAX_SPREAD               = 35   
EPS                      = 1e-9 
BUFFER_STOP_LEVEL        = 10  
MIN_ABS_STOP_DIST        = 50  
ATR_SL_MULT              = 1.5 
RR_RATIO                 = 2.0 

# Strategy Params
MIN_BODY_ATR        = 0.3  
ADX_THRESHOLD       = 20   
SAFE_DIST_ATR       = 0.5  
MIN_SAFE_DIST_PRICE = 0.50 
MAX_SAFE_DIST_PRICE = 2.00 

def calculate_rules(data_pack):
    
    contract = {
        "signal": "NO",
        "reason": "Initializing...",
        "setup": {},
        "timestamp": None,
        "tick": {},
        "df_5m": pd.DataFrame(),
        "meta": {"spread": 0, "session": False, "warnings": []}
    }

    # --- GUARD 1: VALIDASI DATA & WAKTU ---
    if not data_pack or 'tick' not in data_pack:
        contract["reason"] = "Data Empty"
        return contract

    meta = data_pack.get("meta", {})
    tick_time_msc = meta.get("tick_time_msc")
    tick_time_sec = meta.get("tick_time")
    server_time   = meta.get("server_time")
    local_time    = time.time()
    broker_ts     = None

    # [CRITICAL CHECK] Timestamp Logic dengan Fallback
    if tick_time_msc is not None and tick_time_msc > 0:
        broker_ts = tick_time_msc / 1000.0
    elif tick_time_sec is not None and tick_time_sec > 0:
        broker_ts = float(tick_time_sec)

    if broker_ts is not None:
        data_lag = local_time - broker_ts
        if data_lag > STALE_FEED_THRESHOLD:
            contract["reason"] = f"BROKER LAG ({data_lag:.1f}s)"
            return contract
        if -10.0 < data_lag < -2.0:
            contract["meta"]["warnings"].append(f"Clock Drift ({data_lag:.2f}s)")
        elif data_lag <= -10.0:
            contract["reason"] = f"CRITICAL: Clock Behind ({data_lag:.1f}s)"
            return contract
    else:
        contract["reason"] = "CRITICAL: Invalid Broker Timestamp (None/0)"
        return contract

    if server_time is not None:
        drift = local_time - float(server_time)
        drift_int = int(round(drift))
        if abs(drift_int) > 5: contract["meta"]["system_drift"] = drift_int
        if abs(drift_int) > CLOCK_DRIFT_LIMIT:
             contract["reason"] = f"System Clock Mismatch ({drift_int}s)"
             return contract

    # --- GUARD 2: VALIDASI TICK & HISTORY ---
    tick = data_pack['tick']
    point = tick.get('point')
    digits = tick.get('digits')
    
    if tick.get('bid', 0) <= 0 or tick.get('ask', 0) <= 0:
        contract["reason"] = "Market Closed"
        return contract

    if point is None or point <= 0 or digits is None or digits < 1:
        contract["reason"] = "Invalid Point/Digits"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    hist = data_pack.get('history', {})
    
    if hist.get('pdh') is None or hist.get('pdl') is None:
        contract["reason"] = "History Missing"
        return contract

    contract["df_5m"] = df_5m
    contract["tick"] = tick
    contract["meta"]["d1_time"] = hist.get("d1_time")

    if len(df_5m) < 60 or len(df_15m) < 200:
        contract["reason"] = "Not Enough Bars"
        return contract

    # --- 3. INDIKATOR ---
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR']    = df_5m.ta.atr(length=14)
    df_5m['RSI']    = df_5m.ta.rsi(length=14)
    
    df_15m['EMA_50']  = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)
    
    # ADX Extraction
    adx_df = df_15m.ta.adx(length=14)
    df_15m['ADX'] = 0; df_15m['DMP'] = 0; df_15m['DMN'] = 0
    adx_columns_found = False

    if adx_df is not None and not adx_df.empty:
        col_adx = [c for c in adx_df.columns if c.startswith("ADX")]
        col_dmp = [c for c in adx_df.columns if c.startswith("DMP")]
        col_dmn = [c for c in adx_df.columns if c.startswith("DMN")]
        
        if col_adx and col_dmp and col_dmn:
            df_15m['ADX'] = adx_df[col_adx[0]]
            df_15m['DMP'] = adx_df[col_dmp[0]]
            df_15m['DMN'] = adx_df[col_dmn[0]]
            adx_columns_found = True
        else:
            contract["meta"]["warnings"].append("ADX Cols Missing")
    else:
        contract["meta"]["warnings"].append("ADX Calc Failed")

    last_5m  = df_5m.iloc[-1]
    prev_5m  = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    adx_ok = adx_columns_found and \
             pd.notna(last_15m['ADX']) and \
             pd.notna(last_15m['DMP']) and \
             pd.notna(last_15m['DMN'])

    if (pd.isna(last_5m['ATR']) or 
        pd.isna(last_15m['EMA_200']) or 
        not adx_ok): 
        contract["reason"] = "Indicators Calculating (NaN)..."
        return contract

    # --- 4. TIMEZONE ---
    try:
        wib_time = last_5m.name.tz_convert(WIB)
        contract["timestamp"] = wib_time
        if not (SESSION_START <= wib_time.hour < SESSION_END):
            contract["meta"]["session"] = False
            contract["reason"] = f"Outside Killzone ({wib_time.hour:02d}:00)"
            return contract
        contract["meta"]["session"] = True
    except Exception as e:
        contract["reason"] = f"Time Error: {e}"
        return contract

    # --- 5. MARKET FILTER ---
    spread = tick.get('spread', 999)
    stop_level = tick.get('stop_level', 0)
    freeze_level = tick.get('freeze_level', 0)
    contract["meta"]["spread"] = spread

    if stop_level > ABNORMAL_LEVEL_THRESHOLD or freeze_level > ABNORMAL_LEVEL_THRESHOLD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Broker Chaos (Stop: {stop_level})"
        return contract

    if spread > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"High Spread: {spread}"
        return contract

    # --- 6. STRATEGY ---
    strong_bull = (last_15m['Close'] > last_15m['EMA_50']) and \
                  (last_15m['EMA_50'] > last_15m['EMA_200']) and \
                  (last_15m['ADX'] > ADX_THRESHOLD) and \
                  (last_15m['DMP'] > last_15m['DMN'])

    strong_bear = (last_15m['Close'] < last_15m['EMA_50']) and \
                  (last_15m['EMA_50'] < last_15m['EMA_200']) and \
                  (last_15m['ADX'] > ADX_THRESHOLD) and \
                  (last_15m['DMN'] > last_15m['DMP'])

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

    # --- 7. EKSEKUSI ---
    def to_points(val): return val / point

    min_dist_req = stop_level + freeze_level + spread + BUFFER_STOP_LEVEL
    min_sl_dist_pts = max(min_dist_req, MIN_ABS_STOP_DIST)

    # Adaptive Safe Distance
    raw_safe_dist_price = last_5m['ATR'] * SAFE_DIST_ATR
    safe_dist_price = max(MIN_SAFE_DIST_PRICE, min(MAX_SAFE_DIST_PRICE, raw_safe_dist_price))
    adaptive_safe_dist_pts = to_points(safe_dist_price)
    
    contract["meta"]["safe_dist_pts"] = adaptive_safe_dist_pts
    contract["meta"]["safe_dist_price"] = safe_dist_price

    # ---------------------------------------------------------
    # 👇 EXPORT DATA LOGGER DI SINI (SEBELUM LOGIC RETURN) 👇
    # ---------------------------------------------------------
    
    input_meta = data_pack.get("meta", {})
    contract["meta"]["tick_time"]     = input_meta.get("tick_time")
    contract["meta"]["tick_time_msc"] = input_meta.get("tick_time_msc")
    contract["meta"]["server_time"]   = input_meta.get("server_time")

    try:
        contract["meta"]["candle"] = {
            "close": float(last_5m.get('Close', 0)),
            "high":  float(last_5m.get('High', 0)),
            "low":   float(last_5m.get('Low', 0)),
            "time":  str(last_5m.name)
        }
    except:
        contract["meta"]["candle"] = {}

    try:
        contract["meta"]["indicators"] = {
            "rsi": round(float(last_5m.get('RSI', 0)), 2),
            "atr": round(float(last_5m.get('ATR', 0)), 5),
            "adx": round(float(last_15m.get('ADX', 0)), 2),
            "dmp": round(float(last_15m.get('DMP', 0)), 2),
            "dmn": round(float(last_15m.get('DMN', 0)), 2),
            "ema50_m15": round(float(last_15m.get('EMA_50', 0)), 2),
            "ema200_m15": round(float(last_15m.get('EMA_200', 0)), 2)
        }
    except Exception:
        contract["meta"]["indicators"] = {}

    # ---------------------------------------------------------
    # LOGIC SINYAL BUY/SELL
    # ---------------------------------------------------------

    # -- SETUP BUY --
    if bull_engulf and strong_bull:
        dist_pdh_pts = to_points(hist['pdh'] - tick['ask'])
        
        if 0 < dist_pdh_pts < (adaptive_safe_dist_pts - EPS):
            contract["signal"] = "SKIP"
            contract["meta"]["dist_pdh_pts"] = dist_pdh_pts
            contract["meta"]["dist_pdh_price"] = dist_pdh_pts * point
            contract["reason"] = f"Near PDH ({dist_pdh_pts:.1f} < {adaptive_safe_dist_pts:.1f} pts)"
            return contract

        entry = tick['ask']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        if to_points(sl_dist_raw) < min_sl_dist_pts: sl_dist_raw = min_sl_dist_pts * point
        
        contract["signal"] = "BUY"
        contract["reason"] = f"Bull Engulf + Strong Trend (ADX {int(last_15m['ADX'])})"
        contract["setup"] = {
            "action": "BUY", "entry": round(entry, digits),
            "sl": round(entry - sl_dist_raw, digits),
            "tp": round(entry + (sl_dist_raw * RR_RATIO), digits),
            "atr": round(last_5m['ATR'], digits)
        }

    # -- SETUP SELL --
    elif bear_engulf and strong_bear:
        dist_pdl_pts = to_points(tick['bid'] - hist['pdl'])
        
        if 0 < dist_pdl_pts < (adaptive_safe_dist_pts - EPS):
            contract["signal"] = "SKIP"
            contract["meta"]["dist_pdl_pts"] = dist_pdl_pts
            contract["meta"]["dist_pdl_price"] = dist_pdl_pts * point
            contract["reason"] = f"Near PDL ({dist_pdl_pts:.1f} < {adaptive_safe_dist_pts:.1f} pts)"
            return contract

        entry = tick['bid']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        if to_points(sl_dist_raw) < min_sl_dist_pts: sl_dist_raw = min_sl_dist_pts * point

        contract["signal"] = "SELL"
        contract["reason"] = f"Bear Engulf + Strong Trend (ADX {int(last_15m['ADX'])})"
        contract["setup"] = {
            "action": "SELL", "entry": round(entry, digits),
            "sl": round(entry + sl_dist_raw, digits),
            "tp": round(entry - (sl_dist_raw * RR_RATIO), digits),
            "atr": round(last_5m['ATR'], digits)
        }
    
    else:
        adx_val = int(last_15m['ADX']) if adx_ok else 0
        if (bull_engulf or bear_engulf) and not adx_ok:
            contract["reason"] = "Pattern Found but ADX Missing"
        elif bull_engulf and not strong_bull:
            contract["reason"] = f"Bull Pattern but Weak Trend (ADX {adx_val})"
        elif bear_engulf and not strong_bear:
            contract["reason"] = f"Bear Pattern but Weak Trend (ADX {adx_val})"
        else:
            contract["reason"] = "No Setup"

    return contract
