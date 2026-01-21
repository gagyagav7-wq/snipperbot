import time
import pandas as pd
from datetime import datetime
import pytz
from src.data_loader import get_market_data
from src.indicators import analyze_technicals
from src.ai_council import run_debate
from src.telegram_bot import send_alert
from src.config import SYMBOL

# Setup Timezone Jakarta
tz = pytz.timezone('Asia/Jakarta')

print(f"🚀 BOT XAUUSD SUPER CERDAS DIMULAI... [{datetime.now(tz)}]")
print(">> Menunggu Candle Close M15...")

last_processed_time = None

while True:
    try:
        # 1. Ambil Data
        data_dict = get_market_data(SYMBOL)
        if data_dict is None:
            print("⚠️ Gagal ambil data, retrying...", end="\r")
            time.sleep(60)
            continue
            
        # 2. Analisa Teknikal
        analysis = analyze_technicals(data_dict)
        
        # Cek apakah candle baru sudah close?
        current_time = analysis['timestamp']
        
        if last_processed_time == current_time:
            # Masih di candle yang sama, tidur dulu
            print(f".", end="", flush=True)
            time.sleep(30)
            continue
            
        # 3. Cek Trigger
        print(f"\n[{datetime.now(tz).strftime('%H:%M')}] Candle Close: {analysis['price']:.2f} | Trigger: {analysis['has_trigger']}")
        
        if analysis['has_trigger']:
            print("🔥 Setup Potensial! Memanggil AI Council...")
            
            # 4. Debat AI
            debate_result = run_debate(analysis)
            
            if debate_result:
                # 5. Kirim Telegram
                send_alert(debate_result, analysis)
                last_processed_time = current_time
        else:
            print("💤 Market Sepi / Tidak Valid. Wait next candle.")
            last_processed_time = current_time

        # Sleep agak lama setelah proses candle
        time.sleep(30)

    except KeyboardInterrupt:
        print("\n👋 Bot dimatikan user.")
        break
    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
        time.sleep(60)
