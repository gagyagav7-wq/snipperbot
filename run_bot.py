from dotenv import load_dotenv
load_dotenv() # WAJIB PALING ATAS

import time
import os
import sys
import requests
import html # Import html escape
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
    print("="*40 + "\n💀 GOLD KILLER PRO: FINAL RELEASE 💀\n" + "="*40)
    logger = TradeLogger()
    
    last_candle_ts = None
    last_logged_ts = None
    last_ai_key = None 

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            ts = last_bar.name
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize("UTC")
            current_ts = int(ts.timestamp())

            # --- 1. STATUS CHECK ---
            status = check_signal_status(last_bar['High'], last_bar['Low'])
            
            # Kalau status korup (STILL_OPEN gara-gara rename), user harus manual check
            # Tapi di loop berikutnya file corrupt udah direname, jadi status bakal jadi "NONE"
            # Ini OK biar bot gak mati selamanya, tapi log di terminal bakal kasih warning.
            
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                finished = status
                icon = "💰" if finished == "TP_HIT" else "💀"
                send_telegram_html(f"{icon} <b>SIGNAL FINISHED:</b> {finished}")
                save_state_atomic(active=False) 
                status = "NONE" 
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
                    current_ai_key = f"{current_ts}_{signal}"
                    
                    if current_ai_key != last_ai_key:
                        last_ai_key = current_ai_key 
                        
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
                            
                            # Safe HTML Handling (Untuk semua field)
                            ai_reason = html.escape(str(judge.get("reason", "No Reason")))
                            entry_safe = html.escape(str(setup.get('entry', '0')))
                            sl_safe    = html.escape(str(setup.get('sl', '0')))
                            tp_safe    = html.escape(str(setup.get('tp', '0')))
                            
                            text = (f"{icon} <b>SIGNAL {signal} APPROVED</b>\n\n"
                                    f"Entry: <code>{entry_safe}</code>\n"
                                    f"SL: <code>{sl_safe}</code>\n"
                                    f"TP: <code>{tp_safe}</code>\n\n"
                                    f"⚖️ <b>AI Debate:</b> <i>{ai_reason}</i>")
                            
                            send_telegram_html(text)
                            
                            save_state_atomic(
                                active=True,
                                sig_type=signal,
                                sl=setup['sl'],
                                tp=setup['tp'],
                                entry=setup['entry'],
                                reason=judge.get("reason", ""),
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
