from dotenv import load_dotenv
load_dotenv() 

import time
import os
import sys
import requests
import html
import json
import math
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
    PRE-FLIGHT CHECK V19: FAIL-CLOSED POLICY.
    Bot menolak nyala jika ada indikasi data busuk atau lag parah.
    """
    print("\n🕵️ RUNNING PRE-FLIGHT DIAGNOSTICS (INSTITUTIONAL GRADE)...")

    # 1. Cek Koneksi & Data Frame
    print("[1/5] Checking Market Data Feed...", end=" ")
    data = get_market_data()
    if not data or 'm5' not in data or data['m5'].empty:
        print("❌ FAILED! (No Data / Empty DataFrame)")
        return False
    print(f"✅ OK ({len(data['m5'])} candles)")

    # 2. Cek Integritas Tick (Bid/Ask Real)
    print("[2/5] Checking Tick Integrity...", end=" ")
    tick = data.get("tick", {})
    bid = float(tick.get("bid", 0) or 0)
    ask = float(tick.get("ask", 0) or 0)
    
    if bid <= 0 or ask <= 0:
        print(f"❌ FAILED! (Invalid Price: Bid={bid}, Ask={ask}. Market Closed?)")
        return False
        
    spread = abs(ask - bid)
    print(f"✅ OK (Bid={bid}, Ask={ask}, Spread={spread:.3f})")

    # 3. Cek Time Sync (CRITICAL FAIL-SAFE)
    print("[3/5] Checking Server Time Sync...", end=" ")
    meta = data.get('meta', {})
    tick_msc = int(meta.get("tick_time_msc") or 0)
    tick_sec = int(meta.get("tick_time") or 0)

    # Prioritas MSC, fallback ke SEC
    broker_ts = (tick_msc / 1000.0) if tick_msc > 0 else (float(tick_sec) if tick_sec > 0 else 0)
    
    if broker_ts <= 0:
        print("❌ FAILED! (No Broker Timestamp found)")
        return False

    lag = time.time() - broker_ts
    print(f"✅ Data Age: {lag:.3f}s")

    # HARD RULES (Sesuai Indicators V17)
    if lag < -10:
        print(f"⛔ FATAL ERROR: Severe Clock Drift ({lag:.3f}s). VPS time is ahead of Broker!")
        return False
    if lag > 8:
        print(f"⛔ FATAL ERROR: Critical Lag ({lag:.3f}s). Connection is too slow for scalping.")
        return False
    if abs(lag) > 2:
        print(f"⚠️ WARNING: Noticeable Lag ({lag:.3f}s). Scalping might be risky.")

    # 4. Cek Kewarasan Harga (Unit Check)
    print("[4/5] Checking Price Unit...", end=" ")
    last_close = float(data['m5']['Close'].iloc[-1])
    if last_close < 100 or last_close > 5000:
        print(f"⚠️ WARNING: Price {last_close} seems weird for XAUUSD. Check Symbol Mapping!")
    else:
        print(f"✅ OK (Price: {last_close})")

    # 5. Cek Kunci AI
    print("[5/5] Checking AI Configuration...", end=" ")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("❌ FAILED! (No API Key found in .env)")
        return False
    print("✅ OK")

    print("\n🚀 SYSTEMS GO. STARTING ENGINE...\n")
    time.sleep(1)
    return True

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: PLATINUM (V19 FINAL) 💀\n" + "="*40)
    
    # WAJIB LOLOS DIAGNOSTIK
    if not run_diagnostics():
        print("⛔ STARTUP ABORTED. FIX THE ERRORS ABOVE.")
        return

    logger = TradeLogger()
    
    last_candle_ts = None
    last_logged_ts = None
    last_ai_fingerprint = None
    
    # Runtime Lag Alert Limiter (biar gak spam telegram)
    last_lag_alert_ts = 0 

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            ts = last_bar.name
            
            if getattr(ts, "tzinfo", None) is None: ts = ts.tz_localize("UTC")
            current_ts = int(ts.timestamp())

            tick = data.get("tick", {})
            bid = float(tick.get("bid", 0) or 0)
            ask = float(tick.get("ask", 0) or 0)
            
            # FIX: Auto-Detect Digits dari Point (Matematis)
            point = float(tick.get("point", 0.01) or 0.01)
            raw_digits = tick.get("digits")
            if raw_digits is not None:
                digits = int(raw_digits)
            else:
                # Kalau broker gak kasih digits, hitung dari log10 point
                # Contoh: point 0.01 -> log10(-2) -> 2 digits
                digits = max(0, int(round(-math.log10(point))))

            # --- 1. STATUS CHECK ---
            status = check_signal_status(last_bar['High'], last_bar['Low'], bid, ask)
            
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                finished = status
                icon = "💰" if finished == "TP_HIT" else "💀"
                send_telegram_html(f"{icon} <b>SIGNAL FINISHED:</b> {finished}")
                save_state_atomic(active=False) 
                status = "NONE" 
                print(f"✅ State Cleared: {finished}")

            # --- 2. CANDLE GATE & LOGIC ---
            if current_ts != last_candle_ts:
                contract = calculate_rules(data)
                
                # Runtime Critical Lag Alert (Via Telegram)
                # Indikator V17 akan return reason "Critical Lag..." jika lag > 8s
                if "Critical Lag" in contract["reason"]:
                    now = time.time()
                    if now - last_lag_alert_ts > 300: # Alert max tiap 5 menit
                        send_telegram_html(f"⚠️ <b>CRITICAL LAG WARNING</b>\nBot paused due to connection instability.\nReason: {contract['reason']}")
                        last_lag_alert_ts = now

                # Debug Print
                obs_status = "Wait"
                if contract["signal"] != "WAIT": obs_status = f"SIGNAL {contract['signal']}"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] P:{last_bar['Close']} | {obs_status} | {contract['reason']}")

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
                        # Safe Fingerprint
                        try:
                            e_r = round(float(setup.get('entry', 0) or 0), digits)
                            sl_r = round(float(setup.get('sl', 0) or 0), digits)
                            tp_r = round(float(setup.get('tp', 0) or 0), digits)
                        except:
                            e_r, sl_r, tp_r = "ERR", "ERR", "ERR"

                        current_fingerprint = f"{current_ts}_{signal}_{e_r}_{sl_r}_{tp_r}"
                        
                        if current_fingerprint != last_ai_fingerprint:
                            last_ai_fingerprint = current_fingerprint 
                            print(f"🤖 AI Judging {signal}...")
                            
                            # Plumbing Data V18/V19
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
