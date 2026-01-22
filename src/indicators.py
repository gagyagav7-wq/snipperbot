import pandas as pd
import pandas_ta as ta
import numpy as np

def get_point_value(tick_data):
    """Auto-detect point & pips value based on Broker Digits"""
    point = tick_data.get('point', 0.01) # Default fallback
    # Standar XAU: 
    # 2 digit (2025.50) -> 1 pip = 0.1, 1 point = 0.01
    # 3 digit (2025.505) -> 1 pip = 0.1 ?? (Biasanya 10 points = 1 pip)
    # Kita pakai standar umum: 1 Pip = 10 Points
    return point

def find_quality_ob(df, atr_threshold=1.0):
    """Mencari Order Block dengan Displacement (Power Candle)"""
    # Ambil data secukupnya
    subset = df.tail(100).copy()
    atr = ta.atr(subset['High'], subset['Low'], subset['Close'], length=14)
    subset['ATR'] = atr
    
    ob_bull = None
    ob_bear = None
    
    # Scan Mundur
    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        
        # BULLISH OB: Candle Merah -> diikuti Candle Hijau Gede (Displacement)
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: # Merah
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            # Syarat: Candle setelahnya harus Bullish & Body > 0.8x ATR (Impulsif)
            if subset['Close'].iloc[i+1] > subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                # Valid OB Zone: Low s/d High candle merah tsb
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i])
                break # Ambil yang paling fresh

    for i in range(len(subset)-4, 0, -1):
        # BEARISH OB: Candle Hijau -> diikuti Candle Merah Gede
        if subset['Close'].iloc[i] > subset['Open'].iloc[i]: # Hijau
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] < subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i])
                break

    return ob_bull, ob_bear

def calculate_rules(data):
    # 1. PREP DATA
    df = data['m5'].copy()
    tick = data.get('tick', {})
    
    # SAFETY: Pastikan Tick Data ada (buat spread & point)
    point = tick.get('point', 0.01)
    if point == 0: point = 0.01 # Fallback biar gak error div by zero
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 2. TREND & STRUKTUR
    ema_50 = ta.ema(df['Close'], length=50).iloc[-1]
    ema_200 = ta.ema(df['Close'], length=200).iloc[-1]
    trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
    
    # 3. SMC LOGIC
    ob_bull, ob_bear = find_quality_ob(df)
    
    signal = "WAIT"
    reason = "Scanning..."
    
    # Jarak harga sekarang ke OB (dalam Points)
    # Pake CLOSE candle terakhir sebagai referensi rejection
    dist_bull_pts = ((last['Close'] - ob_bull[1]) / point) if ob_bull else 99999
    dist_bear_pts = ((ob_bear[0] - last['Close']) / point) if ob_bear else 99999
    
    # TOLERANSI: Harga harus masuk zona atau deket banget (max 50 points / 5 pips)
    # DAN harus ada rejection (Wick)
    
    # --- LOGIC BUY ---
    # 1. Trend Bullish
    # 2. Harga nyentuh/deket OB Bullish
    # 3. Candle sekarang Hijau (Rejection confirm) atau Pinbar
    if trend == "BULLISH" and ob_bull:
        if dist_bull_pts <= 50: # Dekat/Masuk Zone
            # Cek Rejection Pattern (Close > Open atau Wick Bawah Panjang)
            is_reject = last['Close'] > last['Open'] or \
                        (last['Open'] - last['Low']) > (abs(last['Close'] - last['Open']) * 2)
            
            if is_reject:
                signal = "BUY"
                reason = f"SMC: Bullish OB Retest + Rejection. Trend Align."

    # --- LOGIC SELL ---
    if trend == "BEARISH" and ob_bear:
        if dist_bear_pts <= 50:
            is_reject = last['Close'] < last['Open'] or \
                        (last['High'] - last['Open']) > (abs(last['Close'] - last['Open']) * 2)
            
            if is_reject:
                signal = "SELL"
                reason = f"SMC: Bearish OB Retest + Rejection. Trend Align."

    # 4. SETUP EXECUTION (CLAMP 30-50 PIPS)
    setup = {}
    if signal in ["BUY", "SELL"]:
        # Gunakan Real Pricing (Ask/Bid)
        entry_price = tick['ask'] if signal == "BUY" else tick['bid']
        
        # Konfigurasi Pips (1 Pip = 10 Points biasanya di XAU)
        min_pips = 30
        max_pips = 50
        rr_ratio = 1.5 # Target 1:1.5
        
        # Konversi ke Price Distance
        # 1 Pip = 10 * Point (Asumsi standar XAU 2/3 digit)
        # Atau lebih aman: pip_val = 0.1 (kalau gold)
        # Kita pakai multiplier 100 * point kalau broker 3 digit, atau 10 * point kalau 2 digit
        # Biar aman: Pake POINT aja. 30 pips = 300 points.
        
        min_dist = 300 * point
        max_dist = 500 * point
        
        if signal == "BUY":
            swing_low = min(last['Low'], prev['Low'])
            raw_sl_dist = entry_price - swing_low
            
            # CLAMPING LOGIC
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
                "ob_status": "Near OB" if (dist_bull_pts < 100 or dist_bear_pts < 100) else "Far",
                "volatility": "Normal" # Bisa diisi ATR logic
            },
            "spread": tick.get('spread', 0),
            "price": last['Close'],
            "dist_pdh_pts": 0, # Placeholder
            "dist_pdl_pts": 0
        }
    }
