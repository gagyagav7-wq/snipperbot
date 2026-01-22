import pandas as pd
import pandas_ta as ta

def find_order_block(df):
    """Mencari Order Block terakhir (Candle berlawanan sebelum move kencang)"""
    # OB Bullish: Candle merah terakhir sebelum kenaikan impulsif
    # OB Bearish: Candle hijau terakhir sebelum penurunan impulsif
    
    # Ambil 50 candle terakhir biar cepat
    subset = df.tail(50).copy()
    ob_bull = None
    ob_bear = None
    
    # Loop mundur
    for i in range(len(subset)-4, 0, -1):
        # Deteksi Bullish OB
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: # Candle Merah
            # Cek apakah setelahnya ada kenaikan impulsif (BOS)
            if subset['Close'].iloc[i+1] > subset['High'].iloc[i] and \
               subset['Close'].iloc[i+2] > subset['High'].iloc[i+1]:
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i]) # Zone OB
                break # Ambil yang paling fresh
                
    for i in range(len(subset)-4, 0, -1):
        # Deteksi Bearish OB
        if subset['Close'].iloc[i] > subset['Open'].iloc[i]: # Candle Hijau
            # Cek apakah setelahnya ada penurunan impulsif
            if subset['Close'].iloc[i+1] < subset['Low'].iloc[i] and \
               subset['Close'].iloc[i+2] < subset['Low'].iloc[i+1]:
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i])
                break

    return ob_bull, ob_bear

def calculate_rules(data):
    # Pastikan data DataFrame
    df = data['m5'].copy()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # --- 1. TREND FILTER (EMA) ---
    # Scalping butuh arah trend jelas
    ema_50 = ta.ema(df['Close'], length=50).iloc[-1]
    ema_200 = ta.ema(df['Close'], length=200).iloc[-1]
    
    trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
    
    # --- 2. SMC: ORDER BLOCK DETECTION ---
    ob_bull, ob_bear = find_order_block(df)
    
    # Jarak harga ke OB (Points)
    dist_to_bull_ob = (last['Close'] - ob_bull[1]) if ob_bull else 99999
    dist_to_bear_ob = (ob_bear[0] - last['Close']) if ob_bear else 99999
    
    # --- 3. PRICE ACTION (ENTRY TRIGGER) ---
    signal = "WAIT"
    reason = "Scanning Market Structure..."
    
    # Logic BUY (Scalping):
    # Trend Bullish + Harga mantul di Bullish OB + Ada rejection (Pinbar/Engulfing)
    is_bullish_rejection = last['Close'] > last['Open'] and \
                           (last['Open'] - last['Low']) > (last['Close'] - last['Open']) * 1.5
                           
    if trend == "BULLISH" and ob_bull and dist_to_bull_ob < 500: # Dekat OB (50 pips tolerance)
        if is_bullish_rejection:
            signal = "BUY"
            reason = "SMC: Rejection at Bullish OB + Trend Align"

    # Logic SELL (Scalping):
    # Trend Bearish + Harga mantul di Bearish OB
    is_bearish_rejection = last['Close'] < last['Open'] and \
                           (last['High'] - last['Open']) > (last['Open'] - last['Close']) * 1.5

    if trend == "BEARISH" and ob_bear and dist_to_bear_ob < 500:
        if is_bearish_rejection:
            signal = "SELL"
            reason = "SMC: Rejection at Bearish OB + Trend Align"

    # --- 4. SCALPING SETUP (SL 30-50 Pips) ---
    setup = {}
    if signal in ["BUY", "SELL"]:
        entry_price = last['Close']
        
        # SL WAJIB 30-50 Pips (300 - 500 Points)
        # Kita set default 40 pips (400 points) atau sesuaikan High/Low candle
        sl_pips = 400 # Default 40 pips
        tp_pips = 600 # RR 1:1.5 (60 pips)
        
        if signal == "BUY":
            sl_price = entry_price - (sl_pips * 0.001) # XAU 1 point = 0.001 (cek digit broker)
            # Opsional: Taruh SL di bawah Low Candle Trigger kalau < 30 pips, tapi min 30 pips
            swing_low = min(last['Low'], prev['Low'])
            
            # Kunci SL minimal 30 pips, maksimal 50 pips
            real_sl_dist = (entry_price - swing_low) * 1000
            if real_sl_dist < 300: sl_price = entry_price - 0.30 # Min 30 pips
            elif real_sl_dist > 500: sl_price = entry_price - 0.50 # Max 50 pips
            else: sl_price = swing_low - 0.05 # Di bawah swing dikit
            
            tp_price = entry_price + (entry_price - sl_price) * 1.5 # RR 1:1.5
            
        else: # SELL
            sl_price = entry_price + (sl_pips * 0.001)
            swing_high = max(last['High'], prev['High'])
            
            real_sl_dist = (swing_high - entry_price) * 1000
            if real_sl_dist < 300: sl_price = entry_price + 0.30
            elif real_sl_dist > 500: sl_price = entry_price + 0.50
            else: sl_price = swing_high + 0.05
            
            tp_price = entry_price - (sl_price - entry_price) * 1.5

        setup = {
            "entry": entry_price,
            "sl": sl_price,
            "tp": tp_price
        }

    return {
        "signal": signal,
        "reason": reason,
        "setup": setup,
        "timestamp": last.name,
        "meta": {
            "indicators": {
                "trend": trend,
                "ema50": ema_50,
                "dist_ob_bull": dist_to_bull_ob if ob_bull else "None",
                "dist_ob_bear": dist_to_bear_ob if ob_bear else "None",
                "candle_pattern": "Rejection" if (is_bullish_rejection or is_bearish_rejection) else "Normal"
            },
            "spread": 0, # Placeholder, diisi di run_bot kalau ada
            "price": last['Close']
        }
    }
