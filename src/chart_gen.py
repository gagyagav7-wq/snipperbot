import mplfinance as mpf
import io

def generate_chart_image(df, title="XAUUSD Chart"):
    # Ambil 50 candle terakhir biar chart gak kekecilan
    df_subset = df.iloc[-50:]
    
    # Style chart
    style = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'font.size': 10})
    
    # Buat buffer gambar (di memori, gak perlu simpen file)
    buf = io.BytesIO()
    
    # Tambah indikator EMA ke chart
    addplots = [
        mpf.make_addplot(df_subset['EMA_50'], color='orange', width=1.5)
    ]
    
    # Generate Chart
    mpf.plot(
        df_subset,
        type='candle',
        style=style,
        title=title,
        ylabel='Price',
        addplot=addplots,
        volume=False,
        savefig=dict(fname=buf, dpi=100, bbox_inches='tight')
    )
    
    buf.seek(0)
    return buf
