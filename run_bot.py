import time
import telebot
from src.config import SYMBOL, TELEGRAM_TOKEN, CHAT_ID
from src.data_loader import get_multi_tf_data
from src.indicators import calculate_rules
from src.ai_council import run_debate
from src.state_manager import load_state, save_state
from src.chart_gen import generate_chart_image

bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("🚀 BOT STARTED...")

# Load state biar ga spam pas restart
state = load_state()
last_processed = state['last_processed_time']

while True:
    try:
        # 1. AMBIL DATA
        data = get_multi_tf_data(SYMBOL)
        if not data:
            time.sleep(10)
            continue

        # 2. JALANKAN RULE ENGINE
        analysis = calculate_rules(data)
        
        # 3. CEK TRIGGER CANDLE CLOSE (Poin 1)
        current_candle_time = str(analysis['timestamp'])
        
        if current_candle_time == last_processed:
            print(".", end="", flush=True)
            time.sleep(10) # Sleep 10 detik biar hemat resource
            continue
            
        # Candle Baru Close!
        print(f"\n⚡ New Candle M5: {current_candle_time}")
        
        # 4. APAKAH ADA SINYAL TEKNIKAL?
        if analysis['signal'] in ["BUY", "SELL"]:
            print(f"🔍 Setup {analysis['signal']} Detected via Rules. Asking AI...")
            
            # 5. DEBAT AI
            debate = run_debate(analysis['setup'])
            
            if debate:
                # 6. DECISION ENGINE (Wasit) (Poin 5)
                # Aturan: Risk harus PASS dan Keputusan AI harus TRADE
                if debate['risk_status'] == "PASS" and debate['referee_decision'] == "TRADE":
                    
                    # 7. GENERATE CHART IMAGE (Poin 7)
                    chart_img = generate_chart_image(analysis['data_5m'], title=f"{analysis['signal']} Setup")
                    
                    # 8. KIRIM ALERT + GAMBAR
                    caption = f"""
🚀 **SIGNAL CONFIRMED: {analysis['signal']}**
---------------------------
📊 **Technical Setup**
Entry: {analysis['setup']['entry']}
SL   : {analysis['setup']['sl']}
TP   : {analysis['setup']['tp']}

🤖 **AI Council Verdict**
Scores: 🐂 {debate['bull_score']} vs 🐻 {debate['bear_score']}
Risk  : {debate['risk_status']} ({debate['risk_reason']})

📝 **Summary:**
{debate['summary']}
---------------------------
⏳ Time: {current_candle_time}
                    """
                    
                    bot.send_photo(CHAT_ID, chart_img, caption=caption)
                    print("✅ Alert with Chart Sent!")
                    
                else:
                    print(f"❌ Skipped by AI: {debate['risk_reason']} / {debate['referee_decision']}")
            
        # 9. SIMPAN STATE (Update time biar ga diproses lagi)
        last_processed = current_candle_time
        save_state(last_processed)
        
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
