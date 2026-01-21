import time
import os
import sys
from datetime import datetime
from src.data_loader import get_market_data
from src.indicators import calculate_rules
from src.logger import TradeLogger
from src.state_manager import check_signal_status, save_signal_state
from src.ai_engine import ask_ai_judge

def main():
    print("="*40)
    print("💀 GOLD KILLER PRO: THE TANK 💀")
    print("="*40)

    logger = TradeLogger()
    last_candle_time = None # PINTU GERBANG UTAMA

    while True:
        try:
            data = get_market_data()
            if not data:
                time.sleep(5)
                continue

            # --- PREP DATA ---
            df_5m = data['m5']
            last_bar = df_5m.iloc[-1]
            current_candle_time = str(last_bar.name)
            
            # --- 1. CEK STATUS SIGNAL JALAN ---
            status = check_signal_status(last_bar['High'], last_bar['Low'])
            if status in ["TP_HIT", "SL_HIT", "EXPIRED"]:
                save_signal_state(active=False)
                print(f"✅ State Cleared: {status}")

            # --- 2. JALANKAN RULES ---
            contract = calculate_rules(data)

            # --- 3. CANDLE-GATE (GERBANG ANTI-SPAM) ---
            if current_candle_time != last_candle_time:
                # A. Log cuma 1x per candle
                logger.log_contract(contract)
                
                # B. Cek Sinyal cuma 1x per candle
                signal = contract["signal"]
                if signal in ["BUY", "SELL"] and status != "STILL_OPEN":
                    print(f"🤖 AI Judging {signal}...")
                    
                    # Kasih data lengkap ke AI
                    rich_metrics = {
                        **contract.get("meta", {}).get("indicators", {}),
                        "spread": contract["meta"].get("spread"),
                        "close": last_bar["Close"]
                    }
                    
                    judge = ask_ai_judge(signal, contract["reason"], rich_metrics)
                    
                    if judge["decision"] == "APPROVE":
                        setup = contract["setup"]
                        # Kirim Tele & Lock State
                        save_signal_state(True, signal, setup['sl'], setup['tp'], setup['entry'], current_candle_time)
                        print(f"🚀 {signal} APPROVED & SENT")
                    else:
                        print(f"❌ AI REJECTED: {judge['reason']}")
                
                last_candle_time = current_candle_time # Tutup gerbang

            time.sleep(2)

        except KeyboardInterrupt: sys.exit()
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__": main()
