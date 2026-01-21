import csv
import os
import time
from datetime import datetime

class TradeLogger:
    def __init__(self, filename_prefix="trade_log"):
        # [FIX] Gunakan Absolute Path biar folder logs selalu di root project
        # Struktur: src/logger.py -> naik 1 level ke root -> folder logs
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_dir = os.path.join(base_dir, "logs")
        self.filename_prefix = filename_prefix
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # Header CSV Lengkap
        self.fields = [
            "timestamp_wib",    # Waktu Candle
            "signal",           # BUY/SELL/SKIP/NO
            "reason",           # Alasan
            "price_close_m5",   # [FIX] Close Candle M5 (bukan tick)
            "spread",           # Spread Broker
            "rsi", "adx",       # Indikator Utama
            "safe_dist_pts",    # Jarak Aman
            "actual_dist_pts",  # Jarak Aktual
            "stop_level",       # Broker Stop Level
            "freeze_level",     # Broker Freeze Level
            "tick_lag_sec",     # [FIX] Latency Presisi (detik.milidetik)
            "warnings"          # Warning list
        ]

    def _get_file_path(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{self.filename_prefix}_{today}.csv")

    def log_contract(self, contract):
        # Filter: Jangan log kalau data kosong/init
        if not contract or contract.get("reason") in ["Initializing...", "Data Empty"]:
            return

        file_path = self._get_file_path()
        file_exists = os.path.isfile(file_path)

        # Extract Data
        meta = contract.get("meta", {})
        tick = contract.get("tick", {})
        inds = meta.get("indicators", {}) 
        candle = meta.get("candle", {}) # [NEW] Ambil data candle

        # Timestamp Candle (WIB)
        ts_obj = contract.get("timestamp")
        ts_str = ts_obj.strftime("%Y-%m-%d %H:%M:%S") if ts_obj else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # [FIX] Hitung Latency/Lag dengan Presisi Tinggi (Msc)
        tick_time_msc = meta.get("tick_time_msc")
        tick_time_sec = meta.get("tick_time")
        
        now_ts = datetime.now().timestamp()
        lag = 0.0
        
        if tick_time_msc and tick_time_msc > 0:
            # Pake Milidetik (convert ke detik float)
            broker_ts = tick_time_msc / 1000.0
            lag = round(now_ts - broker_ts, 3)
        elif tick_time_sec:
            # Fallback ke detik
            lag = round(now_ts - tick_time_sec, 3)

        # Distances
        dist_actual = meta.get("dist_pdh_pts") or meta.get("dist_pdl_pts") or 0
        dist_safe   = meta.get("safe_dist_pts", 0)

        # Susun Baris Data
        row = {
            "timestamp_wib": ts_str,
            "signal": contract.get("signal"),
            "reason": contract.get("reason"),
            "price_close_m5": candle.get("close", 0), # [FIX] Pake Close Candle
            "spread": meta.get("spread"),
            "rsi": inds.get("rsi", "N/A"),
            "adx": inds.get("adx", "N/A"),
            "safe_dist_pts": round(dist_safe, 1) if dist_safe else 0,
            "actual_dist_pts": round(dist_actual, 1) if dist_actual else 0,
            "stop_level": tick.get("stop_level"),
            "freeze_level": tick.get("freeze_level"),
            "tick_lag_sec": lag, # Latency realtime
            "warnings": "; ".join(meta.get("warnings", []))
        }

        try:
            with open(file_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
        except Exception as e:
            print(f"❌ Logger Error: {e}")
