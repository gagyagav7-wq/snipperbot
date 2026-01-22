import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timezone

# --- KONFIGURASI SCALPER (USD ABSOLUTE) ---
# XAUUSD: $1 gerak harga = 100 points (di broker 2 digit) atau 1000 points (3 digit)
# Kita pakai USD Price biar anti-salah.

TARGET_SL_MIN_USD = 3.0  # Min SL $3 (setara 30 pips umum)
TARGET_SL_MAX_USD = 5.0  # Max SL $5 (setara 50 pips umum)
MAX_SPREAD_USD    = 0.50 # Spread maks $0.50 (50 cents / 5 pips). Lebih dari ini SKIP.
RR_RATIO          = 1.2  # Risk Reward 1:1.2 (Winrate Priority)
MAX_TP_USD        = 8.0  # Cap TP maks $8 (biar gak kejauhan di M5)

def find_quality_ob(df):
    """Mencari Order Block Valid dengan Displacement & ATR Guard"""
    subset = df.tail(100).copy()
    # Hitung ATR buat ngukur volatilitas & displacement
    atr = ta.atr(subset['High'], subset['Low'], subset['Close'], length=14)
    subset['ATR'] = atr
    
    ob_bull = None
    ob_bear = None
    
    # Scan Mundur (Cari yang paling fresh)
    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        if pd.isna(current_atr) or current_atr <= 0: continue # Guard NaN
        
        # BULLISH OB: Candle Merah -> diikuti Candle Hijau Gede (Displacement)
        if subset['Close'].iloc[i] < subset['Open'].iloc[i]: 
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            # Syarat: Candle besoknya Bullish & Body > 0.8x ATR (Impulsif)
            if subset['Close'].iloc[i+1] > subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bull = (subset['Low'].iloc[i], subset['High'].iloc[i]) # Zone: Low - High
                break 

    for i in range(len(subset)-4, 0, -1):
        current_atr = subset['ATR'].iloc[i]
        if pd.isna(current_atr) or current_atr <= 0: continue

        # BEARISH OB: Candle Hijau -> diikuti Candle Merah Gede
        if subset['Close'].iloc[i] > subset['Open'].iloc[i]:
            body_next = abs(subset['Close'].iloc[i+1] - subset['Open'].iloc[i+1])
            if subset['Close'].iloc[i+1] < subset['Open'].iloc[i+1] and body_next > (current_atr * 0.8):
                ob_bear = (subset['Low'].iloc[i], subset['High'].iloc[i]) # Zone: Low - High
                break

    return ob_bull, ob_bear

