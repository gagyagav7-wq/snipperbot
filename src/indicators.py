import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime

# --- CONFIG KONSTANTA ---
# GOLD STANDARD: XAUUSD 1 Pip = $0.10 per Oz (biasanya 0.01 harga di chart)
# Contoh: 2025.00 -> 2025.10 = 1 Pip (10 Points)
PIP_SIZE = 0.1 # Revisi: 0.1 di harga = 1 Pip (Standard MT4/5 XAUUSD seringnya 1 pip = 10 cent)
# TAPI banyak broker pakai contract size beda.
# Cara paling aman: Asumsikan SL 30-50 pips ~ $3.0 - $5.0 pergerakan harga emas.
# KOREKSI: Dalam istilah umum scalper gold:
# "30 pips" biasanya maksudnya pergerakan $3.0 (300 points).
# Jadi SL = Entry +/- 3.0
TARGET_SL_MIN_PRICE = 3.0 # $3 pergerakan harga
TARGET_SL_MAX_PRICE = 5.0 # $5 pergerakan harga

def find_quality_ob(df):
    """Mencari Order Block Valid dengan Displacement > ATR"""
    subset = df.tail(100).copy()
    atr = ta.atr(subset['High'], subset['Low'], subset['Close'], length=14)
    subset['ATR'] = atr
    
    ob_bull = None
    ob_bear = None
    
    # Loop Mundur
    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        
        # Bullish OB (Merah -> Hijau Gede)
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: 
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] > subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i]) # (Low, High)
                break 

    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i] # FIX: Definisi ATR di loop kedua
        
        # Bearish OB (Hijau -> Merah Gede)
        if subset['Close'].iloc[i] > subset['Open'].iloc[i]:
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] < subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i]) # (Low, High)
                break

    return ob_bull, ob_bear

def calculate_rules(data):
    # 1. PREP DATA
    df = data['m5'].copy()
    tick = data.get('tick', {})
    meta = {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # --- SAFETY GUARD (BANK GRADE) ---
    # Spread Check (Max spread $0.3 / 300 points / 3 pips besar)
    spread = tick.get('spread', 0)
    point = tick.get('point', 0.01)
    
    # Hitung spread dalam harga
    # spread_val = spread * point
    # if spread_val > 0.40: # Di atas 40 cent ($0.4)
    #     return {"signal": "WAIT", "reason": f"High Spread: {spread_val:.2f}", "setup": {}, "timestamp": last.name}
    
    # 2. TREND FILTER (EMA)
    ema_50 = ta.ema(df['Close'], length=50).iloc[-1]
    ema_200 = ta.ema(df['Close'], length=200).iloc[-1]
    trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
    
    # 3. SMC LOGIC (OB + Rejection)
    ob_bull, ob_bear = find_quality_ob(df)
    
    signal = "WAIT"
    reason = "Scanning Market Structure..."
    
    # --- LOGIC BUY ---
    if trend == "BULLISH" and ob_bull:
        ob_low, ob_high = ob_bull
        # Syarat Retest:
        # 1. Harga Low candle menyentuh/masuk zona OB (atau sedikit di bawahnya - Stop Hunt toleransi)
        touched = last['Low'] <= ob_high 
        # 2. Harga Close menutup DI ATAS zona OB (Rejection Valid)
        rejected = last['Close'] > ob_high 
        
        if touched and rejected:
            signal = "BUY"
            reason = "SMC: Bullish OB Retest + Valid Rejection"

    # --- LOGIC SELL ---
    if trend == "BEARISH" and ob_bear:
        ob_low, ob_high = ob_bear
        # Syarat Retest:
        # 1. Harga High menyentuh/masuk zona
        touched = last['High'] >= ob_low
        # 2. Harga Close menutup DI BAWAH zona
        rejected = last['Close'] < ob_low
        
        if touched and rejected:
            signal = "SELL"
            reason = "SMC: Bearish OB Retest + Valid Rejection"

    # 4. SETUP EXECUTION (CLAMP 30-50 PIPS)
    setup = {}
    if signal in ["BUY", "SELL"]:
        # Pakai Real Ask/Bid
        entry_price = tick['ask'] if signal == "BUY" else tick['bid']
        
        # TARGET: SL $3.0 - $5.0 (30-50 pips scalping term)
        min_dist = TARGET_SL_MIN_PRICE
        max_dist = TARGET_SL_MAX_PRICE
        rr_ratio = 1.5 
        
        if signal == "BUY":
            swing_low = min(last['Low'], prev['Low'])
            raw_sl_dist = entry_price - swing_low
            
            # CLAMPING LOGIC (Pakai Harga Absolut)
            final_sl_dist = max(min_dist, min(raw_sl_dist, max_dist))
            
            sl_price = entry_price - final_sl_dist
            tp_price = entry_price + (final_sl_dist * rr_ratio)
            
        else: # SELL
            swing_high = max(last['High'], prev['High'])
            raw_sl_dist = swing_high - entry_price
            
            # CLAMPING LOGIC
            final_sl_dist = max(min_dist, min(raw_sl_dist, max_dist))
            
            sl_price = entry_price + final_sl_dist
            tp_price = entry_price - (final_sl_dist * rr_ratio)

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
                "ob_bull": str(ob_bull) if ob_bull else "None",
                "ob_bear": str(ob_bear) if ob_bear else "None",
            },
            "spread": spread,
            "price": last['Close'],
            "safe_dist_price": 0 # Placeholder
        }
    }
