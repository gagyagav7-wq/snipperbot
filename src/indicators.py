import pandas as pd
import pandas_ta as ta
import pytz
import time
from datetime import datetime

# ==========================================
# ⚙️ KONFIGURASI SISTEM
# ==========================================

# 1. TIMEZONE & SESSION
WIB = pytz.timezone('Asia/Jakarta')
SESSION_START = 14  
SESSION_END = 23    

# 2. SAFETY THRESHOLDS
STALE_FEED_THRESHOLD     = 30   
CLOCK_DRIFT_LIMIT        = 30   
ABNORMAL_LEVEL_THRESHOLD = 100  
MAX_SPREAD               = 35   
EPS                      = 1e-9 

# 3. RISK MANAGEMENT
BUFFER_STOP_LEVEL = 10  
MIN_ABS_STOP_DIST = 50  
ATR_SL_MULT       = 1.5 
RR_RATIO          = 2.0 

# 4. STRATEGY PARAMS
MIN_BODY_ATR     = 0.3  # Filter candle doji
ADX_THRESHOLD    = 20   # [NEW] Minimal kekuatan trend
SAFE_DIST_ATR    = 0.5  # [NEW] Jarak aman ke PDH/PDL (Multiplier ATR)

def calculate_rules(data_pack):
    
    # --- 0. INISIALISASI KONTRAK ---
    contract = {
        "signal": "NO",
        "reason": "Initializing...",
        "setup": {},
        "timestamp": None,
        "tick": {},
        "df_5m": pd.DataFrame(),
        "meta": {"spread": 0, "session": False, "warning": None}
    }

    # ==========================================
    # 🛡️ GUARD 1: VALIDASI DATA & WAKTU
    # ==========================================
    if not data_pack or 'tick' not in data_pack:
        contract["reason"] = "Data Empty"
        return contract

    meta = data_pack.get("meta", {})
    tick_time_msc = meta.get("tick_time_msc")
    tick_time_sec = meta.get("tick_time")
    server_time   = meta.get("server_time")
    local_time    = time.time()
    broker_ts     = None

    if tick_time_msc is not None and tick_time_msc > 0:
        broker_ts = tick_time_msc / 1000.0
    elif tick_time_sec is not None and tick_time_sec > 0:
        broker_ts = float(tick_time_sec)

    if broker_ts is not None:
        data_lag = local_time - broker_ts
        if data_lag > STALE_FEED_THRESHOLD:
            contract["reason"] = f"BROKER LAG ({data_lag:.1f}s) - Check Connection"
            return contract
        if -10.0 < data_lag < -2.0:
            msg = f"Clock Drift Detected ({data_lag:.2f}s)"
            contract["meta"]["warning"] = msg
            print(f"⚠️ {msg}") 
        elif data_lag <= -10.0:
            contract["reason"] = f"CRITICAL: PC Clock Behind Broker ({data_lag:.1f}s). RESYNC TIME!"
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

    # ==========================================
    # 🛡️ GUARD 2: VALIDASI TICK & HISTORY
    # ==========================================
    tick = data_pack['tick']
    point = tick.get('point')
    digits = tick.get('digits')
    
    if tick.get('bid', 0) <= 0 or tick.get('ask', 0) <= 0:
        contract["reason"] = "Market Closed (Price 0)"
        return contract

    if point is None or point <= 0 or digits is None or digits < 1:
        contract["reason"] = "Invalid Point/Digits"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    hist = data_pack.get('history', {})
    
    if hist.get('pdh') is None or hist.get('pdl') is None:
        contract["reason"] = "History Missing (PDH/PDL)"
        return contract

    contract["df_5m"] = df_5m
    contract["tick"] = tick
    contract["meta"]["d1_time"] = hist.get("d1_time")

    if len(df_5m) < 60 or len(df_15m) < 200:
        contract["reason"] = "Not Enough Bars (Loading...)"
        return contract

    # ==========================================
    # 📊 3. KALKULASI INDIKATOR
    # ==========================================
    # M5 Indicators
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR']    = df_5m.ta.atr(length=14)
    df_5m['RSI']    = df_5m.ta.rsi(length=14)
    
    # M15 Indicators
    df_15m['EMA_50']  = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)
    # [NEW] ADX Filter (Trend Strength)
    adx_df = df_15m.ta.adx(length=14)
    if adx_df is not None and not adx_df.empty:
        # Pandas TA biasanya return 3 kolom (ADX, DMP, DMN). Kita ambil kolom pertama (ADX)
        df_15m['ADX'] = adx_df.iloc[:, 0] 
    else:
        df_15m['ADX'] = 0

    last_5m  = df_5m.iloc[-1]
    prev_5m  = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    if pd.isna(last_5m['ATR']) or pd.isna(last_15m['EMA_200']) or pd.isna(last_15m['ADX']):
        contract["reason"] = "Indicators Calculating (NaN)..."
        return contract

    # ==========================================
    # 🕒 4. CEK SESI & WAKTU
    # ==========================================
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

    # ==========================================
    # 🛑 5. FILTER KONDISI MARKET
    # ==========================================
    spread       = tick.get('spread', 999)
    stop_level   = tick.get('stop_level', 0)
    freeze_level = tick.get('freeze_level', 0)
    
    contract["meta"]["spread"] = spread

    if stop_level > ABNORMAL_LEVEL_THRESHOLD or freeze_level > ABNORMAL_LEVEL_THRESHOLD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Broker Chaos (Stop: {stop_level}, Freeze: {freeze_level})"
        return contract

    if spread > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"High Spread: {spread}"
        return contract

    # ==========================================
    # 📈 6. LOGIKA STRATEGI (Trend + Pattern + ADX)
    # ==========================================

    # A. Identifikasi Trend (Strong Trend Only) + ADX CHECK
    is_bull_trend = (last_15m['Close'] > last_15m['EMA_50']) and \
                    (last_15m['EMA_50'] > last_15m['EMA_200']) and \
                    (last_15m['ADX'] > ADX_THRESHOLD) # [NEW] Trend harus kuat

    is_bear_trend = (last_15m['Close'] < last_15m['EMA_50']) and \
                    (last_15m['EMA_50'] < last_15m['EMA_200']) and \
                    (last_15m['ADX'] > ADX_THRESHOLD) # [NEW] Trend harus kuat

    # B. Identifikasi Pattern (Engulfing Strict)
    body     = abs(last_5m['Close'] - last_5m['Open'])
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

    # ==========================================
    # 🚀 7. EKSEKUSI & VALIDASI LEVEL (ADAPTIVE)
    # ==========================================
    
    def to_points(val): return val / point

    # Hitung Jarak SL Minimal
    min_dist_req    = stop_level + freeze_level + spread + BUFFER_STOP_LEVEL
    min_sl_dist_pts = max(min_dist_req, MIN_ABS_STOP_DIST)

    # [NEW] Hitung Jarak Aman PDH/PDL secara Adaptif (ATR Based)
    # Kalau ATR 2.0 (200 point), safe dist jadi 100 point.
    # Kalau ATR 5.0 (500 point), safe dist jadi 250 point.
    adaptive_safe_dist_pts = to_points(last_5m['ATR'] * SAFE_DIST_ATR)

    # --- SETUP BUY ---
    if bull_engulf and is_bull_trend:
        dist_pdh_pts = to_points(hist['pdh'] - tick['ask'])
        
        # Cek Jarak PDH Adaptif
        if 0 < dist_pdh_pts < (adaptive_safe_dist_pts - EPS):
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDH ({int(dist_pdh_pts)} < {int(adaptive_safe_dist_pts)} pts)"
            return contract

        entry       = tick['ask']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        if to_points(sl_dist_raw) < min_sl_dist_pts:
            sl_dist_raw = min_sl_dist_pts * point
        
        sl = entry - sl_dist_raw
        tp = entry + (sl_dist_raw * RR_RATIO)
        
        contract["signal"] = "BUY"
        contract["reason"] = f"Bull Engulf + Strong Trend (ADX {int(last_15m['ADX'])})"
        contract["setup"] = {
            "action": "BUY",
            "entry":  round(entry, digits),
            "sl":     round(sl, digits),
            "tp":     round(tp, digits),
            "atr":    round(last_5m['ATR'], digits)
        }

    # --- SETUP SELL ---
    elif bear_engulf and is_bear_trend:
        dist_pdl_pts = to_points(tick['bid'] - hist['pdl'])
        
        # Cek Jarak PDL Adaptif
        if 0 < dist_pdl_pts < (adaptive_safe_dist_pts - EPS):
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDL ({int(dist_pdl_pts)} < {int(adaptive_safe_dist_pts)} pts)"
            return contract

        entry       = tick['bid']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        if to_points(sl_dist_raw) < min_sl_dist_pts:
            sl_dist_raw = min_sl_dist_pts * point

        sl = entry + sl_dist_raw
        tp = entry - (sl_dist_raw * RR_RATIO)
        
        contract["signal"] = "SELL"
        contract["reason"] = f"Bear Engulf + Strong Trend (ADX {int(last_15m['ADX'])})"
        contract["setup"] = {
            "action": "SELL",
            "entry":  round(entry, digits),
            "sl":     round(sl, digits),
            "tp":     round(tp, digits),
            "atr":    round(last_5m['ATR'], digits)
        }
    
    else:
        # Tambahan Info Kenapa Gak Setup (Optional, buat debugging)
        if bull_engulf and not is_bull_trend:
            contract["reason"] = f"Bull Pattern but Weak Trend (ADX {int(last_15m['ADX'])})"
        elif bear_engulf and not is_bear_trend:
            contract["reason"] = f"Bear Pattern but Weak Trend (ADX {int(last_15m['ADX'])})"
        else:
            contract["reason"] = "No Setup"

    return contract