def calculate_rules(data):
    # 1. PREP DATA & DATA GUARD
    if 'm5' not in data or data['m5'].empty:
        return {"signal": "WAIT", "reason": "Data Empty", "setup": {}, "timestamp": None}

    df = data['m5'].copy()
    tick = data.get('tick', {})
    
    # Ambil Bid/Ask dengan aman (Cast float & default 0)
    bid = float(tick.get('bid', 0) or 0)
    ask = float(tick.get('ask', 0) or 0)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    timestamp = last.name

    # --- GUARD BLOCK 1: MARKET INTEGRITY ---
    # 1. Market Closed / Data Error
    if bid <= 0 or ask <= 0:
        return {"signal": "WAIT", "reason": "Market Closed / Invalid Tick", "setup": {}, "timestamp": timestamp}

    # 2. Spread Guard (USD Price Based)
    point = float(tick.get('point', 0.01) or 0.01)
    spread_raw = float(tick.get('spread', 0) or 0)
    # Konversi spread points ke USD. XAU biasanya: spread 30 points (3 digit) = $0.30
    spread_usd = spread_raw * point 
    
    if spread_usd > MAX_SPREAD_USD:
        return {"signal": "WAIT", "reason": f"High Spread: ${spread_usd:.2f}", "setup": {}, "timestamp": timestamp}

    # 3. Stale Feed (Data Basi > 2 Menit) - Opsional kalau tick time ada
    tick_ts = int(tick.get('time', 0) or 0)
    if tick_ts > 0:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if (now_ts - tick_ts) > 120:
             return {"signal": "WAIT", "reason": "Stale Data Feed (>2m lag)", "setup": {}, "timestamp": timestamp}

    # --- INDICATOR BLOCK ---
    # 1. Trend Filter (EMA)
    ema_50 = ta.ema(df['Close'], length=50).iloc[-1]
    ema_200 = ta.ema(df['Close'], length=200).iloc[-1]
    trend = "BULLISH" if ema_50 > ema_200 else "BEARISH"
    
    # 2. ATR untuk Buffer
    atr_val = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]
    sweep_buffer = 0.2 * atr_val # Buffer toleransi stop hunt (wick sedikit tembus OB)

    # 3. SMC Logic
    ob_bull, ob_bear = find_quality_ob(df)
    
    signal = "WAIT"
    reason = "Scanning..."
    
    # --- LOGIC BUY ---
    if trend == "BULLISH" and ob_bull:
        ob_low, ob_high = ob_bull
        # Retest Logic Yang Ketat:
        # A. Harga Low masuk ke dalam zona (di bawah High OB)
        touched_zone = last['Low'] <= ob_high
        # B. Harga Low TIDAK tembus terlalu dalam (di atas Low OB - buffer) -> Valid Rejection, bukan Breakdown
        held_zone = last['Low'] >= (ob_low - sweep_buffer)
        # C. Close berhasil tutup DI ATAS zona (Konfirmasi Rejection)
        rejected_up = last['Close'] > ob_high
        
        if touched_zone and held_zone and rejected_up:
            signal = "BUY"
            reason = "SMC: Bullish OB Retest + Clean Rejection"

    # --- LOGIC SELL ---
    if trend == "BEARISH" and ob_bear:
        ob_low, ob_high = ob_bear
        # Retest Logic:
        # A. Harga High masuk zona (di atas Low OB)
        touched_zone = last['High'] >= ob_low
        # B. Harga High TIDAK tembus atas (di bawah High OB + buffer)
        held_zone = last['High'] <= (ob_high + sweep_buffer)
        # C. Close berhasil tutup DI BAWAH zona
        rejected_down = last['Close'] < ob_low
        
        if touched_zone and held_zone and rejected_down:
            signal = "SELL"
            reason = "SMC: Bearish OB Retest + Clean Rejection"

    # --- EXECUTION BLOCK (MONEY MANAGEMENT) ---
    setup = {}
    if signal in ["BUY", "SELL"]:
        # Entry Realtime
        entry_price = ask if signal == "BUY" else bid
        
        # Hitung Jarak SL Mentah (berdasarkan Swing)
        if signal == "BUY":
            swing_low = min(last['Low'], prev['Low'])
            raw_sl_dist = entry_price - swing_low
        else:
            swing_high = max(last['High'], prev['High'])
            raw_sl_dist = swing_high - entry_price
        
        # CLAMPING JARAK SL ($3.0 - $5.0)
        # "Jangan kurang dari $3 (kebisingan), Jangan lebih dari $5 (kegedean)"
        final_sl_dist = max(TARGET_SL_MIN_USD, min(raw_sl_dist, TARGET_SL_MAX_USD))
        
        # Hitung TP dengan Cap Max
        raw_tp_dist = final_sl_dist * RR_RATIO
        final_tp_dist = min(raw_tp_dist, MAX_TP_USD)
        
        # Hitung Harga Akhir
        if signal == "BUY":
            sl_price = entry_price - final_sl_dist
            tp_price = entry_price + final_tp_dist
        else:
            sl_price = entry_price + final_sl_dist
            tp_price = entry_price - final_tp_dist

        setup = {
            "entry": entry_price,
            "sl": sl_price,
            "tp": tp_price
        }

    return {
        "signal": signal,
        "reason": reason,
        "setup": setup,
        "timestamp": timestamp,
        "meta": {
            "indicators": {
                "trend": trend,
                "ema50": ema_50,
                "atr": atr_val
            },
            "risk_audit": {
                "spread_usd": spread_usd,
                "sl_dist_usd": final_sl_dist if signal in ["BUY", "SELL"] else 0,
                "tp_dist_usd": final_tp_dist if signal in ["BUY", "SELL"] else 0
            },
            "spread": spread_raw, # Untuk run_bot/AI
            "price": last['Close'],
            "dist_pdh_pts": 0,
            "dist_pdl_pts": 0
        }
    }
