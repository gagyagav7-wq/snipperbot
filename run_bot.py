import time
import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime

# Import Module Internal
from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger
from src.state_manager import check_trade_status, save_state_atomic
from src.ai_engine import ask_ai_judge

# --- CONFIG ---
load_dotenv() 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AI_MODE = True # Matikan ke False jika kuota AI habis/ingin rules saja

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def main():
    print("="*40)
    print("💀 JUDGEMENT DAY: GOLD KILLER PRO 💀")
    print("   Status: AI Judge + State Guard")
    print("="*40)

    logger = TradeLogger()
    last_print_reason = ""
    
    print("📡 Connecting to MT5 Server...")

    while True:
        try:
            # 1. AMBIL DATA
            data = get_market_data()
            if not data:
                print("⚠️ Waiting for MT5 Server...", end="\r")
                time.sleep(5)
                continue

            # 2. UPDATE NASIB TRADE (Cek SL/TP dari Candle terakhir yang CLOSE)
            # Kita pakai data m5 bar terakhir (index -1)
            last_closed_bar = data['m5'].iloc[-1]
            status = check_trade_status(last_closed_bar['high'], last_closed_bar['low'])
            
            if status in ["TP_HIT", "SL_HIT"]:
                icon = "💰" if status == "TP_HIT" else "💀"
                send_telegram(f"{icon} *TRADE FINISHED:* {status}")
                print(f"\n{icon} {status}! Resetting state...")
                save_state_atomic(active=False) # Reset memori jadi kosong

            # 3. KALKULASI RULES
            contract = calculate_rules(data)
            logger.log_contract(contract)

            # 4. FEEDBACK TERMINAL
            current_reason = contract["reason"]
            signal = contract["signal"]
            ts = contract["timestamp"]
            timestamp_str = ts.strftime("%H:%M") if ts else "--:--"

            if current_reason != last_print_reason:
                print(f"[{timestamp_str}] {signal} | {current_reason}")
                last_print_reason = current_reason

            # 5. EKSEKUSI SINYAL DENGAN FILTER KETAT
            if signal in ["BUY", "SELL"]:
                # FILTER A: Cek apakah masih ada trade jalan?
                if status == "STILL_OPEN":
                    if current_reason != last_print_reason:
                        print(f"⏳ {signal} Ignored: Previous trade still active.")
                    continue

                # FILTER B: AI JUDGE DEBATE
                if AI_MODE:
                    print(f"🤖 AI Judge is debating {signal}...")
                    # Kirim ringkasan indikator ke AI
                    metrics = contract.get("meta", {}).get("indicators", {})
                    judge = ask_ai_judge(signal, contract["reason"], metrics)
                    
                    if judge["decision"] == "APPROVE":
                        setup = contract["setup"]
                        icon = "🟢" if signal == "BUY" else "🔴"
                        
                        msg = f"{icon} *SIGNAL {signal} APPROVED*\n"
                        msg += f"🎯 Confidence: {judge['confidence']}%\n\n"
                        msg += f"Entry: `{setup['entry']}`\n"
                        msg += f"SL: `{setup['sl']}`\n"
                        msg += f"TP: `{setup['tp']}`\n\n"
                        msg += f"⚖️ *AI Debate:* _{judge['reason']}_\n"
                        msg += f"⏰ {timestamp_str} WIB"

                        send_telegram(msg)
                        # Simpan ke memori supaya gak entry lagi sampai hit SL/TP
                        save_state_atomic(
                            active=True, 
                            sig_type=signal, 
                            sl=setup['sl'], 
                            tp=setup['tp'], 
                            entry=setup['entry'],
                            reason=judge['reason']
                        )
                        print(f"✅ {signal} SENT & LOCKED")
                    else:
                        print(f"❌ AI REJECTED: {judge['reason']}")
                
                else:
                    # Mode No-AI (Langsung Kirim)
                    # ... (sama kayak run_bot lama lu) ...
                    pass

            time.sleep(2)

        except KeyboardInterrupt:
            print("\n🛑 Bot Stopped")
            sys.exit()
        except Exception as e:
            print(f"\n❌ Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
