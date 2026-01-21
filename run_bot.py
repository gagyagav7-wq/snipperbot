import time
import pandas as pd
from datetime import datetime
import pytz
from src.data_loader import get_market_data
from src.indicators import analyze_technicals
from src.ai_council import run_debate
from src.telegram_bot import send_alert
from src.config import SYMBOL

tz = pytz.timezone('Asia/Jakarta')

print(f"🚀 BOT SCALPING SIAP TEMPUR...")

# Variable buat ngunci biar ga spam
last_processed_candle_time = None 

while True:
    try:
        # 1. Ambil Data
        data_dict = get_market_data(SYMBOL)
        if data_dict is None:
            time.sleep(5)
            continue
            
        # 2. Analisa
        analysis = analyze_technicals(data_dict)
        
        # Waktu candle yang baru saja close (bukan waktu sekarang)
        candle_close_time = analysis['timestamp']
        
        # --- LOGIKA ANTI SPAM ---
        # Kalau waktu candle ini SAMA dengan yang terakhir diproses, berati ini candle lama. SKIP.
        if last_processed_candle_time == candle_close_time:
            # Print titik doang biar tau bot idup
            print(".", end="", flush=True)
            time.sleep(3) # Cek lagi 3 detik kemudian
            continue
            
        # Kalau ini candle BARU, baru kita cek sinyalnya
        print(f"\n[{datetime.now(tz).strftime('%H:%M:%S')}] New Candle Close: {analysis['price']}")
        
        if analysis['has_trigger']:
            print("⚡ Setup Valid! Memanggil Dewan AI...")
            
            debate = run_debate(analysis)
            
            if debate and debate.get('decision') != "SKIP":
                send_alert(debate, analysis)
                print("✅ Alert Terkirim!")
            else:
                print("❌ AI Memutuskan SKIP (Resiko Tinggi/Trend Lawan Arah).")
        
        # Kunci candle ini biar gak diproses ulang
        last_processed_candle_time = candle_close_time
        
    except Exception as e:
        print(f"Error Loop: {e}")
        time.sleep(10)
