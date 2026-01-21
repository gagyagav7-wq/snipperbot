import time
from datetime import datetime
import pytz
from src.data_loader import get_market_data
from src.indicators import analyze_technicals
from src.ai_council import run_debate
from src.telegram_bot import send_alert
from src.config import SYMBOL
from src.historical_context import get_big_picture # Import modul baru

tz = pytz.timezone('Asia/Jakarta')

print(f"🚀 BOT STARTING...")

# 1. LOAD CONTEXT (SEJARAH) SEKALI AJA PAS START
history = get_big_picture(SYMBOL)
if history is None:
    print("⚠️ Gagal load history, bot jalan dengan mode buta sejarah.")
    # Default dummy biar ga error
    history = {'daily':{'trend':'NEUTRAL','pdh':0,'pdl':0}, 'weekly':{'trend':'NEUTRAL','range_low':0,'range_high':0}, 'monthly':{'range_low':0,'range_high':0}}

last_processed_candle_time = None
current_day = datetime.now(tz).day

while True:
    try:
        # Cek Ganti Hari (Buat refresh data PDH/PDL)
        if datetime.now(tz).day != current_day:
            print("🔄 Hari baru! Refresh data sejarah...")
            history = get_big_picture(SYMBOL)
            current_day = datetime.now(tz).day
        
        # ... (Logika Ambil Data Realtime sama kayak sebelumnya) ...
        data_dict = get_market_data(SYMBOL)
        if data_dict is None:
            time.sleep(5)
            continue
            
        analysis = analyze_technicals(data_dict)
        candle_close_time = analysis['timestamp']
        
        if last_processed_candle_time == candle_close_time:
            time.sleep(1)
            continue
            
        print(f"[{datetime.now(tz).strftime('%H:%M')}] Price: {analysis['price']}")
        
        if analysis['has_trigger']:
            print("⚡ Trigger! Checking Context...")
            
            # 2. MASUKIN DATA SEJARAH KE AI
            debate = run_debate(analysis, history)
            
            if debate and debate.get('decision') != "SKIP":
                # Tambahin info sejarah di alert biar lu tau
                analysis['pdh'] = history['daily']['pdh']
                analysis['pdl'] = history['daily']['pdl']
                
                send_alert(debate, analysis)
                last_processed_candle_time = candle_close_time
        
        last_processed_candle_time = candle_close_time
        
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
