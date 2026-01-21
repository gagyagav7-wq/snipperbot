import pandas as pd
import pandas_ta as ta
from datetime import datetime
import pytz

def calculate_rules(data_dict, history_ctx):
    # Unpack Data
    df_1m = data_dict['1m'].copy()
    df_5m = data_dict['5m'].copy()
    df_15m = data_dict['15m'].copy()
    current_spread = data_dict['spread']
    
    # 1. INDIKATOR DASAR
    df_1m['EMA_50'] = df_1m.ta.ema(length=50)
    df_1m['RSI'] = df_1m.ta.rsi(length=14)
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    
    # Ambil Candle Closed Terakhir
    last_1m = df_1m.iloc[-1] # Data ZMQ udah clean, index terakhir adalah closed
    last_15m = df_15m.iloc[-1]
    
    # --- 2. SPREAD FILTER (WAJIB BUAT SCALPING) ---
    # Kalau spread > 20 poin (misal), SKIP. Jangan maksa entry.
    MAX_SPREAD = 25 
    if current_spread > MAX_SPREAD:
        return {"signal": "SKIP", "reason": f"Spread too high: {current_spread}"}

    # --- 3. SESSION FILTER (Pake Timestamp Candle, BUKAN Jam Server) ---
    # Convert waktu candle ke WIB
    candle_time_utc = last_1m.name
    wib_tz = pytz.timezone('Asia/Jakarta')
    candle_time_wib = candle_time_utc.replace(tzinfo=pytz.utc).astimezone(wib_tz)
    hour = candle_time_wib.hour
    
    # Session: London (14-17) & NY (19-23)
    is_session = (14 <= hour < 18) or (19 <= hour < 23)
    if not is_session:
        return {"signal": "SKIP", "reason": "Outside Kill Zone Session"}

    # --- 4. HISTORICAL CONTEXT FILTER (Poin 7) ---
    # Cek apakah harga mepet PDH (High Kemarin) atau PDL (Low Kemarin)
    price = last_1m['Close']
    pdh = history_ctx['daily']['pdh']
    pdl = history_ctx['daily']['pdl']
    
    near_resistance = abs(price - pdh) < 1.0 # Jarak kurang dari $1
    near_support = abs(price - pdl) < 1.0
    
    # --- 5. LOGIC TRIGGER ---
    trend_15m = "BULL" if last_15m['Close'] > last_15m['EMA_50'] else "BEAR"
    
    # Deteksi Engulfing di 1M
    bull_engulf = (last_1m['Close'] > last_1m['Open']) and \
                  (last_1m['Open'] < df_1m['Close'].iloc[-2]) and \
                  (last_1m['Close'] > df_1m['Open'].iloc[-2])
    
    bear_engulf = (last_1m['Close'] < last_1m['Open']) and \
                  (last_1m['Open'] > df_1m['Close'].iloc[-2]) and \
                  (last_1m['Close'] < df_1m['Open'].iloc[-2])

    # SUSUN SETUP
    signal = "NO"
    setup = {}
    
    if bull_engulf and trend_15m == "BULL":
        if near_resistance:
            return {"signal": "SKIP", "reason": "Buy Signal but hit PDH Resistance"}
        
        signal = "BUY"
        atr = last_1m['ATR'] if not pd.isna(last_1m.get('ATR')) else 1.0
        sl = price - 2.0 # SL 20 Pips (Scalping Gold)
        tp = price + 4.0 # TP 40 Pips (RR 1:2)
        
        setup = {
            "action": "BUY",
            "entry": price,
            "sl": sl, "tp": tp,
            "context": "Clean Bullish Setup"
        }

    elif bear_engulf and trend_15m == "BEAR":
        if near_support:
            return {"signal": "SKIP", "reason": "Sell Signal but hit PDL Support"}

        signal = "SELL"
        sl = price + 2.0
        tp = price - 4.0
        
        setup = {
            "action": "SELL",
            "entry": price,
            "sl": sl, "tp": tp,
            "context": "Clean Bearish Setup"
        }

    return {
        "signal": signal,
        "setup": setup,
        "timestamp": candle_time_wib,
        "spread": current_spread
    }
