import yfinance as yf
import pandas as pd

def get_market_data(symbol="GC=F"):
    try:
        # Ambil 3 Timeframe Sekaligus
        # 1m = Data "mikro" buat entry (cuma bisa ambil 7 hari terakhir di Yahoo)
        df_1m = yf.download(symbol, period="5d", interval="1m", progress=False)
        
        # 5m = Data "tactical"
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        
        # 15m = Data "trend"
        df_15m = yf.download(symbol, period="1mo", interval="15m", progress=False)
        
        # DXY tetep pake H1 buat korelasi makro
        df_dxy = yf.download("DX-Y.NYB", period="1mo", interval="1h", progress=False)

        # Validasi Data
        if len(df_1m) < 50 or len(df_5m) < 50 or len(df_15m) < 50:
            return None

        # Fix Multi-Index Column (Penyakit Yahoo Finance baru)
        for df in [df_1m, df_5m, df_15m, df_dxy]:
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df.columns = df.columns.get_level_values(0)
                except: pass

        return {
            "1m": df_1m,
            "5m": df_5m,
            "15m": df_15m,
            "dxy": df_dxy
        }

    except Exception as e:
        print(f"❌ Error Data Loader: {e}")
        return None
