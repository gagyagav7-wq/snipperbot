import pandas as pd
import pandas_ta as ta
import pytz

def calculate_rules(data):
    df_5m = data['m5'].copy()
    df_15m = data['m15'].copy()
    tick = data['tick']
    hist = data['history'] # Ini history broker asli
    
    # 1. INDIKATOR
    df_5m['EMA_50'] = df_5m.ta.ema(length=50)
    df_5m['ATR'] = df_5m.ta.atr(length=14)
    df_15m['EMA_50'] = df_15m.ta.ema(length=50)
    
    # Last Closed Candle
    last_5m = df_5m.iloc[-1]
    last_15m = df_15m.iloc[-1]
    
    # 2. SPREAD FILTER (Configurable)
    # Misal Max 30 Points (biasanya 3 pips di broker 5 digit)
    if tick['spread'] > 35: 
        return {"signal": "SKIP", "reason": f"High Spread: {tick['spread']}"}

    # 3. CONTEXT FILTER (PDH/PDL)
    price = last_5m['Close']
    
    # Jarak aman ke resistance (misal 200 points)
    dist_pdh = (hist['pdh'] - price) / tick['point']
    dist_pdl = (price - hist['pdl']) / tick['point']
    
    # 4. SETUP LOGIC (Bullish Engulfing Example)
    trend_15m = "BULL" if last_15m['Close'] > last_15m['EMA_50'] else "BEAR"
    
    # Simple Engulfing Check
    prev_5m = df_5m.iloc[-2]
    bull_engulf = (last_5m['Close'] > last_5m['Open']) and \
                  (last_5m['Open'] < prev_5m['Close']) and \
                  (last_5m['Close'] > prev_5m['Open'])
    
    signal = "NO"
    reason = ""
    setup_data = {}

    if bull_engulf and trend_15m == "BULL":
        if dist_pdh < 200: # Kalau < 20 pips ke atap, jangan buy
             return {"signal": "SKIP", "reason": "Too close to Daily High"}
        
        signal = "BUY"
        atr = last_5m['ATR']
        sl = price - (atr * 1.5)
        tp = price + ((price - sl) * 2.0)
        
        setup_data = {
            "entry": price,
            "sl": round(sl, tick['digits']),
            "tp": round(tp, tick['digits']),
            "atr": round(atr, tick['digits'])
        }

    return {
        "signal": signal,
        "setup": setup_data,
        "timestamp": last_5m.name, # Ini datetime object
        "df_5m": df_5m
    }
