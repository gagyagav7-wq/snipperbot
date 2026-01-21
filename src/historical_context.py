import yfinance as yf
import pandas as pd
import pandas_ta as ta

def get_big_picture(symbol="GC=F"):
    print("⏳ Sedang menganalisa sejarah market (Daily, Weekly, Monthly)...")
    
    try:
        # Ambil data jangka panjang (1 Tahun ke belakang)
        # Kita ambil interval 1 Hari (1d) cukup mewakili hari, minggu, bulan
        df = yf.download(symbol, period="2y", interval="1d", progress=False)
        
        if len(df) < 200: return None

        # Fix MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # --- 1. ANALISA HARIAN (YESTERDAY) ---
        # Kita ambil candle index -2 (Kemarin Full Day yang udah close)
        yesterday = df.iloc[-2] 
        
        pdh = yesterday['High'] # Previous Day High
        pdl = yesterday['Low']  # Previous Day Low
        pdc = yesterday['Close'] # Previous Day Close
        
        # Trend Harian (EMA 50)
        df['EMA_50'] = df.ta.ema(length=50)
        daily_trend = "BULLISH" if pdc > df['EMA_50'].iloc[-2] else "BEARISH"

        # --- 2. ANALISA MINGGUAN (WEEKLY) ---
        # Resample data harian jadi mingguan
        logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
        df_weekly = df.resample('W').apply(logic)
        
        last_week = df_weekly.iloc[-2] # Minggu lalu full
        pwh = last_week['High'] # Previous Week High
        pwl = last_week['Low']  # Previous Week Low
        
        # Trend Mingguan (EMA 50 Weekly)
        df_weekly['EMA_50'] = df_weekly.ta.ema(length=50)
        weekly_trend = "BULLISH" if last_week['Close'] > df_weekly['EMA_50'].iloc[-2] else "BEARISH"

        # --- 3. ANALISA BULANAN (MONTHLY) ---
        df_monthly = df.resample('M').apply(logic)
        last_month = df_monthly.iloc[-2]
        
        pmh = last_month['High']
        pml = last_month['Low']
        
        # --- RANGKUMAN INTELEJEN ---
        context = {
            "daily": {
                "trend": daily_trend,
                "pdh": round(pdh, 2), # Resistance Kuat
                "pdl": round(pdl, 2), # Support Kuat
            },
            "weekly": {
                "trend": weekly_trend,
                "range_high": round(pwh, 2),
                "range_low": round(pwl, 2)
            },
            "monthly": {
                "range_high": round(pmh, 2),
                "range_low": round(pml, 2)
            }
        }
        
        print("✅ Analisa Sejarah Selesai!")
        return context

    except Exception as e:
        print(f"❌ Gagal Analisa Sejarah: {e}")
        return None
