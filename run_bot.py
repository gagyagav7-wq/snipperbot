import time
from src.data_loader import get_realtime_data # Pake yang ZMQ
from src.indicators import calculate_rules
from src.ai_council import run_debate
from src.historical_context import get_big_picture
from src.telegram_bot import send_alert
from src.config import SYMBOL

# GLOBAL STATE
COOLDOWN_UNTIL = 0 # Timestamp cooldown
DAILY_LOSS = 0
MAX_DAILY_LOSS = 20 # Stop kalau rugi $20 hari ini

print("🚀 SUPER BOT STARTED (ZMQ MODE)...")

# Load History Sekali
history = get_big_picture(SYMBOL)
if not history: history = {'daily':{'pdh':9999,'pdl':0}} # Dummy

while True:
    try:
        # 1. COOLDOWN CHECK
        if time.time() < COOLDOWN_UNTIL:
            time.sleep(10)
            continue

        # 2. AMBIL DATA REALTIME (MT5)
        data = get_realtime_data(SYMBOL)
        if not data:
            time.sleep(5)
            continue
            
        # 3. CEK RULES
        analysis = calculate_rules(data, history)
        
        # LOGIC PENTING: Cek Candle Baru
        # Kita pake timestamp dari data candle terakhir
        candle_ts = analysis.get('timestamp')
        
        # (Implementasi logic state last_processed di sini sperti sebelumnya)
        # ...
        
        if analysis['signal'] in ["BUY", "SELL"]:
            print(f"🔍 Setup Valid. Spread: {analysis['spread']}")
            
            # 4. DEBAT AI
            debate = run_debate(analysis['setup'], history)
            
            if debate and debate['decision'] == "TRADE" and debate['risk_status'] == "PASS":
                # KIRIM ALERT
                send_alert(debate, analysis)
                
                # 5. SET COOLDOWN (Poin 8)
                # Abis kirim sinyal, bot tidur 15 menit (biar ga spam di candle yg sama/berikutnya)
                print("💤 Entering Cooldown (15 mins)...")
                COOLDOWN_UNTIL = time.time() + (15 * 60)
            else:
                print(f"❌ AI Reject: {debate['risk_reason']}")
        
        time.sleep(3) # Cek cepet karena ini realtime data

    except Exception as e:
        print(f"Critical Loop Error: {e}")
        time.sleep(10)
