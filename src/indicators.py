import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime

# --- KONFIGURASI (Production Config) ---
# Timezone
WIB = pytz.timezone('Asia/Jakarta')

# Trading Rules
SESSION_START_HOUR = 14  # Jam 14.00 WIB
SESSION_END_HOUR = 23    # Jam 23.00 WIB
MAX_SPREAD_POINTS = 35   # Configurable di .env
SAFE_DIST_POINTS = 200   # Jarak aman ke PDH/PDL
MIN_BODY_ATR = 0.3       # Filter Doji

# Risk Rules
ATR_SL_MULT = 1.5        # SL = 1.5x ATR
RR_RATIO = 2.0           # TP = 2x Risk
MIN_STOP_LEVEL = 10      # Jarak minimum SL dari Entry (Points) - Jaga2 kalau broker nolak

def calculate_rules(data_pack):
    # ---------------------------------------------------------
    # 0. INITIALIZE CONTRACT (Template Output Default)
    # Biar downstream (AI/Telegram) gak error KeyMissing
    # ---------------------------------------------------------
    contract = {
        "signal": "NO",
        "reason": "Initializing...",
        "setup": {},
        "timestamp": None,
        "tick": data_pack.get('tick', {}),
        "df_5m": pd.DataFrame(),
        "meta": {"spread": 0, "session": False}
    }

    # 1. DATA GUARD
    if not data_pack or 'm5' not in data_pack or 'm15' not in data_pack:
        contract["reason"] = "Data Empty"
        return contract

    df_5m = data_pack['m5'].copy()
    df_15m = data_pack['m15'].copy()
    tick = data_pack.get('tick', {})
    hist = data_pack.get('history', {})
    
    # Isi DataFrame ke kontrak buat chart nanti
    contract["df_5m"] = df_5m

    # Validasi Panjang Data
    if len(df_5m) < 60 or len(df_15m) < 60:
        contract["reason"] = "Not Enough Data"
        return contract

    # ---------------------------------------------------------
    # 2. HITUNG INDIKATOR
    # ---------------------------------------------------------
    # M5
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    
    # M15
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    df_15m['EMA_200'] = df_15m.ta.ema(length=200) # (Buat trend filter advanced)

    last_5m = df_5m.iloc[-1]
    last_15m = df_15m.iloc[-1]

    # Guard NaN Indikator
    if pd.isna(last_5m['ATR']) or pd.isna(last_5m['EMA_50']):
        contract["reason"] = "Indicators Loading (NaN)"
        return contract

    # ---------------------------------------------------------
    # 3. TIME & SESSION HANDLING (Robust)
    # ---------------------------------------------------------
    # Asumsi index DataFrame adalah datetime (UTC/Naive dari server ZMQ)
    try:
        ts = last_5m.name
        # Kalau Naive (polos), kasih UTC dulu
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=pytz.utc)
        
        # Convert ke WIB
        candle_time_wib = ts.astimezone(WIB)
        contract["timestamp"] = candle_time_wib
        
        current_hour = candle_time_wib.hour
        is_session = (SESSION_START_HOUR <= current_hour < SESSION_END_HOUR)
        contract["meta"]["session"] = is_session
        
        if not is_session:
            contract["signal"] = "NO"
            contract["reason"] = f"Outside Killzone ({current_hour}:00 WIB)"
            return contract
            
    except Exception as e:
        contract["reason"] = f"Timezone Error: {e}"
        return contract

    # ---------------------------------------------------------
    # 4. SPREAD FILTER
    # ---------------------------------------------------------
    spread = tick.get('spread', 999)
    contract["meta"]["spread"] = spread
    
    if spread > MAX_SPREAD_POINTS:
        contract["signal"] = "SKIP"
        contract["reason"] = f"High Spread: {spread} pts"
        return contract

    # ---------------------------------------------------------
    # 5. PATTERN & TREND LOGIC
    # ---------------------------------------------------------
    # Trend M15 (Sekarang pakai EMA 50 & 200 buat strong trend)
    is_bull_trend = (last_15m['Close'] > last_15m['EMA_50'])
    is_bear_trend = (last_15m['Close'] < last_15m['EMA_50'])
    
    # Pattern Quality M5
    body_size = abs(last_5m['Close'] - last_5m['Open'])
    min_body = last_5m['ATR'] * MIN_BODY_ATR
    
    prev_5m = df_5m.iloc[-2]
    
    # Bullish Engulfing + Quality Gate
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open']) and \
                  (body_size > min_body) and \
                  (last_5m['RSI'] < 70) # Gak Overbought parah

    # Bearish Engulfing + Quality Gate
    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > prev_5m['Close']) and \
                  (last_5m['Close'] < prev_5m['Open']) and \
                  (body_size > min_body) and \
                  (last_5m['RSI'] > 30) # Gak Oversold parah

    # ---------------------------------------------------------
    # 6. SIGNAL GENERATION + LEVEL CHECK
    # ---------------------------------------------------------
    point = tick.get('point', 0.001)
    digits = tick.get('digits', 2)
    
    def get_points(p1, p2): return (p1 - p2) / point

    # --- BUY SETUP ---
    if bull_engulf and is_bull_trend:
        # Cek Jarak ke Resistance (PDH)
        # Dist positif = belum breakout. Dist negatif = udah breakout.
        dist_pdh = get_points(hist['pdh'], tick['ask'])
        
        # Kalau belum breakout DAN deket banget, SKIP
        if 0 < dist_pdh < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Too Close to PDH ({int(dist_pdh)} pts)"
            return contract
            
        # Hitung SL/TP (ATR Based)
        atr_val = last_5m['ATR']
        entry_price = tick['ask'] # Entry di ASK
        
        # SL di bawah Low - Buffer
        # Pake ATR murni buat jarak, bukan Close-Low
        sl_dist = atr_val * ATR_SL_MULT
        sl_price = entry_price - sl_dist
        
        # Guard: Stop Level Broker
        if get_points(entry_price, sl_price) < MIN_STOP_LEVEL:
             sl_price = entry_price - (MIN_STOP_LEVEL * point)

        risk = entry_price - sl_price
        tp_price = entry_price + (risk * RR_RATIO)
        
        contract["signal"] = "BUY"
        contract["reason"] = "Valid Bullish Engulfing"
        contract["setup"] = {
            "action": "BUY",
            "entry": round(entry_price, digits),
            "sl": round(sl_price, digits),
            "tp": round(tp_price, digits),
            "atr": round(atr_val, digits)
        }

    # --- SELL SETUP ---
    elif bear_engulf and is_bear_trend:
        # Cek Jarak ke Support (PDL)
        dist_pdl = get_points(tick['bid'], hist['pdl'])
        
        if 0 < dist_pdl < SAFE_DIST_POINTS:
            contract["signal"] = "SKIP"
            contract["reason"] = f"Too Close to PDL ({int(dist_pdl)} pts)"
            return contract
            
        # Hitung SL/TP
        atr_val = last_5m['ATR']
        entry_price = tick['bid'] # Entry di BID
        
        sl_dist = atr_val * ATR_SL_MULT
        sl_price = entry_price + sl_dist
        
        # Guard Stop Level
        if get_points(sl_price, entry_price) < MIN_STOP_LEVEL:
            sl_price = entry_price + (MIN_STOP_LEVEL * point)

        risk = sl_price - entry_price
        tp_price = entry_price - (risk * RR_RATIO)
        
        contract["signal"] = "SELL"
        contract["reason"] = "Valid Bearish Engulfing"
        contract["setup"] = {
            "action": "SELL",
            "entry": round(entry_price, digits),
            "sl": round(sl_price, digits),
            "tp": round(tp_price, digits),
            "atr": round(atr_val, digits)
        }
    
    else:
        contract["reason"] = "No Valid Pattern"

    return contract
