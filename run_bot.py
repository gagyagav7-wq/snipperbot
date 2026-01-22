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
    PRE-FLIGHT CHECK V21.1: STRICT AI & BROKER TIME.
    """
    print("\n🕵️ RUNNING PRE-FLIGHT DIAGNOSTICS (V21.1 DIAMOND)...")

    # 1. Cek Data Feed
    print("[1/7] Checking Market Data Feed...", end=" ")
    data = get_market_data()
    if not data or 'm5' not in data or data['m5'].empty:
        print("❌ FAILED! (No Data)")
        return False
    print(f"✅ OK ({len(data['m5'])} candles)")

    # 2. Cek Server Time Sync
    print("[2/7] Checking Server Time Sync...", end=" ")
    meta = data.get('meta', {})
    tick_msc = int(meta.get("tick_time_msc") or 0)
    tick_sec = int(meta.get("tick_time") or 0)
    broker_ts = (tick_msc / 1000.0) if tick_msc > 0 else (float(tick_sec) if tick_sec > 0 else 0)
    
    if broker_ts <= 0:
        print("❌ FAILED! (No Broker Timestamp)")
        return False
    
    lag = time.time() - broker_ts
    print(f"✅ Lag: {lag:.3f}s")

    if lag < -10:
        print(f"⛔ FATAL: Severe Clock Drift ({lag:.3f}s). VPS ahead of Broker!")
        return False
    if lag > 8:
        print(f"⛔ FATAL: Critical Lag ({lag:.3f}s). Connection too slow.")
        return False

    # 3. Cek Candle Freshness (vs Broker Time)
    print("[3/7] Checking Candle Validty...", end=" ")
    last_candle_ts = data['m5'].iloc[-1].name
    
    # FIX: Strict Timezone Logic
    if getattr(last_candle_ts, "tzinfo", None) is None: 
        last_candle_ts = last_candle_ts.tz_localize("UTC")
    else:
        last_candle_ts = last_candle_ts.tz_convert("UTC")
    
    # Compare vs Broker TS (Truth Source)
    candle_gap = broker_ts - last_candle_ts.timestamp()
    
    if candle_gap > 600: 
        print(f"❌ FAILED! Candle vs Broker Gap too big ({candle_gap:.0f}s). Feed Stuck?")
        return False
    elif candle_gap < -600:
        print(f"❌ FAILED! Candle from future? Gap: {candle_gap:.0f}s.")
        return False
    print(f"✅ OK (Gap: {candle_gap:.0f}s)")

    # 4. Tick Integrity
    print("[4/7] Checking Tick Integrity...", end=" ")
    tick = data.get("tick", {})
    bid = float(tick.get("bid", 0) or 0)
    ask = float(tick.get("ask", 0) or 0)
    if bid <= 0 or ask <= 0:
        print(f"❌ FAILED! (Invalid Price)")
        return False
    spread = abs(ask - bid)
    print(f"✅ OK (Spread: {spread:.3f})")

    # 5. Price Unit
    print("[5/7] Checking Price Unit...", end=" ")
    last_close = float(data['m5']['Close'].iloc[-1])
    point = float(tick.get("point", 0.01) or 0.01)
    if point <= 0:
        print(f"❌ FAILED! (Invalid Point: {point})")
        return False
    if last_close < 100 or last_close > 5000:
        print(f"⚠️ WARNING: Price {last_close} seems weird.")
    else:
        print(f"✅ OK")

    # 6. API Key Check
    print("[6/7] Checking API Key...", end=" ")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("❌ FAILED! (No API Key)")
        return False
    print("✅ OK")

    # 7. AI LIVE PING (Strict Validation)
    print("[7/7] Pinging AI Brain...", end=" ")
    dummy_metrics = {"trend_m15": "NEUTRAL", "price": last_close, "warnings": ["DIAGNOSTIC_TEST"]}
    try:
        response = ask_ai_judge("BUY", "SYSTEM_DIAGNOSTIC", dummy_metrics)
        decision = str(response.get("decision", "")).upper()
        
        # FIX: Validasi Jawaban Harus Masuk Akal
        if decision in ["APPROVE", "REJECT"]:
            print("✅ ALIVE & VALID")
        else:
            print(f"❌ FAILED! (Invalid Decision: {decision})")
            return False
    except Exception as e:
        print(f"❌ FAILED! (Connection Error: {e})")
        return False

    print("\n🚀 SYSTEMS GO. STARTING ENGINE...\n")
    time.sleep(1)
    return True

def main():
    print("="*40 + "\n💀 GOLD KILLER PRO: V21.1 (DIAMOND SEALED) 💀\n" + "="*40)
    
    if not run_diagnostics():
        msg = "⛔ <b>STARTUP ABORTED</b>\nPre-flight diagnostics failed. Check terminal."
        print(msg)
        send_telegram_html(msg)
        return

    send_telegram_html("🚀 <b>SYSTEM STARTED (V21.1)</b>\nAll Systems Green. Trading Active.")

    logger = TradeLogger()
    
    last_candle_ts = None
    last_logged_ts = None
    last_ai_fingerprint = None
    last_lag_alert_ts = 0 
    last_freeze_alert_ts = 0

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5); continue

            # --- PREP DATA (RUNTIME CHECK) ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            ts = last_bar.name
            
            # FIX: Strict Timezone Standard
            if getattr(ts, "tzinfo", None) is None: 
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
            
            current_ts = int(ts.timestamp())

            # Extract Meta for Time Source
            meta = data.get('meta', {})
            tick_msc = int(meta.get("tick_time_msc") or 0)
            tick_sec = int(meta.get("tick_time") or 0)
            broker_ts = (tick_msc / 1000.0) if tick_msc > 0 else (float(tick_sec) if tick_sec > 0 else 0)
            
            # Fallback jika broker_ts kosong (should be rare if diag passed)
            if broker_ts <= 0: broker_ts = time.time()

            # FIX: Runtime Candle Freshness (vs Broker Time)
            candle_age = broker_ts - current_ts
            
            if candle_age > 480: # 8 mins
                now = time.time()
                if now - last_freeze_alert_ts > 600: 
                    print(f"⚠️ DATA FREEZE DETECTED! Candle vs Broker Gap: {candle_age:.0f}s")
                    send_telegram_html(f"⚠️ <b>DATA FREEZE</b>\nCandle stuck for {candle_age:.0f}s. Check API.")
                    last_freeze_alert_ts = now
                time.sleep(10)
                continue 

            tick = data.get("tick", {})
            bid = float(tick.get("bid", 0) or 0)
            ask = float(tick.get("ask", 0) or 0)
            
            point = float(tick.get("point", 0.01) or 0.01)
            if point <= 0: point = 0.01 
            
            raw_digits = tick.get("digits")
            if raw_digits is not None:
                digits = int(raw_digits)
            else:
                try: digits = max(0, int(round(-math.log10(point))))
                except: digits = 2

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
                
                # Critical Lag Guard
                is_critical = "Critical Lag" in contract["reason"] or "Severe Clock Drift" in contract["reason"]
                if is_critical:
                    now = time.time()
                    if now - last_lag_alert_ts > 300: 
                        send_telegram_html(f"⚠️ <b>CONNECTION UNSTABLE</b>\nBot paused.\nReason: {contract['reason']}")
                        last_lag_alert_ts = now

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
            err_msg = f"❌ <b>BOT CRASHED</b>\nError: {str(e)}"
            print(err_msg)
            send_telegram_html(err_msg)
            time.sleep(10)

if __name__ == "__main__": main()
