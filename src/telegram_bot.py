import telebot
from src.config import TELEGRAM_TOKEN, CHAT_ID

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_alert(debate_result, market_data):
    decision = debate_result['decision']
    
    if decision == "SKIP":
        print(f"⏭️ AI Memutuskan SKIP: {debate_result['reason']}")
        return

    emoji = "🟢" if decision == "BUY" else "🔴"
    
    message = f"""
{emoji} **SIGNAL: {decision} XAUUSD** {emoji}
--------------------------------
📊 Price: {market_data['price']:.2f}
📈 H1 Trend: {market_data['h1_trend']}
💵 DXY Trend: {market_data['dxy_trend']}

🗣️ **THE DEBATE:**
🐺 Sniper: "{debate_result['sniper_opinion']}"
🛡️ Risk: "{debate_result['risk_opinion']}"

⚖️ **VERDICT:**
"{debate_result['reason']}"

🎯 **PLAN:**
SL: {debate_result['stop_loss']}
TP: {debate_result['take_profit']}
--------------------------------
⚠️ *AI Generated Signal - DYOR*
    """
    
    try:
        bot.send_message(CHAT_ID, message, parse_mode="Markdown")
        print(f"✅ Sinyal {decision} terkirim ke Telegram!")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
