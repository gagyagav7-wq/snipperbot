import pandas as pd
import pandas_ta as ta

def calculate_single_tf(df):
    # Fungsi pembantu biar gak ngetik ulang-ulang
    df = df.copy()
    df['EMA_50'] = df.ta.ema(length=50)
    df['EMA_200'] = df.ta.ema(length=200)
    df['RSI'] = df.ta.rsi(length=14)
    df['ATR'] = df.ta.atr(length=14)
    return df

def analyze_technicals(data_dict):
    # 1. Olah Semua Timeframe
    df_1m = calculate_single_tf(data_dict["1m"])
    df_5m = calculate_single_tf(data_dict["5m"])
    df_15m = calculate_single_tf(data_dict["15m"])
    df_dxy = calculate_single_tf(data_dict["dxy"])

    # Ambil Candle Terakhir (Closed)
    last_1m = df_1m.iloc[-2]
    last_5m = df_5m.iloc[-2]
    last_15m = df_15m.iloc[-2]
    last_dxy = df_dxy.iloc[-2]

    # 2. TENTUKAN TREND (THE BIAS)
    # Trend 15m (EMA 200) adalah Raja
    trend_15m = "BULLISH" if last_15m['Close'] > last_15m['EMA_200'] else "BEARISH"
    
    # 3. DETEKSI PATTERN DI 1 MENIT (SNIPER ENTRY)
    # Kita cari Engulfing di 1m buat entry cepet
    body = abs(last_1m['Close'] - last_1m['Open'])
    prev_body = abs(df_1m['Close'].iloc[-3] - df_1m['Open'].iloc[-3])
    
    bull_engulf = (last_1m['Close'] > last_1m['Open']) & \
                  (last_1m['Open'] < df_1m['Close'].iloc[-3]) & \
                  (last_1m['Close'] > df_1m['Open'].iloc[-3])
                  
    bear_engulf = (last_1m['Close'] < last_1m['Open']) & \
                  (last_1m['Open'] > df_1m['Close'].iloc[-3]) & \
                  (last_1m['Close'] < df_1m['Open'].iloc[-3])

    patterns = []
    if bull_engulf: patterns.append("1M Bullish Engulfing")
    if bear_engulf: patterns.append("1M Bearish Engulfing")

    # 4. FILTER (SYARAT PANGGIL AI)
    # Panggil AI cuma kalau:
    # Ada pola di 1m DAN Arahnya sesuai sama Trend 15m (Biar gak ngelawan arus)
    
    has_trigger = False
    if "1M Bullish Engulfing" in patterns and trend_15m == "BULLISH":
        has_trigger = True
    elif "1M Bearish Engulfing" in patterns and trend_15m == "BEARISH":
        has_trigger = True
    
    # Atau kalau RSI 1m Ekstrem banget (Scalping Reversal)
    if last_1m['RSI'] < 25 or last_1m['RSI'] > 75:
        has_trigger = True

    return {
        "has_trigger": has_trigger,
        "price": last_1m['Close'],
        "rsi_1m": last_1m['RSI'],
        "rsi_5m": last_5m['RSI'],
        "rsi_15m": last_15m['RSI'],
        "atr_1m": last_1m['ATR'],
        "patterns": patterns,
        "trend_1m": "UP" if last_1m['Close'] > last_1m['EMA_50'] else "DOWN",
        "trend_5m": "UP" if last_5m['Close'] > last_5m['EMA_50'] else "DOWN",
        "trend_15m": trend_15m,
        "dxy_trend": "UP" if last_dxy['Close'] > last_dxy['EMA_50'] else "DOWN",
        "timestamp": last_1m.name
    }
