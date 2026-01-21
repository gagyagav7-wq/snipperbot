import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime

# --- KONFIGURASI ---
WIB = pytz.timezone('Asia/Jakarta')
SESSION_START = 14 
SESSION_END = 23
MAX_SPREAD = 35 
MIN_BODY_ATR = 0.3
SAFE_DIST_POINTS = 200 
ATR_SL_MULT = 1.5
RR_RATIO = 2.0

def calculate_rules(data_pack):
    # ---------------------------------------------------------
    # 0. CONTRACT INITIALIZATION
    # ---------------------------------------------------------
    contract = {
        "signal": "NO",
        "reason": "Init",
        "setup": {},
        "timestamp": None,
        "tick": {},
        "df_5m": pd.DataFrame(),
        "meta": {}
    }

    # 1. CRITICAL DATA GUARD
    if not data_pack or 'tick' not in data_pack:
        contract["reason"] = "Data Empty"
        return contract

    tick = data_pack['tick']
    
    # Kunci Mati: Kalau point/digit 0 atau None, matikan bot.
    if not tick.get('point') or not tick.get('digits'):
        contract["reason"] = "CRITICAL: Tick Point/Digits Missing"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    hist = data_pack.get('history', {})
    contract["df_5m"] = df_5m
    contract["tick"] = tick

    # ---------------------------------------------------------
    # 2. TIME & SESSION (Epoch Based)
    # ---------------------------------------------------------
    try:
        # Server kirim epoch (int/float), pasti UTC.
        last_ts = df_5m.index[-1] 
        # Convert ke Datetime UTC Aware
        utc_dt = pd.to_datetime(last_ts, unit='s').replace(tzinfo=pytz.utc)
        # Convert ke WIB
        wib_dt = utc_dt.astimezone(WIB)
        
        contract["timestamp"] = wib_dt
        contract["meta"]["session"] = False

        if not (SESSION_START <= wib_dt.hour < SESSION_END):
            contract["reason"] = f"Outside Session ({wib_dt.hour}:00)"
            return contract
            
        contract["meta"]["session"] = True
    except Exception as e:
        contract["reason"] = f"Time Error: {e}"
        return contract

    # ---------------------------------------------------------
    # 3. INDICATORS
    # ---------------------------------------------------------
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200) # Strong Trend Filter

    last_5m = df_5m.iloc[-1]
    prev_5m = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    if pd.isna(last_5m['ATR']):
        contract["reason"] = "Indikator Loading..."
        return contract

    # ---------------------------------------------------------
    # 4. FILTERS (Spread & Trend)
    # ---------------------------------------------------------
    if tick['spread'] > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Spread {tick['spread']} > {MAX_SPREAD}"
        return contract

    # Strong Trend Definition (EMA 50 & 200)
    # Bull: Harga > EMA50 DAN EMA50 > EMA200
    bull_trend_15m = (last_15m['Close'] > last_15m['EMA_50']) and (last_15m['EMA_50'] > last_15m['EMA_200'])
    
    # Bear: Harga < EMA50 DAN EMA50 < EMA200
    bear_trend_15m = (last_15m['Close'] < last_15m['EMA_50']) and (last_15m['EMA_50'] < last_15m['EMA_200'])

    # ---------------------------------------------------------
    # 5. PATTERN RECOGNITION (Confirm Close)
    # ---------------------------------------------------------
    body = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    # Bullish Engulfing Valid:
    # 1. Candle Hijau nelen Merah
    # 2. Body gede (bukan doji)
    # 3. RSI aman (<70)
    # 4. CONFIRM: Close sekarang > High candle sebelumnya (Breakout micro structure)
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['RSI'] < 70) and \
                  (last_5m['Close'] > prev_5m['High']) 

    # Bearish Engulfing Valid:
    # 4. CONFIRM: Close sekarang < Low candle sebelumnya
    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > prev_5m['Close']) and \
                  (last_5m['Close'] < prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['RSI'] > 30) and \
                  (last_5m['Close'] < prev_5m['Low'])

    # ---------------------------------------------------------
    # 6. EXECUTION LOGIC
    # ---------------------------------------------------------
    point = tick['point']
    digits = tick['digits']
    stop_level = tick.get('stop_level', 0) # Ambil dari broker
    
    # Safety Buffer buat Stop Level (Stop Level + Spread + 10 points)
    min_sl_dist = (stop_level * point) + (tick['spread'] * point) + (10 * point)

    def to_points(val): return val / point

    # --- BUY SETUP ---
    if bull_engulf and bull_trend_15m:
        # PDH Check
        dist_pdh = to_points(hist['pdh'] - tick['ask']) # Positif = Belum breakout
        if 0 < dist_pdh < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDH Resistance ({int(dist_pdh)} pts)"
            return contract

        entry = tick['ask']
        sl_dist = last_5m['ATR'] * ATR_SL_MULT
        
        # Guard Stop Level
        if sl_dist < min_sl_dist: sl_dist = min_sl_dist
        
        sl = entry - sl_dist
        tp = entry + (sl_dist * RR_RATIO)
        
        contract["signal"] = "BUY"
        contract["reason"] = "Strong Bullish Engulfing + Trend"
        contract["setup"] = {
            "action": "BUY",
            "entry": round(entry, digits),
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "atr": round(last_5m['ATR'], digits)
        }

    # --- SELL SETUP ---
    elif bear_engulf and bear_trend_15m:
        # PDL Check
        dist_pdl = to_points(tick['bid'] - hist['pdl']) # Positif = Belum breakdown
        if 0 < dist_pdl < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Near PDL Support ({int(dist_pdl)} pts)"
            return contract

        entry = tick['bid']
        sl_dist = last_5m['ATR'] * ATR_SL_MULT
        
        # Guard Stop Level
        if sl_dist < min_sl_dist: sl_dist = min_sl_dist

        sl = entry + sl_dist
        tp = entry - (sl_dist * RR_RATIO)
        
        contract["signal"] = "SELL"
        contract["reason"] = "Strong Bearish Engulfing + Trend"
        contract["setup"] = {
            "action": "SELL",
            "entry": round(entry, digits),
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "atr": round(last_5m['ATR'], digits)
        }

    else:
        contract["reason"] = "No Valid Setup"

    return contract
