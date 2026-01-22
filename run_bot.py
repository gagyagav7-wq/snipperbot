from dotenv import load_dotenv
load_dotenv() # WAJIB PALING ATAS

import time
import os
import sys
import requests
import html
from datetime import datetime

from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger
from src.state_manager import check_signal_status, save_state_atomic
from src.ai_engine import ask_ai_judge

def send_telegram_html(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: HERMETIC VERSION 💀\n" + "="*40)
    logger = TradeLogger()
    
    last_candle_ts = None
    last_logged_ts = None
    last_ai_key = None # GATE PINTAR (Waktu + Sinyal)

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA (Timezone Safe) ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            ts = last_bar.name
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize("UTC")
            current_ts = int(ts.timestamp())

            # --- 1. STATUS CHECK ---
            status = check_signal_status(last_bar['High'], last_bar['Low'])
            
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                finished = status
                icon = "💰" if finished == "TP_HIT" else "💀"
                send_telegram_html(f"{icon} <b>SIGNAL FINISHED:</b> {finished}")
                save_state_atomic(active=False) # Bersih-bersih state
                status = "NONE" # Reset lokal
                print(f"✅ State Cleared: {finished}")

            # --- 2. CANDLE GATE ---
            if current_ts != last_candle_ts:
                contract = calculate_rules(data)
                
                if current_ts != last_logged_ts:
                    logger.log_contract(contract)
                    last_logged_ts = current_ts

                signal = contract["signal"]
                
                # --- 3. SMART AI GATE ---
                if signal in ["BUY", "SELL"] and status == "NONE":
                    # Kunci Unik: Waktu Candle + Arah Sinyal
                    current_ai_key = f"{current_ts}_{signal}"
                    
                    # Cek apakah kombinasi ini sudah pernah didebat?
                    if current_ai_key != last_ai_key:
                        last_ai_key = current_ai_key # Kunci dulu biar gak spam
                        
                        print(f"🤖 AI Judging {signal}...")
                        metrics = {
                            **contract.get("meta", {}).get("indicators", {}),
                            "spread": contract["meta"].get("spread"),
                            "price": last_bar["Close"]
                        }
                        
                        judge = ask_ai_judge(signal, contract["reason"], metrics)
                        decision = str(judge.get("decision", "REJECT")).strip().upper()
                        
                        if decision == "APPROVE":
                            setup = contract["setup"]
                            icon = "🟢" if signal == "BUY" else "🔴"
                            
                            # Safe HTML Handling (Biar gak ada 'None' nongol)
                            reason_raw = judge.get("reason") or "No reason provided"
                            ai_reason = html.escape(str(reason_raw))
                            
                            text = (f"{icon} <b>SIGNAL {signal} APPROVED</b>\n\n"
                                    f"Entry: <code>{setup['entry']}</code>\n"
                                    f"SL: <code>{setup['sl']}</code>\n"
                                    f"TP: <code>{setup['tp']}</code>\n\n"
                                    f"⚖️ <b>AI Debate:</b> <i>{ai_reason}</i>")
                            
                            send_telegram_html(text)
                            
                            save_state_atomic(
                                active=True,
                                sig_type=signal,
                                sl=setup['sl'],
                                tp=setup['tp'],
                                entry=setup['entry'],
                                reason=reason_raw,
                                candle_ts=current_ts
                            )
                            status = "STILL_OPEN"
                            print(f"✅ {signal} SENT & LOCKED")
                        else:
                            print(f"❌ AI REJECTED: {judge.get('reason')}")
                
                last_candle_ts = current_ts

            time.sleep(2)
        except KeyboardInterrupt: sys.exit()
        except Exception as e: print(f"❌ Main Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
