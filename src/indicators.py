import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime

# --- KONFIGURASI ---
WIB = pytz.timezone('Asia/Jakarta')

# Market Hours (WIB) - Approx London Open to NY Mid
SESSION_START = 14  
SESSION_END = 23    

# Risk & Strategy Config
MAX_SPREAD = 35         # Max Spread in Points
ATR_SL_MULT = 1.5       # SL Multiplier
RR_RATIO = 2.0          # Risk Reward
MIN_BODY_ATR = 0.3      # Candle Body vs ATR Filter
BUFFER_STOP_LEVEL = 10  # Tambahan jarak (points) dari minimum broker

def calculate_rules(data_pack):
    # ---------------------------------------------------------
    # 0. SAFEGUARD: DEFAULT CONTRACT
    # ---------------------------------------------------------
    contract = {
        "signal": "NO",
        "reason": "Initializing...",
        "setup": {},
        "timestamp": None,
        "tick": {},
        "df_5m": pd.DataFrame(),
        "meta": {"spread": 0, "session": False}
    }

    # 1. CRITICAL DATA VALIDATION (Anti Crash)
    if not data_pack or 'tick' not in data_pack:
        contract["reason"] = "Data Empty"
        return contract

    tick = data_pack['tick']
    
    # GUARD: Kalau Point/Digits 0/None (Server error/Market tutup) -> LOCK
    if not tick.get('point') or tick.get('point') <= 0:
        contract["reason"] = "CRITICAL: Invalid Point Value"
        return contract
        
    if tick.get('digits') is None:
        contract["reason"] = "CRITICAL: Invalid Digits Value"
        return contract

    # 2. LOAD DATA
    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    hist = data_pack.get('history', {})
    contract["df_5m"] = df_5m
    contract["tick"] = tick

    # Guard: Data Kurang
    if len(df_5m) < 60 or len(df_15m) < 200: # Butuh 200 candle buat EMA 200
        contract["reason"] = "Not Enough Data (Need 200+)"
        return contract

    # ---------------------------------------------------------
    # 3. INDICATOR CALCULATION
    # ---------------------------------------------------------
    # M5
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    
    # M15
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)

    last_5m = df_5m.iloc[-1]
    prev_5m = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-1]

    # Guard: NaN Indicators (Baru start)
    if pd.isna(last_5m['ATR']) or pd.isna(last_15m['EMA_200']):
        contract["reason"] = "Indicators Calculating..."
        return contract

    # ---------------------------------------------------------
    # 4. TIMEZONE & SESSION
    # ---------------------------------------------------------
    try:
        ts = last_5m.name
        # Paksa UTC kalau naive (karena server kirim Epoch UTC)
        if ts.tzinfo is None: ts = ts.replace(tzinfo=pytz.utc)
        
        # Convert ke WIB
        wib_time = ts.astimezone(WIB)
        contract["timestamp"] = wib_time
        
        # Session Filter
        if not (SESSION_START <= wib_time.hour < SESSION_END):
            contract["meta"]["session"] = False
            contract["reason"] = f"Outside Killzone ({wib_time.hour:02d}:00)"
            return contract
            
        contract["meta"]["session"] = True
    except Exception as e:
        contract["reason"] = f"Timezone Error: {e}"
        return contract

    # ---------------------------------------------------------
    # 5. SPREAD FILTER
    # ---------------------------------------------------------
    spread = tick.get('spread', 999)
    contract["meta"]["spread"] = spread
    
    if spread > MAX_SPREAD:
        contract["signal"] = "SKIP"
        contract["reason"] = f"Spread {spread} > {MAX_SPREAD}"
        return contract

    # ---------------------------------------------------------
    # 6. TREND FILTER (STRONG TREND ONLY)
    # ---------------------------------------------------------
    # Bullish: Harga > EMA50 > EMA200
    is_bull_trend = (last_15m['Close'] > last_15m['EMA_50']) and (last_15m['EMA_50'] > last_15m['EMA_200'])
    
    # Bearish: Harga < EMA50 < EMA200
    is_bear_trend = (last_15m['Close'] < last_15m['EMA_50']) and (last_15m['EMA_50'] < last_15m['EMA_200'])

    # ---------------------------------------------------------
    # 7. PATTERN RECOGNITION (STRICT QUALITY)
    # ---------------------------------------------------------
    body = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    # Bullish Engulfing Strict
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['Close'] > prev_5m['High']) # Confirm Breakout

    # Bearish Engulfing Strict
    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > prev_5m['Close']) and \
                  (last_5m['Close'] < prev_5m['Open']) and \
                  (body > min_body) and \
                  (last_5m['Close'] < prev_5m['Low']) # Confirm Breakout

    # ---------------------------------------------------------
    # 8. EXECUTION LOGIC (POINTS BASED)
    # ---------------------------------------------------------
    point = tick['point']
    digits = tick['digits']
    
    # Helper: Convert Price Diff to Points
    def to_points(price_diff): return price_diff / point

    # Validasi Stop Level dari Broker
    stop_level_pts = tick.get('stop_level', 0)
    # Minimum jarak SL dari Entry (StopLevel + Spread + Buffer 10 pts)
    min_sl_dist_pts = stop_level_pts + spread + BUFFER_STOP_LEVEL
    
    # -- BUY SETUP --
    if bull_engulf and is_bull_trend:
        # Cek Jarak PDH
        dist_pdh_pts = to_points(hist['pdh'] - tick['ask']) 
        if 0 < dist_pdh_pts < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Resistance PDH too close ({int(dist_pdh_pts)} pts)"
            return contract

        entry = tick['ask']
        # SL = Low Candle - Buffer ATR
        raw_sl_dist = last_5m['ATR'] * ATR_SL_MULT
        
        # Guard: Kalau SL kekecilan (kurang dari syarat broker), lebarin.
        if to_points(raw_sl_dist) < min_sl_dist_pts:
            raw_sl_dist = min_sl_dist_pts * point
        
        sl = entry - raw_sl_dist
        tp = entry + (raw_sl_dist * RR_RATIO)
        
        contract["signal"] = "BUY"
        contract["reason"] = "Valid Bullish Engulfing"
        contract["setup"] = {
            "action": "BUY",
            "entry": round(entry, digits),
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "atr": round(last_5m['ATR'], digits)
        }

    # -- SELL SETUP --
    elif bear_engulf and is_bear_trend:
        # Cek Jarak PDL
        dist_pdl_pts = to_points(tick['bid'] - hist['pdl'])
        if 0 < dist_pdl_pts < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Support PDL too close ({int(dist_pdl_pts)} pts)"
            return contract

        entry = tick['bid']
        # SL = High Candle + Buffer ATR
        raw_sl_dist = last_5m['ATR'] * ATR_SL_MULT

        # Guard: Stop Level
        if to_points(raw_sl_dist) < min_sl_dist_pts:
            raw_sl_dist = min_sl_dist_pts * point

        sl = entry + raw_sl_dist
        tp = entry - (raw_sl_dist * RR_RATIO)
        
        contract["signal"] = "SELL"
        contract["reason"] = "Valid Bearish Engulfing"
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
