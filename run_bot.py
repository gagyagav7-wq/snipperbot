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
    PRE-FLIGHT CHECK V20: FORT KNOX SAFETY.
    Cek Tick, Cek Candle Freshness, Cek Unit, Cek Jam.
    """
    print("\n🕵️ RUNNING PRE-FLIGHT DIAGNOSTICS (V20 FORT KNOX)...")

    # 1. Cek Koneksi & Data Frame
    print("[1/6] Checking Market Data Feed...", end=" ")
    data = get_market_data()
    if not data or 'm5' not in data or data['m5'].empty:
        print("❌ FAILED! (No Data / Empty DataFrame)")
        return False
    print(f"✅ OK ({len(data['m5'])} candles)")

    # 2. Cek Candle Freshness (PENTING: Anti Data Basi)
    print("[2/6] Checking Candle Freshness...", end=" ")
    last_candle_ts = data['m5'].iloc[-1].name
    # Ensure UTC
    if getattr(last_candle_ts, "tzinfo", None) is None: 
        last_candle_ts = last_candle_ts.tz_localize("UTC")
    
    candle_age = time.time() - last_candle_ts.timestamp()
    # M5 candle baru muncul tiap 5 menit (300s). Toleransi max 8 menit (480s).
    if candle_age > 480:
        print(f"❌ FAILED! (Stale Candle: {candle_age:.0f}s old). Data feed stuck?")
        return False
    print(f"✅ OK (Candle Age: {candle_age:.0f}s)")

    # 3. Cek Integritas Tick
    print("[3/6] Checking Tick Integrity...", end=" ")
    tick = data.get("tick", {})
    bid = float(tick.get("bid", 0) or 0)
    ask = float(tick.get("ask", 0) or 0)
    
    if bid <= 0 or ask <= 0:
        print(f"❌ FAILED! (Invalid Price: Bid={bid}, Ask={ask})")
        return False
    spread = abs(ask - bid)
    print(f"✅ OK (Bid={bid}, Ask={ask}, Spread={spread:.3f})")

    # 4. Cek Time Sync
    print("[4/6] Checking Server Time Sync...", end=" ")
    meta = data.get('meta', {})
    tick_msc = int(meta.get("tick_time_msc") or 0)
    tick_sec = int(meta.get("tick_time") or 0)

    broker_ts = (tick_msc / 1000.0) if tick_msc > 0 else (float(tick_sec) if tick_sec > 0 else 0)
    
    if broker_ts <= 0:
        print("❌ FAILED! (No Broker Timestamp)")
        return False

    lag = time.time() - broker_ts
    print(f"✅ Data Age: {lag:.3f}s")

    if lag < -10:
        print(f"⛔ FATAL ERROR: Severe Clock Drift ({lag:.3f}s). VPS ahead of Broker!")
        return False
    if lag > 8:
        print(f"⛔ FATAL ERROR: Critical Lag ({lag:.3f}s). Connection too slow.")
        return False
    if abs(lag) > 2:
        print(f"⚠️ WARNING: Noticeable Lag ({lag:.3f}s).")

    # 5. Cek Point & Harga (Safe Guard Math)
    print("[5/6] Checking Price Unit...", end=" ")
    last_close = float(data['m5']['Close'].iloc[-1])
    point = float(tick.get("point", 0.01) or 0.01)
    
    if point <= 0: # Anti Zero Division / Log Error
        print(f"❌ FAILED! (Invalid Point Value: {point})")
        return False

    if last_close < 100 or last_close > 5000:
        print(f"⚠️ WARNING: Price {last_close} seems weird for XAUUSD.")
    else:
        print(f"✅ OK (Price: {last_close}, Point: {point})")

    # 6. Cek AI Key
    print("[6/6] Checking AI Configuration...", end=" ")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("❌ FAILED! (No API Key found)")
        return False
    print("✅ OK")

    print("\n🚀 SYSTEMS GO. STARTING ENGINE...\n")
    time.sleep(1)
    return True

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: PLATINUM (V20 FORT KNOX) 💀\n" + "="*40)
    
    # 1. DIAGNOSTIK AWAL (Fail-Closed)
    if not run_diagnostics():
        msg = "⛔ <b>STARTUP ABORTED</b>\nPre-flight diagnostics failed. Check VPS clock / Data Feed."
        print(msg)
        send_telegram_html(msg)
        return # STOP PROGRAM

    # 2. KIRIM NOTIFIKASI STARTUP SUKSES
    send_telegram_html("🚀 <b>SYSTEM STARTED</b>\nDiagnostics Passed. Engine Running.")

    logger = TradeLogger()
    
    last_candle_ts = None
    last_logged_ts = None
    last_ai_fingerprint = None
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
            
            # FIX: Auto-Detect Digits (Safe Math)
            point = float(tick.get("point", 0.01) or 0.01)
            if point <= 0: point = 0.01 # Fallback biar gak error log10
            
            raw_digits = tick.get("digits")
            if raw_digits is not None:
                digits = int(raw_digits)
            else:
                try:
                    digits = max(0, int(round(-math.log10(point))))
                except:
                    digits = 2 # Fallback terakhir

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
                
                # Runtime Critical Guard (Lag/Drift)
                # Indikator V17+ return reason spesifik untuk drift/lag parah
                is_critical = "Critical Lag" in contract["reason"] or "Severe Clock Drift" in contract["reason"]
                
                if is_critical:
                    now = time.time()
                    if now - last_lag_alert_ts > 300: # Alert max tiap 5 menit
                        send_telegram_html(f"⚠️ <b>CONNECTION UNSTABLE</b>\nBot paused logic.\nReason: {contract['reason']}")
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
                            
                            # Plumbing Data V18/V19/V20
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
        except Exception as e: 
            # Critical Error Alert
            err_msg = f"❌ <b>BOT CRASHED</b>\nError: {str(e)}"
            print(err_msg)
            send_telegram_html(err_msg)
            time.sleep(10) # Jeda biar gak spam kalau auto-restart

if __name__ == "__main__": main()
