import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime

# --- KONFIGURASI HARDCODED (Bisa pindah ke .env nanti) ---
SESSION_START = 14  # Jam 14.00 WIB (London Open)
SESSION_END = 23    # Jam 23.00 WIB (Pertengahan NY)
MAX_SPREAD = 35     # Max Spread (Points)
MIN_BODY_ATR = 0.3  # Minimal body candle 0.3x ATR (Anti Doji)
SAFE_DIST_POINTS = 200 # Jarak aman ke PDH/PDL (Points)

def calculate_rules(data_pack):
    # 1. DATA GUARD (Anti Error)
    if data_pack is None or 'm5' not in data_pack:
        return {"signal": "NO", "reason": "Data Empty"}
        
    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    tick = data_pack['tick']
    hist = data_pack['history']

    # Pastikan data cukup buat hitung indikator
    if len(df_5m) < 60 or len(df_15m) < 60:
        return {"signal": "NO", "reason": "Not Enough Data for Indicators"}

    # 2. HITUNG INDIKATOR
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200)

    # Ambil Candle Closed Terakhir
    last_5m = df_5m.iloc[-1]
    last_15m = df_15m.iloc[-1]
    
    # Guard NaN (Indikator belum ke-load sempurna)
    if pd.isna(last_5m['ATR']) or pd.isna(last_5m['EMA_50']):
        return {"signal": "NO", "reason": "Indicators Loading..."}

    # --- 3. SESSION FILTER (KILLZONES) ---
    # Convert epoch index ke WIB
    wib = pytz.timezone('Asia/Jakarta')
    candle_time = last_5m.name.tz_localize('UTC').astimezone(wib)
    hour = candle_time.hour
    
    # Filter Jam: Trade cuma di jam likuid
    if not (SESSION_START <= hour < SESSION_END):
        return {"signal": "NO", "reason": f"Outside Session ({hour}:00)"}

    # --- 4. SPREAD FILTER ---
    if tick['spread'] > MAX_SPREAD:
        return {"signal": "SKIP", "reason": f"High Spread: {tick['spread']}"}

    # --- 5. LOGIC PATTERN & TREND ---
    # Trend Filter (M15)
    trend_15m = "BULL" if last_15m['Close'] > last_15m['EMA_50'] else "BEAR"
    
    # Pattern Quality (M5)
    body_size = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    # Engulfing Definitions
    prev_5m = df_5m.iloc[-2]
    
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open']) and \
                  (body_size > min_body) # Quality Check

    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > prev_5m['Close']) and \
                  (last_5m['Close'] < prev_5m['Open']) and \
                  (body_size > min_body) # Quality Check

    # --- 6. SIGNAL GENERATION + CONTEXT CHECK ---
    signal = "NO"
    reason = "No Pattern"
    setup = {}
    
    # Helper convert harga ke point distance
    def get_point_dist(price1, price2):
        return (price1 - price2) / tick['point']

    # --- BUY LOGIC ---
    if bull_engulf and trend_15m == "BULL":
        # Cek PDH (Resistance)
        dist_to_pdh = get_point_dist(hist['pdh'], tick['ask'])
        
        # Logic Smart: Kalau belum breakout DAN jaraknya mepet (< 200 poin), SKIP.
        # Tapi kalau udah breakout (dist negatif), GAS.
        if 0 < dist_to_pdh < SAFE_DIST_POINTS:
            return {"signal": "SKIP", "reason": "Too Close to PDH Resistance"}
            
        signal = "BUY"
        reason = "Bullish Engulfing + Trend M15"
        
        # Entry pake ASK (Harga Beli)
        entry_price = tick['ask']
        # SL di bawah Low candle - Buffer (misal 50 point)
        sl_dist = (last_5m['Close'] - last_5m['Low']) + (last_5m['ATR'] * 0.5)
        sl_price = entry_price - sl_dist
        
        # TP min 1.5R
        risk = entry_price - sl_price
        tp_price = entry_price + (risk * 2.0)
        
        setup = {
            "action": "BUY",
            "entry": round(entry_price, tick['digits']),
            "sl": round(sl_price, tick['digits']),
            "tp": round(tp_price, tick['digits']),
            "atr": round(last_5m['ATR'], tick['digits'])
        }

    # --- SELL LOGIC ---
    elif bear_engulf and trend_15m == "BEAR":
        # Cek PDL (Support)
        dist_to_pdl = get_point_dist(tick['bid'], hist['pdl'])
        
        # Kalau belum breakdown DAN jarak mepet, SKIP
        if 0 < dist_to_pdl < SAFE_DIST_POINTS:
            return {"signal": "SKIP", "reason": "Too Close to PDL Support"}
            
        signal = "SELL"
        reason = "Bearish Engulfing + Trend M15"
        
        # Entry pake BID (Harga Jual)
        entry_price = tick['bid']
        # SL di atas High candle + Buffer
        sl_dist = (last_5m['High'] - last_5m['Close']) + (last_5m['ATR'] * 0.5)
        sl_price = entry_price + sl_dist
        
        risk = sl_price - entry_price
        tp_price = entry_price - (risk * 2.0)
        
        setup = {
            "action": "SELL",
            "entry": round(entry_price, tick['digits']),
            "sl": round(sl_price, tick['digits']),
            "tp": round(tp_price, tick['digits']),
            "atr": round(last_5m['ATR'], tick['digits'])
        }

    # --- 7. RETURN CONTRACT (KONSISTEN) ---
    return {
        "signal": signal,       # BUY / SELL / SKIP / NO
        "reason": reason,       # Penjelasan kenapa
        "setup": setup,         # Dict kosong kalau NO/SKIP
        "timestamp": candle_time,
        "tick": tick,           # Kirim balik buat info
        "df_5m": df_5m          # Buat chart gen
    }
