from dotenv import load_dotenv
load_dotenv() 

import time
import os
import sys
import requests
import html
import json
from datetime import datetime, timezone

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
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=5
        )
    except: pass

def run_diagnostics():
    """
    PRE-FLIGHT CHECK: Pastikan Server, Waktu, dan Data sehat sebelum trading.
    """
    print("\n🕵️ RUNNING PRE-FLIGHT DIAGNOSTICS...")
    
    # 1. Cek Koneksi Data
    print("[1/4] Checking Market Data Feed...", end=" ")
    data = get_market_data()
    if not data or 'm5' not in data or data['m5'].empty:
        print("❌ FAILED! (No Data)")
        return False
    print(f"✅ OK ({len(data['m5'])} candles)")

    # 2. Cek Time Sync (Vital buat Scalping)
    print("[2/4] Checking Server Time Sync...", end=" ")
    meta = data.get('meta', {})
    tick_msc = int(meta.get("tick_time_msc") or 0)
    
    if tick_msc == 0:
        print("❌ FAILED! (No Tick Timestamp)")
        return False
        
    server_ts = tick_msc / 1000.0
    local_ts = time.time()
    lag = local_ts - server_ts
    
    print(f"✅ OK (Lag: {lag:.3f}s)")
    if abs(lag) > 2.0:
        print(f"⚠️ WARNING: High Lag detected ({lag:.3f}s). Check VPS Clock!")

    # 3. Cek USD Unit Consistency (Harga Emas)
    print("[3/4] Checking Price Unit...", end=" ")
    last_close = data['m5']['Close'].iloc[-1]
    if last_close < 100 or last_close > 5000:
        print(f"⚠️ WARNING: Price {last_close} seems weird for XAUUSD. Check Symbol!")
    else:
        print(f"✅ OK (Price: {last_close})")

    # 4. AI Config Check
    print("[4/4] Checking AI Configuration...", end=" ")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("❌ FAILED! (No API Key)")
        return False
    print("✅ OK")

    print("\n🚀 SYSTEMS GO. STARTING ENGINE...\n")
    time.sleep(2)
    return True

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: PLATINUM (V18 SEALED) 💀\n" + "="*40)
    
    # JALANKAN DIAGNOSTIK DULU
    if not run_diagnostics():
        print("⛔ STARTUP ABORTED DUE TO SYSTEM FAILURE.")
        return

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
                
                # --- DEBUG PRINT (Buat Audit Log Realtime) ---
                # Print status tiap candle baru biar lu tau bot hidup
                obs_status = "Wait"
                if contract["signal"] != "WAIT": obs_status = f"SIGNAL {contract['signal']}"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Candle Close: {last_bar['Close']} | {obs_status} | Reason: {contract['reason']}")

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
                        # FIX: Safe Fingerprint
                        try:
                            e_r = round(float(setup.get('entry', 0) or 0), digits)
                            sl_r = round(float(setup.get('sl', 0) or 0), digits)
                            tp_r = round(float(setup.get('tp', 0) or 0), digits)
                        except:
                            e_r = str(setup.get('entry', 'err'))
                            sl_r = str(setup.get('sl', 'err'))
                            tp_r = str(setup.get('tp', 'err'))

                        current_fingerprint = f"{current_ts}_{signal}_{e_r}_{sl_r}_{tp_r}"
                        
                        if current_fingerprint != last_ai_fingerprint:
                            last_ai_fingerprint = current_fingerprint 
                            
                            print(f"🤖 AI Judging {signal}...")
                            
                            # --- FIX PLUMBING (V18 VERIFIED) ---
                            meta = contract.get("meta", {})
                            
                            metrics = {
                                **meta.get("indicators", {}),
                                "warnings": meta.get("warnings", []),
                                "tick_lag_sec": meta.get("tick_lag_sec", 0),
                                "tick_lag_sec_raw": meta.get("tick_lag_sec_raw", 0),
                                "spread": meta.get("spread", 0),
                                "risk_audit": meta.get("risk_audit", {}),
                                "price": meta.get("candle", {}).get("close", 0)
                            }
                            
                            # DEBUG: DUMP METRICS UNTUK AUDIT (Opsional, print di console)
                            # print(json.dumps(metrics, indent=2, default=str))

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
                                    print("🚨 WRITE FAIL!")
                            else:
                                print(f"❌ AI REJECTED: {judge.get('reason')}")
                
                last_candle_ts = current_ts

            time.sleep(2)
        except KeyboardInterrupt: sys.exit()
        except Exception as e: print(f"❌ Main Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
