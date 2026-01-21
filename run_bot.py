import time
import os
import sys
import requests
from dotenv import load_dotenv
from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger
from src.state_manager import check_signal_status, save_state_atomic
from src.ai_engine import ask_ai_judge

load_dotenv()

def send_telegram_html(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Gunakan HTML agar tidak gampang error karakter khusus
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: THE IMMORTAL 💀\n" + "="*40)
    logger = TradeLogger()
    last_candle_ts = None 
    last_logged_ts = None

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA (Fix iloc Bug) ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            current_ts = int(last_bar.name.timestamp())

            # --- 1. UPDATE SIGNAL STATUS (Signal Lock) ---
            status = check_signal_status(last_bar['High'], last_bar['Low'], current_ts)
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                send_telegram_html(f"🔔 <b>SIGNAL FINISHED:</b> {status}")
                save_state_atomic(active=False)

            # --- 2. RUN STRATEGY ---
            contract = calculate_rules(data)

            # --- 3. CANDLE GATE (ANTI-SPAM) ---
            if current_ts != last_candle_ts:
                # Log cuma 1x per candle
                if current_ts != last_logged_ts:
                    logger.log_contract(contract)
                    last_logged_ts = current_ts

                # Proses Sinyal
                signal = contract["signal"]
                if signal in ["BUY", "SELL"] and status != "STILL_OPEN":
                    # Siapkan data kaya buat AI
                    metrics = {
                        **contract.get("meta", {}).get("indicators", {}),
                        "spread": contract["meta"].get("spread"),
                        "price": last_bar["Close"],
                        "safe_dist": contract["meta"].get("safe_dist_price")
                    }
                    
                    judge = ask_ai_judge(signal, contract["reason"], metrics)
                    
                    if judge["decision"] == "APPROVE":
                        setup = contract["setup"]
                        icon = "🟢" if signal == "BUY" else "🔴"
                        text = (f"{icon} <b>SIGNAL {signal} APPROVED</b>\n\n"
                                f"Entry: {setup['entry']}\nSL: {setup['sl']}\nTP: {setup['tp']}\n\n"
                                f"⚖️ <b>AI Debate:</b> {judge['reason']}")
                        
                        send_telegram_html(text)
                        save_state_atomic(True, signal, setup['sl'], setup['tp'], setup['entry'], current_ts)
                        print(f"✅ {signal} SENT & LOCKED")
                    else:
                        print(f"❌ AI REJECTED: {judge['reason']}")
                
                last_candle_ts = current_ts

            time.sleep(2)
        except KeyboardInterrupt: sys.exit()
        except Exception as e: print(f"❌ Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
