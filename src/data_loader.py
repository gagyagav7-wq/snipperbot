import yfinance as yf
import pandas as pd

def get_multi_tf_data(symbol="GC=F"):
    try:
        # Ambil M5 (Entry & Volatility)
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        
        # Ambil M15 (Trend Filter)
        df_15m = yf.download(symbol, period="5d", interval="15m", progress=False)

        # Validasi
        if len(df_5m) < 50 or len(df_15m) < 50: return None

        # Fix MultiIndex Yahoo
        for df in [df_5m, df_15m]:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        return {"5m": df_5m, "15m": df_15m}
    except Exception as e:
        print(f"Data Error: {e}")
        return None
