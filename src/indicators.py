import pandas as pd
import pandas_ta as ta

def analyze_technicals(data_dict):
    df = data_dict["m15"].copy()
    df_h1 = data_dict["h1"].copy()
    df_dxy = data_dict["dxy"].copy()

    # --- 1. PROSES M15 (UTAMA) ---
    df['EMA_50'] = df.ta.ema(length=50)
    df['RSI'] = df.ta.rsi(length=14)
    df['ATR'] = df.ta.atr(length=14)

    # Pola Price Action (Engulfing)
    df['body'] = abs(df['Close'] - df['Open'])
    df['prev_body'] = abs(df['Close'].shift(1) - df['Open'].shift(1))
    
    df['bullish_engulfing'] = (df['Close'] > df['Open']) & \
                              (df['Open'] < df['Close'].shift(1)) & \
                              (df['Close'] > df['Open'].shift(1)) & \
                              (df['body'] > df['prev_body'])

    df['bearish_engulfing'] = (df['Close'] < df['Open']) & \
                              (df['Open'] > df['Close'].shift(1)) & \
                              (df['Close'] < df['Open'].shift(1)) & \
                              (df['body'] > df['prev_body'])

    # SMC: Fair Value Gap (FVG) Simple
    df['fvg_bullish'] = (df['High'].shift(2) < df['Low']) & (df['Close'] > df['Open'])
    df['fvg_bearish'] = (df['Low'].shift(2) > df['High']) & (df['Close'] < df['Open'])

    # --- 2. PROSES H1 & DXY (TREND FILTER) ---
    df_h1['EMA_200'] = df_h1.ta.ema(length=200)
    df_dxy['EMA_50'] = df_dxy.ta.ema(length=50)

    # --- 3. RANGKUM DATA CANDLE TERAKHIR (CLOSED) ---
    last_m15 = df.iloc[-2] # Index -2 karena -1 adalah candle running
    last_h1 = df_h1.iloc[-2]
    last_dxy = df_dxy.iloc[-2]

    # Cek Pola
    patterns = []
    if last_m15['bullish_engulfing']: patterns.append("Bullish Engulfing")
    if last_m15['bearish_engulfing']: patterns.append("Bearish Engulfing")
    if last_m15['fvg_bullish']: patterns.append("Bullish FVG")
    if last_m15['fvg_bearish']: patterns.append("Bearish FVG")

    # Tentukan Trigger (Apakah perlu panggil AI?)
    # Kita panggil AI jika ada pola ATAU RSI ekstrem
    has_trigger = len(patterns) > 0 or last_m15['RSI'] < 30 or last_m15['RSI'] > 70

    return {
        "has_trigger": has_trigger,
        "price": last_m15['Close'],
        "rsi": last_m15['RSI'],
        "atr": last_m15['ATR'],
        "patterns": patterns,
        "m15_trend": "BULLISH" if last_m15['Close'] > last_m15['EMA_50'] else "BEARISH",
        "h1_trend": "BULLISH" if last_h1['Close'] > last_h1['EMA_200'] else "BEARISH",
        "dxy_trend": "BULLISH" if last_dxy['Close'] > last_dxy['EMA_50'] else "BEARISH",
        "timestamp": last_m15.name
    }
