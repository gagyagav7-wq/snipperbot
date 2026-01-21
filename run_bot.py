import time
import os
import sys
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger
from src.state_manager import check_trade_status, save_state_atomic
from src.ai_engine import ask_ai_judge

load_dotenv()
AI_MODE = True # Switch ke False jika ingin Rules saja

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except: pass

def main():
    print("="*40)
    print("💀 GOLD KILLER PRO: JUDGEMENT MODE 💀")
    print("="*40)

    logger = TradeLogger()
    last_processed_candle = None # ANTI-SPAM GATE
    last_print_reason = ""

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5)
                continue

            # --- 1. DATA PREP (Pandas Handling) ---
            # data['m5'] dan data['m15'] sekarang adalah DataFrame
            df_5m = data['m5']
            last_closed_bar = df_5m.iloc[-1] # Bar terakhir yang SUDAH CLOSE
            current_candle_time = str(last_closed_bar.name)

            # --- 2. UPDATE STATE (Cek SL/TP) ---
            status = check_trade_status(last_closed_bar['High'], last_closed_bar['Low'])
            
            if status in ["TP_HIT", "SL_HIT"]:
                icon = "💰" if status == "TP_HIT" else "💀"
                send_telegram(f"{icon} *SIGNAL CLOSED:* {status}")
                save_state_atomic(active=False)
                print(f"\n{icon} {status}! State Cleared.")

            # --- 3. RUN STRATEGY ---
            contract = calculate_rules(data)
            logger.log_contract(contract)

            # --- 4. TERMINAL FEEDBACK ---
            current_reason = contract["reason"]
            signal = contract["signal"]
            timestamp_str = contract["timestamp"].strftime("%H:%M") if contract["timestamp"] else "--:--"

            if current_reason != last_print_reason:
                print(f"[{timestamp_str}] {signal} | {current_reason}")
                last_print_reason = current_reason

            # --- 5. SIGNAL EXECUTION ---
            if signal in ["BUY", "SELL"]:
                # A. Proteksi: Masih ada signal aktif?
                if status == "STILL_OPEN":
                    continue

                # B. Anti-Spam: Apakah candle ini sudah diproses?
                if current_candle_time == last_processed_candle:
                    continue

                # C. AI JUDGE DEBATE
                if AI_MODE:
                    print(f"🤖 AI is judging {signal} @ {current_candle_time}...")
                    metrics = contract.get("meta", {}).get("indicators", {})
                    judge = ask_ai_judge(signal, contract["reason"], metrics)
                    
                    if judge.get("decision") == "APPROVE":
                        setup = contract["setup"]
                        icon = "🟢" if signal == "BUY" else "🔴"
                        
                        msg = f"{icon} *SIGNAL {signal} APPROVED*\n"
                        msg += f"Confidence: {judge.get('confidence')}% | ID: {current_candle_time[-5:]}\n\n"
                        msg += f"Entry: `{setup['entry']}`\n"
                        msg += f"SL: `{setup['sl']}`\n"
                        msg += f"TP: `{setup['tp']}`\n\n"
                        msg += f"⚖️ *AI Debate:* _{judge.get('reason')}_\n"
                        msg += f"🚩 *Risks:* {', '.join(judge.get('risk_flags', []))}"

                        send_telegram(msg)
                        save_state_atomic(
                            active=True, 
                            sig_type=signal, 
                            sl=setup['sl'], 
                            tp=setup['tp'], 
                            entry=setup['entry'],
                            reason=judge.get('reason'),
                            opened_at=current_candle_time
                        )
                        last_processed_candle = current_candle_time
                        print(f"✅ {signal} SENT & LOCKED")
                    else:
                        # Reject tetap dihitung sebagai 'sudah diproses' biar gak spam AI
                        last_processed_candle = current_candle_time
                        print(f"❌ AI REJECTED: {judge.get('reason')}")

            time.sleep(2)

        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
