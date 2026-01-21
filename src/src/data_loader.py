import yfinance as yf

def get_market_data(symbol="GC=F"):
    try:
        # 1. Ambil Data XAUUSD (M15 dan H1)
        # Period 5 hari cukup untuk hitung indikator M15
        df_m15 = yf.download(symbol, period="5d", interval="15m", progress=False)
        
        # Period 1 bulan untuk H1 (Trend Besar)
        df_h1 = yf.download(symbol, period="1mo", interval="1h", progress=False)
        
        # 2. Ambil Data DXY (US Dollar Index) - H1
        df_dxy = yf.download("DX-Y.NYB", period="1mo", interval="1h", progress=False)

        if len(df_m15) < 50 or len(df_h1) < 50:
            return None

        # Fix bug Yahoo Finance (Multi-level columns)
        for df in [df_m15, df_h1, df_dxy]:
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df.columns = df.columns.get_level_values(0)
                except:
                    pass

        return {
            "m15": df_m15,
            "h1": df_h1,
            "dxy": df_dxy
        }

    except Exception as e:
        print(f"❌ Error Data Loader: {e}")
        return None
