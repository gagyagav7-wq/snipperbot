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
SESSION_START = 14  # 14.00 WIB (London Open Approx)
SESSION_END = 23    # 23.00 WIB (NY Session Mid)

# 2. SAFETY THRESHOLDS (GUARDRAILS)
STALE_FEED_THRESHOLD     = 30   # Detik (Batas data basi)
CLOCK_DRIFT_LIMIT        = 30   # Detik (Batas beda jam PC vs Server)
ABNORMAL_LEVEL_THRESHOLD = 100  # Points (Stop/Freeze level kegedean = Chaos)
MAX_SPREAD               = 35   # Points
EPS                      = 1e-9 # Epsilon untuk komparasi float presisi

# 3. RISK MANAGEMENT
BUFFER_STOP_LEVEL = 10  # Buffer tambahan jarak SL
MIN_ABS_STOP_DIST = 50  # Jarak SL minimal absolut (Points)
ATR_SL_MULT       = 1.5 # Multiplier ATR untuk SL
RR_RATIO          = 2.0 # Risk Reward Ratio

# 4. STRATEGY PARAMS
SAFE_DIST_POINTS = 200  # Jarak aman ke PDH/PDL
MIN_BODY_ATR     = 0.3  # Filter candle doji

def calculate_rules(data_pack):
    """
    Inti logika trading: Mengolah data mentah menjadi keputusan trading (Signal).
    Output: Dictionary 'contract' yang berisi Signal, Reason, dan Setup.
    """
    
    # --- 0. INISIALISASI KONTRAK DEFAULT ---
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
    # 🛡️ GUARD 1: VALIDASI DATA KRITIS & WAKTU
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

    # A. Tentukan Timestamp Broker (Prioritas Milidetik)
    if tick_time_msc is not None and tick_time_msc > 0:
        broker_ts = tick_time_msc / 1000.0
    elif tick_time_sec is not None and tick_time_sec > 0:
        broker_ts = float(tick_time_sec)

    # B. Cek Freshness Data (Stale Feed & Future Tick)
    if broker_ts is not None:
        data_lag = local_time - broker_ts
        
        # Cek 1: Data Basi (> 30 detik)
        if data_lag > STALE_FEED_THRESHOLD:
            contract["reason"] = f"BROKER LAG ({data_lag:.1f}s) - Check Connection"
            return contract
            
        # Cek 2: Clock Drift / Future Tick
        # Zone Warning (-2s s/d -10s)
        if -10.0 < data_lag < -2.0:
            msg = f"Clock Drift Detected ({data_lag:.2f}s)"
            contract["meta"]["warning"] = msg
            print(f"⚠️ {msg}") 
            
        # Zone Kill (< -10s) -> Waktu PC telat parah
        elif data_lag <= -10.0:
            contract["reason"] = f"CRITICAL: PC Clock Behind Broker ({data_lag:.1f}s). RESYNC TIME!"
            return contract
    else:
        # [BANK-GRADE UPDATE] Kalau tidak ada timestamp, matikan bot.
        contract["reason"] = "CRITICAL: Invalid Broker Timestamp (None/0)"
        return contract

    # C. Cek Integritas Jam Sistem (Server Script vs Indicators Script)
    if server_time is not None:
        drift = local_time - float(server_time)
        drift_int = int(round(drift))
        
        if abs(drift_int) > 5: 
            contract["meta"]["system_drift"] = drift_int
            
        if abs(drift_int) > CLOCK_DRIFT_LIMIT:
             contract["reason"] = f"System Clock Mismatch ({drift_int}s)"
             return contract

    # ==========================================
    # 🛡️ GUARD 2: VALIDASI TICK & HISTORY
    # ==========================================

    tick = data_pack['tick']
    point = tick.get('point')
    digits = tick.get('digits')
    
    # Cek Market Tutup / Glitch
    if tick.get('bid', 0) <= 0 or tick.get('ask', 0) <= 0:
        contract["reason"] = "Market Closed (Price 0)"
        return contract

    # Cek Validitas Instrumen
    if point is None or point <= 0 or digits is None or digits < 1:
        contract["reason"] = "Invalid Point/Digits"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    hist = data_pack.get('history', {})
    
    # Cek Kelengkapan History
    if hist.get('pdh') is None or hist.get('pdl') is None:
        contract["reason"] = "History Missing (PDH/PDL)"
        return contract

    # Populate Contract Dasar
    contract["df_5m"] = df_5m
    contract["tick"] = tick
    contract["meta"]["d1_time"] = hist.get("d1_time")

    # Cek Jumlah Candle
    if len(df_5m) < 60 or len(df_15m) < 200:
        contract["reason"] = "Not Enough Bars (Loading...)"
        return contract

    # ==========================================
    # 📊 3. KALKULASI INDIKATOR
    # ==========================================
    
    # Timeframe M5
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR']    = df_5m.ta.atr(length=14)
    df_5m['RSI']    = df_5m.ta.rsi(length=14)
    
    # Timeframe M15
    df_15m['EMA_50']  = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)

    # Ambil Data Terakhir
    last_5m  = df_5m.iloc[-1]
    prev_5m  = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    # Guard NaN (Indikator belum siap)
    if pd.isna(last_5m['ATR']) or pd.isna(last_15m['EMA_200']):
        contract["reason"] = "Indicators Calculating (NaN)..."
        return contract

    # ==========================================
    # 🕒 4. CEK SESI & WAKTU (Timezone)
    # ==========================================
    try:
        # Asumsi index sudah UTC Aware dari data_loader
        ts = last_5m.name
        
        # Fallback safety convert
        if isinstance(ts, (int, float)):
            utc_time = pd.to_datetime(ts, unit='s', utc=True)
        else:
            utc_time = pd.to_datetime(ts).tz_localize('UTC') if ts.tzinfo is None else ts

        wib_time = utc_time.astimezone(WIB)
        contract["timestamp"] = wib_time
        
        # Killzone Filter
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

    # Cek Kondisi Broker Abnormal (News/Chaos)
    if stop_level > ABNORMAL_LEVEL_THRESHOLD or freeze_level > ABNORMAL_LEVEL_THRESHOLD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Broker Restricted (Stop: {stop_level}, Freeze: {freeze_level})"
        return contract

    # Cek Spread Lebar
    if spread > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"High Spread: {spread}"
        return contract

    # ==========================================
    # 📈 6. LOGIKA STRATEGI (Trend & Pattern)
    # ==========================================

    # A. Identifikasi Trend (Strong Trend Only)
    bull_trend = (last_15m['Close'] > last_15m['EMA_50']) and (last_15m['EMA_50'] > last_15m['EMA_200'])
    bear_trend = (last_15m['Close'] < last_15m['EMA_50']) and (last_15m['EMA_50'] < last_15m['EMA_200'])

    # B. Identifikasi Pattern (Engulfing Strict)
    body     = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    # Syarat: Candle nelen prev + Body Valid + Break High/Low + RSI Filter
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
    # 🚀 7. EKSEKUSI & VALIDASI LEVEL
    # ==========================================
    
    def to_points(val): return val / point  # Return float, jangan dibuletin di sini

    # Hitung Jarak SL Minimal (Sesuai aturan Broker)
    min_dist_req    = stop_level + freeze_level + spread + BUFFER_STOP_LEVEL
    min_sl_dist_pts = max(min_dist_req, MIN_ABS_STOP_DIST)

    # --- SETUP BUY ---
    if bull_engulf and bull_trend:
        # Cek Jarak ke Resistance (PDH)
        dist_pdh_pts = to_points(hist['pdh'] - tick['ask'])
        
        # Logic: Kalau belum breakout (positif) DAN jarak terlalu dekat -> SKIP
        if 0 < dist_pdh_pts < (SAFE_DIST_POINTS - EPS):
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDH Resistance ({int(dist_pdh_pts)} pts)"
            return contract

        # Hitung Entry & SL/TP
        entry       = tick['ask']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        # Koreksi SL jika terlalu sempit
        if to_points(sl_dist_raw) < min_sl_dist_pts:
            sl_dist_raw = min_sl_dist_pts * point
        
        sl = entry - sl_dist_raw
        tp = entry + (sl_dist_raw * RR_RATIO)
        
        contract["signal"] = "BUY"
        contract["reason"] = "Bullish Engulfing + Trend"
        contract["setup"] = {
            "action": "BUY",
            "entry":  round(entry, digits),
            "sl":     round(sl, digits),
            "tp":     round(tp, digits),
            "atr":    round(last_5m['ATR'], digits)
        }

    # --- SETUP SELL ---
    elif bear_engulf and bear_trend:
        # Cek Jarak ke Support (PDL)
        dist_pdl_pts = to_points(tick['bid'] - hist['pdl'])
        
        if 0 < dist_pdl_pts < (SAFE_DIST_POINTS - EPS):
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDL Support ({int(dist_pdl_pts)} pts)"
            return contract

        # Hitung Entry & SL/TP
        entry       = tick['bid']
        sl_dist_raw = last_5m['ATR'] * ATR_SL_MULT
        
        # Koreksi SL
        if to_points(sl_dist_raw) < min_sl_dist_pts:
            sl_dist_raw = min_sl_dist_pts * point

        sl = entry + sl_dist_raw
        tp = entry - (sl_dist_raw * RR_RATIO)
        
        contract["signal"] = "SELL"
        contract["reason"] = "Bearish Engulfing + Trend"
        contract["setup"] = {
            "action": "SELL",
            "entry":  round(entry, digits),
            "sl":     round(sl, digits),
            "tp":     round(tp, digits),
            "atr":    round(last_5m['ATR'], digits)
        }
    
    else:
        contract["reason"] = "No Valid Setup"

    return contract
