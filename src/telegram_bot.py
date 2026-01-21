import telebot
from src.config import TELEGRAM_TOKEN, CHAT_ID

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_alert(ai_data, market_data):
    # Ambil variable biar gampang
    dec = ai_data['decision']
    scores = ai_data['scores']
    risk = ai_data['risk']
    setup = ai_data['setup']
    summary_points = ai_data['summary']

    # 1. Header Emoji
    if dec == "BUY":
        header = "🟢 **SIGNAL: BUY XAUUSD**"
        color = "🟩"
    elif dec == "SELL":
        header = "🔴 **SIGNAL: SELL XAUUSD**"
        color = "🟥"
    else:
        # Kalau SKIP, biasanya gak dikirim (difilter di run_bot.py), 
        # tapi kalau mau dikirim buat log:
        header = "⚠️ **DECISION: SKIP**"
        color = "⬜"

    # 2. Format Summary (Bikin jadi list bullet points)
    summary_text = ""
    for point in summary_points:
        summary_text += f"• {point}\n"

    # 3. Susun Pesan Final (Sesuai Format Lu)
    message = f"""
{header}
--------------------------------
📊 **SCOREBOARD**
Rule Quality : {scores['rule_score']}/100
🐂 Bull Power: {scores['bull_score']}
🐻 Bear Power: {scores['bear_score']}

🛡️ **RISK ASSESSMENT**
Status: {risk['status']}
Alasan: {risk['reason']}

🎯 **TRADING PLAN**
Entry : {setup['entry']}
SL    : {setup['sl']}
TP    : {setup['tp']}

📝 **DEBATE SUMMARY**
{summary_text}
--------------------------------
⏳ Time: {market_data['timestamp']}
💵 DXY Trend: {market_data['dxy_trend']}
"""
    
    try:
        bot.send_message(CHAT_ID, message, parse_mode="Markdown")
        print(f"✅ Pesan Telegram Terkirim: {dec}")
    except Exception as e:
        print(f"❌ Gagal Kirim Telegram: {e}")
