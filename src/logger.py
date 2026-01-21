import csv
import os
import time
from datetime import datetime

class TradeLogger:
    def __init__(self, filename_prefix="trade_log"):
        # Absolute path setup
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_dir = os.path.join(base_dir, "logs")
        self.filename_prefix = filename_prefix
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        self.fields = [
            "timestamp_wib", "signal", "reason", "price_close_m5", 
            "spread", "rsi", "adx", "safe_dist_pts", "actual_dist_pts",
            "safe_dist_price", "actual_dist_price", # [NEW] Tambah Price buat audit enak
            "stop_level", "freeze_level", "tick_lag_sec", "warnings"
        ]

    def _get_file_path(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{self.filename_prefix}_{today}.csv")

    def log_contract(self, contract):
        if not contract or contract.get("reason") in ["Initializing...", "Data Empty"]:
            return

        file_path = self._get_file_path()
        file_exists = os.path.isfile(file_path)

        meta = contract.get("meta", {})
        tick = contract.get("tick", {})
        inds = meta.get("indicators", {}) 
        candle = meta.get("candle", {})

        ts_obj = contract.get("timestamp")
        ts_str = ts_obj.strftime("%Y-%m-%d %H:%M:%S") if ts_obj else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # [FIX] Lag Calculation: time.time() & Clamp Negative
        tick_time_msc = meta.get("tick_time_msc")
        tick_time_sec = meta.get("tick_time")
        
        now_ts = time.time() # [FIX] Pake time.time() biar konsisten epoch
        lag = 0.0
        
        if tick_time_msc and tick_time_msc > 0:
            broker_ts = tick_time_msc / 1000.0
            raw_lag = now_ts - broker_ts
            # Clamp: Kalau negatif (PC telat dikit), anggap 0 biar log gak aneh
            lag = max(0.0, round(raw_lag, 3))
        elif tick_time_sec:
            raw_lag = now_ts - tick_time_sec
            lag = max(0.0, round(raw_lag, 3))

        # Distances (Points & Price)
        dist_actual_pts = meta.get("dist_pdh_pts") or meta.get("dist_pdl_pts") or 0
        dist_safe_pts   = meta.get("safe_dist_pts", 0)
        
        # [NEW] Audit Price Distance
        dist_actual_price = meta.get("dist_pdh_price") or meta.get("dist_pdl_price") or 0
        dist_safe_price   = meta.get("safe_dist_price", 0)

        row = {
            "timestamp_wib": ts_str,
            "signal": contract.get("signal"),
            "reason": contract.get("reason"),
            "price_close_m5": candle.get("close", 0),
            "spread": meta.get("spread"),
            "rsi": inds.get("rsi", "N/A"),
            "adx": inds.get("adx", "N/A"),
            "safe_dist_pts": round(dist_safe_pts, 1) if dist_safe_pts else 0,
            "actual_dist_pts": round(dist_actual_pts, 1) if dist_actual_pts else 0,
            "safe_dist_price": round(dist_safe_price, 2) if dist_safe_price else 0,
            "actual_dist_price": round(dist_actual_price, 2) if dist_actual_price else 0,
            "stop_level": tick.get("stop_level"),
            "freeze_level": tick.get("freeze_level"),
            "tick_lag_sec": lag, 
            "warnings": "; ".join(meta.get("warnings", []))
        }

        try:
            with open(file_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                if not file_exists: writer.writeheader()
                writer.writerow(row)
        except Exception as e:
            print(f"❌ Logger Error: {e}")
