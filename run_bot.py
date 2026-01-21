import time
import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime
from src.state_manager import check_trade_status, save_state

# Import Module Buatan Kita
from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger

# --- CONFIG ---
load_dotenv() 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- TELEGRAM SENDER ---
def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram Token/Chat ID belum diset di .env")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# --- MAIN LOOP ---
def main():
    print("="*40)
    print("🚀 GOLD KILLER BOT (HYBRID MODE)")
    print("   Analisa: MT5 (Python)")
    print("   Eksekusi: Manual (MT4)")
    print("="*40)

    logger = TradeLogger()
    last_signal_time = None 
    last_print_reason = ""
    
    print("📡 Connecting to MT5 Server via ZMQ...")

    while True:
        try:
            # 1. Ambil Data (Panggil fungsi dari src/data_loader.py)
            data = get_market_data()
            
            if not data:
                print("⚠️ Waiting for MT5 Server...", end="\r")
                time.sleep(5)
                continue

            # 2. Kalkulasi Strategi
            contract = calculate_rules(data)

            # 3. Log
            logger.log_contract(contract)

            # 4. Feedback Terminal
            current_reason = contract["reason"]
            signal = contract["signal"]
            ts = contract["timestamp"]
            timestamp_str = ts.strftime("%H:%M") if ts else "--:--"

            if current_reason != last_print_reason:
                print(f"[{timestamp_str}] {signal} | {current_reason}")
                last_print_reason = current_reason

            # 5. Eksekusi Sinyal
            if signal in ["BUY", "SELL"]:
                candle_time = contract["timestamp"]
                
                if candle_time != last_signal_time:
                    setup = contract["setup"]
                    icon = "🟢" if signal == "BUY" else "🔴"
                    msg = f"{icon} *SIGNAL {signal} XAUUSD*\n\n"
                    msg += f"Entry: `{setup['entry']}`\n"
                    msg += f"SL: `{setup['sl']}`\n"
                    msg += f"TP: `{setup['tp']}`\n"
                    msg += f"ATR: {setup['atr']}\n\n"
                    msg += f"📝 *Reason:* {contract['reason']}\n"
                    msg += f"⏰ *Time:* {timestamp_str} WIB"

                    send_telegram(msg)
                    print(f"✅ ALERT SENT: {signal} @ {setup['entry']}")
                    
                    last_signal_time = candle_time
            
            time.sleep(2)

        except KeyboardInterrupt:
            print("\n🛑 Bot Stopped")
            sys.exit()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
