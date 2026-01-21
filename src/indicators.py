import pandas_ta as ta
from datetime import datetime
import pytz

def calculate_rules(data):
    df_5m = data['5m'].copy()
    df_15m = data['15m'].copy()

    # --- INDIKATOR ---
    # M15 Trend
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    
    # M5 Setup
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['RSI'] = df_5m.ta.rsi(length=14)
    df_5m['ATR'] = df_5m.ta.atr(length=14)

    # Ambil Candle Closed Terakhir
    last_5m = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-2] # Simplified matching logic

    # --- 1. SESSION FILTER (Poin 6) ---
    # Hanya trade sesi London (14-17 WIB) & NY (19-23 WIB)
    tz = pytz.timezone('Asia/Jakarta')
    hour = datetime.now(tz).hour
    is_session = (14 <= hour < 18) or (19 <= hour < 23)
    
    # --- 2. TREND FILTER ---
    trend_15m = "BULL" if last_15m['Close'] > last_15m['EMA_50'] else "BEAR"

    # --- 3. PATTERN & TRIGGER (Engulfing) ---
    # Bullish Engulfing
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < df_5m['Close'].iloc[-3]) and \
                  (last_5m['Close'] > df_5m['Open'].iloc[-3])
    
    # Bearish Engulfing
    bear_engulf = (last_5m['Close'] < last_5m['Open']) and \
                  (last_5m['Open'] > df_5m['Close'].iloc[-3]) and \
                  (last_5m['Close'] < df_5m['Open'].iloc[-3])

    # --- 4. SUSUN SETUP LENGKAP (Poin 3) ---
    signal = "NO"
    setup = {}
    
    # Logic Buy
    if bull_engulf and trend_15m == "BULL" and is_session:
        signal = "BUY"
        atr = last_5m['ATR']
        entry = last_5m['Close']
        sl = entry - (atr * 1.5) # SL = 1.5x ATR
        tp = entry + ((entry - sl) * 2.0) # RR 1:2
        
        setup = {
            "action": "BUY",
            "reason": "M5 Bullish Engulfing aligned with M15 Trend",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "atr": round(atr, 2),
            "confidence": 80 # Base score rule
        }

    # Logic Sell
    elif bear_engulf and trend_15m == "BEAR" and is_session:
        signal = "SELL"
        atr = last_5m['ATR']
        entry = last_5m['Close']
        sl = entry + (atr * 1.5)
        tp = entry - ((sl - entry) * 2.0)
        
        setup = {
            "action": "SELL",
            "reason": "M5 Bearish Engulfing aligned with M15 Trend",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "atr": round(atr, 2),
            "confidence": 80
        }

    return {
        "signal": signal,
        "setup": setup,
        "data_5m": df_5m, # Balikin dataframe buat bikin chart nanti
        "timestamp": last_5m.name
    }
