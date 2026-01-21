# --- 1. WAJIB DI PALING ATAS ---
from dotenv import load_dotenv
load_dotenv() 

import time
import os
import sys
import requests
import html # Tambahan buat escape HTML
from datetime import datetime

# Import Module Internal
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
    try:
        requests.post(url, json=payload, timeout=5)
    except: pass

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: PRODUCTION READY 💀\n" + "="*40)
    logger = TradeLogger()
    last_candle_ts = None 
    last_logged_ts = None
    AI_MODE = os.getenv("AI_MODE", "true").lower() == "true"

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA (Pandas handling) ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            # Gunakan timestamp agar aman dari clock drift
            current_ts = int(last_bar.name.timestamp())

            # --- 1. STATUS CHECK (Every Tick 2s) ---
            status = check_signal_status(last_bar['High'], last_bar['Low'], current_ts)
            
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                icon = "💰" if status == "TP_HIT" else "💀"
                send_telegram_html(f"{icon} <b>SIGNAL {status}</b>")
                save_state_atomic(active=False)
                status = None # FIX: Reset status lokal agar tidak skip sinyal baru
                print(f"✅ State Cleared: {status}")

            # --- 2. CANDLE GATE (Hanya kalkulasi jika candle baru) ---
            if current_ts != last_candle_ts:
                # Jalankan Rules & Logger
                contract = calculate_rules(data)
                if current_ts != last_logged_ts:
                    logger.log_contract(contract)
                    last_logged_ts = current_ts

                signal = contract["signal"]
                # Cek Sinyal & Signal Lock
                if signal in ["BUY", "SELL"] and status != "STILL_OPEN":
                    print(f"🤖 AI Judging {signal}...")
                    
                    # Kasih data "kenyang" ke AI
                    metrics = {
                        **contract.get("meta", {}).get("indicators", {}),
                        "spread": contract["meta"].get("spread"),
                        "price": last_bar["Close"],
                        "pdh_dist": contract["meta"].get("dist_pdh_pts"),
                        "pdl_dist": contract["meta"].get("dist_pdl_pts")
                    }
                    
                    judge = ask_ai_judge(signal, contract["reason"], metrics)
                    
                    # Normalize decision (Fix: strip & upper)
                    decision = str(judge.get("decision", "REJECT")).strip().upper()
                    
                    if decision == "APPROVE":
                        setup = contract["setup"]
                        icon = "🟢" if signal == "BUY" else "🔴"
                        
                        # Fix: Escape HTML reason dari AI
                        safe_reason = html.escape(str(judge.get("reason", "No Reason")))
                        
                        text = (f"{icon} <b>SIGNAL {signal} APPROVED</b>\n\n"
                                f"Entry: <code>{setup['entry']}</code>\n"
                                f"SL: <code>{setup['sl']}</code>\n"
                                f"TP: <code>{setup['tp']}</code>\n\n"
                                f"⚖️ <b>AI Debate:</b> <i>{safe_reason}</i>")
                        
                        send_telegram_html(text)
                        
                        # FIX: Gunakan Named Arguments agar tidak geser posisi
                        save_state_atomic(
                            active=True,
                            sig_type=signal,
                            sl=setup['sl'],
                            tp=setup['tp'],
                            entry=setup['entry'],
                            reason=judge.get("reason", ""),
                            opened_at_ts=current_ts
                        )
                        print(f"✅ {signal} SENT & LOCKED")
                    else:
                        print(f"❌ AI REJECTED: {judge.get('reason')}")
                
                last_candle_ts = current_ts

            time.sleep(2)
        except KeyboardInterrupt: sys.exit()
        except Exception as e: print(f"❌ Main Loop Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
