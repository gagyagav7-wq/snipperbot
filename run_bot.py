from dotenv import load_dotenv
load_dotenv() 

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
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=5
        )
    except: pass

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: PLATINUM EDITION 💀\n" + "="*40)
    logger = TradeLogger()
    
    last_candle_ts = None
    last_logged_ts = None
    last_ai_fingerprint = None

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            ts = last_bar.name
            
            # UTC Safe Check
            if getattr(ts, "tzinfo", None) is None: ts = ts.tz_localize("UTC")
            current_ts = int(ts.timestamp())

            tick = data.get("tick", {})
            bid = tick.get("bid", 0.0)
            ask = tick.get("ask", 0.0)
            digits = int(tick.get("digits", 2)) 

            # --- 1. STATUS CHECK ---
            status = check_signal_status(last_bar['High'], last_bar['Low'], bid, ask)
            
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
                
                # --- 3. AI GATE ---
                if signal in ["BUY", "SELL"] and status == "NONE":
                    setup = contract.get("setup", {})
                    if not setup or "entry" not in setup:
                        print("⚠️ Setup incomplete, skipping...")
                    else:
                        # FIX: Safe Fingerprint (String Fallback)
                        # Kalau data error, jangan jadi 0_0_0, tapi pakai string aslinya biar unik
                        try:
                            e_val = float(setup.get('entry', 0) or 0)
                            sl_val = float(setup.get('sl', 0) or 0)
                            tp_val = float(setup.get('tp', 0) or 0)
                            
                            e_r = round(e_val, digits)
                            sl_r = round(sl_val, digits)
                            tp_r = round(tp_val, digits)
                        except:
                            # Kalau gagal cast, pakai raw string biar fingerprint tetep jalan
                            e_r = str(setup.get('entry', 'err'))
                            sl_r = str(setup.get('sl', 'err'))
                            tp_r = str(setup.get('tp', 'err'))

                        current_fingerprint = f"{current_ts}_{signal}_{e_r}_{sl_r}_{tp_r}"
                        
                        if current_fingerprint != last_ai_fingerprint:
                            last_ai_fingerprint = current_fingerprint 
                            
                            print(f"🤖 AI Judging {signal}...")
                            metrics = {
                                **contract.get("meta", {}).get("indicators", {}),
                                "spread": contract["meta"].get("spread"),
                                "price": last_bar["Close"]
                            }
                            
                            judge = ask_ai_judge(signal, contract["reason"], metrics)
                            decision = str(judge.get("decision", "REJECT")).strip().upper()
                            
                            if decision == "APPROVE":
                                icon = "🟢" if signal == "BUY" else "🔴"
                                
                                ai_reason = html.escape(str(judge.get("reason", "No Reason")))
                                e_entry = html.escape(str(setup['entry']))
                                e_sl = html.escape(str(setup['sl']))
                                e_tp = html.escape(str(setup['tp']))
                                
                                text = (f"{icon} <b>SIGNAL {signal} APPROVED</b>\n\n"
                                        f"Entry: <code>{e_entry}</code>\n"
                                        f"SL: <code>{e_sl}</code>\n"
                                        f"TP: <code>{e_tp}</code>\n\n"
                                        f"⚖️ <b>AI Debate:</b> <i>{ai_reason}</i>")
                                
                                send_telegram_html(text)
                                
                                if save_state_atomic(
                                    active=True,
                                    sig_type=signal,
                                    sl=setup['sl'],
                                    tp=setup['tp'],
                                    entry=setup['entry'],
                                    reason=judge.get("reason", ""),
                                    candle_ts=current_ts
                                ):
                                    status = "STILL_OPEN"
                                    print(f"✅ {signal} SENT & LOCKED")
                                else:
                                    print("🚨 WRITE FAIL! Signal ignored.")
                                    send_telegram_html("⚠️ <b>SYSTEM ERROR:</b> Disk Write Failed!")
                            else:
                                print(f"❌ AI REJECTED: {judge.get('reason')}")
                
                last_candle_ts = current_ts

            time.sleep(2)
        except KeyboardInterrupt: sys.exit()
        except Exception as e: print(f"❌ Main Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
