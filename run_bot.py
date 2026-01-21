import time
import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime

# Import Module Buatan Kita
from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger

# --- CONFIG ---
load_dotenv() # Load token dari file .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- TELEGRAM SENDER ---
def send_telegram(message):
    """Kirim pesan ke Telegram dengan Mode Markdown"""
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
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            print(f"❌ Telegram Fail: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# --- MAIN LOOP ---
def main():
    print("="*40)
    print("🚀 GOLD KILLER BOT (HYBRID MODE)")
    print("   Analisa: MT5 (Python)")
    print("   Eksekusi: Manual (MT4)")
    print("="*40)

    # Init Logger (Black Box Recorder)
    logger = TradeLogger()
    
    # State Tracking (Biar gak spam alert yang sama)
    last_signal_time = None 
    last_print_reason = ""
    
    print("📡 Connecting to MT5 Server via ZMQ...")

    while True:
        try:
            # 1. Ambil Data dari Server Windows
            data = get_market_data()
            
            if not data:
                # Kalau server mati/koneksi putus
                print("⚠️ Waiting for MT5 Server...", end="\r")
                time.sleep(5)
                continue

            # 2. Kalkulasi Strategi (The Brain)
            contract = calculate_rules(data)

            # 3. Catat ke Log CSV (Audit Trail)
            logger.log_contract(contract)

            # 4. Feedback Terminal (Biar lu tau bot lagi ngapain)
            # Cuma print kalau reason berubah biar gak nyampah
            current_reason = contract["reason"]
            signal = contract["signal"]
            timestamp_str = contract["timestamp"].strftime("%H:%M") if contract["timestamp"] else "--:--"

            if current_reason != last_print_reason:
                print(f"[{timestamp_str}] {signal} | {current_reason}")
                last_print_reason = current_reason

            # 5. Eksekusi Sinyal (Kirim Alert)
            if signal in ["BUY", "SELL"]:
                # Pastikan ini sinyal dari candle BARU (bukan spam di candle yang sama)
                candle_time = contract["timestamp"]
                
                if candle_time != last_signal_time:
                    setup = contract["setup"]
                    
                    # Format Pesan Cantik
                    icon = "🟢" if signal == "BUY" else "🔴"
                    msg = f"{icon} *SIGNAL {signal} XAUUSD*\n\n"
                    msg += f"Entry: `{setup['entry']}`\n"
                    msg += f"SL: `{setup['sl']}`\n"
                    msg += f"TP: `{setup['tp']}`\n"
                    msg += f"ATR: {setup['atr']}\n\n"
                    msg += f"📝 *Reason:* {contract['reason']}\n"
                    msg += f"⏰ *Time:* {timestamp_str} WIB"

                    # Kirim!
                    send_telegram(msg)
                    print(f"✅ ALERT SENT TO TELEGRAM: {signal} @ {setup['entry']}")
                    
                    # Update state biar gak kirim lagi untuk candle ini
                    last_signal_time = candle_time
            
            # 6. Critical Warning Check (Optional)
            # Kalau ada warning serius di meta (Clock Drift parah, dll), kirim notif sekali aja
            # (Logic ini bisa dikembangkan nanti)

            # Sleep 2 detik biar gak makan CPU, tapi cukup cepat buat scalping
            time.sleep(2)

        except KeyboardInterrupt:
            print("\n🛑 Bot Stopped by User")
            sys.exit()
        except Exception as e:
            print(f"\n❌ CRITICAL LOOP ERROR: {e}")
            time.sleep(5) # Cooldown kalau error biar gak spam crash

if __name__ == "__main__":
    main()
