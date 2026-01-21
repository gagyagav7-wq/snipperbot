from dotenv import load_dotenv
load_dotenv() # WAJIB PALING ATAS

import time
import os
import sys
import requests
import html
import pandas as pd
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
    print("="*40 + "\n💀 GOLD KILLER PRO: GOD MODE TANK 💀\n" + "="*40)
    logger = TradeLogger()
    
    # --- GATES & THROTTLING ---
    last_candle_ts = None
    last_logged_ts = None
    last_ai_reject_ts = 0 # Throttling AI per candle

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

            # --- 1. STATUS CHECK & CLEARING ---
            status = check_signal_status(last_bar['High'], last_bar['Low'], current_ts)
            
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                finished = status # Simpan status asli buat log
                icon = "💰" if finished == "TP_HIT" else "💀"
                send_telegram_html(f"{icon} <b>SIGNAL FINISHED:</b> {finished}")
                save_state_atomic(active=False)
                status = "NONE" # Reset variabel lokal
                print(f"✅ State Cleared: {finished}")

            # --- 2. CANDLE GATE (ANTI-SPAM) ---
            if current_ts != last_candle_ts:
                contract = calculate_rules(data)
                
                # Logger gate
                if current_ts != last_logged_ts:
                    logger.log_contract(contract)
                    last_logged_ts = current_ts

                signal = contract["signal"]
                
                # --- 3. SIGNAL & AI JUDGE GATE ---
                if signal in ["BUY", "SELL"] and status == "NONE":
                    # AI Throttling: Jangan tanya AI kalau sudah tanya di candle ini (hemat kuota)
                    if current_ts != last_ai_reject_ts:
                        print(f"🤖 AI Judging {signal}...")
                        
                        # Kasih metrics "Decider-Grade" sesuai saran Suhu GPT
                        metrics = {
                            **contract.get("meta", {}).get("indicators", {}),
                            "spread": contract["meta"].get("spread"),
                            "tick_lag": contract["meta"].get("tick_lag", 0),
                            "dist_pdh_pts": contract["meta"].get("dist_pdh_pts"),
                            "dist_pdl_pts": contract["meta"].get("dist_pdl_pts"),
                            "price": last_bar["Close"]
                        }
                        
                        judge = ask_ai_judge(signal, contract["reason"], metrics)
                        decision = str(judge.get("decision", "REJECT")).strip().upper()
                        
                        if decision == "APPROVE":
                            setup = contract["setup"]
                            icon = "🟢" if signal == "BUY" else "🔴"
                            
                            # Safe HTML Escaping
                            ai_reason = html.escape(str(judge.get("reason", "No Reason")))
                            
                            text = (f"{icon} <b>SIGNAL {signal} APPROVED</b>\n\n"
                                    f"Entry: <code>{html.escape(str(setup['entry']))}</code>\n"
                                    f"SL: <code>{html.escape(str(setup['sl']))}</code>\n"
                                    f"TP: <code>{html.escape(str(setup['tp']))}</code>\n\n"
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
                            print(f"✅ {signal} SENT & LOCKED")
                        else:
                            # Catat TS reject biar gak tanya AI lagi di candle yang sama
                            last_ai_reject_ts = current_ts
                            print(f"❌ AI REJECTED: {judge.get('reason')}")
                
                last_candle_ts = current_ts

            time.sleep(2)
        except KeyboardInterrupt: sys.exit()
        except Exception as e: print(f"❌ Main Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
