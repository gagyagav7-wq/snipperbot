import csv
import os
from datetime import datetime

class TradeLogger:
    def __init__(self, filename_prefix="trade_log"):
        self.log_dir = "logs"
        self.filename_prefix = filename_prefix
        
        # Buat folder logs kalau belum ada
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # Header CSV Lengkap (Audit Trail)
        self.fields = [
            "timestamp_wib",    # Waktu Candle
            "signal",           # BUY/SELL/SKIP/NO
            "reason",           # Alasan lengkap
            "price_close",      # Harga Close M5
            "spread",           # Spread Broker
            "rsi", "adx",       # Indikator Utama
            "safe_dist_pts",    # Jarak Aman (Points)
            "actual_dist_pts",  # Jarak Aktual ke PDH/PDL
            "stop_level",       # Broker Stop Level
            "freeze_level",     # Broker Freeze Level
            "tick_lag",         # Latency Broker
            "warnings"          # Clock drift, dll
        ]

    def _get_file_path(self):
        # Generate nama file berdasarkan tanggal HARI INI
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{self.filename_prefix}_{today}.csv")

    def log_contract(self, contract):
        # 1. Filter Log: Jangan catat kalau masih Initializing atau Data Kosong
        if not contract or contract.get("reason") in ["Initializing...", "Data Empty"]:
            return

        file_path = self._get_file_path()
        file_exists = os.path.isfile(file_path)

        # 2. Extract Data dengan Aman (Pake .get biar gak crash)
        meta = contract.get("meta", {})
        tick = contract.get("tick", {})
        inds = meta.get("indicators", {}) # Ambil dari update indicators.py tadi
        
        # Ambil Timestamp Candle (Lebih akurat dari waktu PC)
        ts_obj = contract.get("timestamp")
        ts_str = ts_obj.strftime("%Y-%m-%d %H:%M:%S") if ts_obj else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Cek Jarak Aktual (PDH atau PDL)
        dist_actual = meta.get("dist_pdh_pts") or meta.get("dist_pdl_pts") or 0
        if dist_actual: dist_actual = round(dist_actual, 1)

        # Cek Jarak Aman
        dist_safe = meta.get("safe_dist_pts", 0)
        if dist_safe: dist_safe = round(dist_safe, 1)

        # Hitung Tick Lag (Audit Latency)
        tick_time = meta.get("tick_time", 0)
        lag = 0
        if tick_time:
            lag = round(datetime.now().timestamp() - tick_time, 2)

        # 3. Susun Baris Data
        row = {
            "timestamp_wib": ts_str,
            "signal": contract.get("signal"),
            "reason": contract.get("reason"),
            "price_close": contract.get("tick", {}).get("bid", 0), # Close price approx (Bid)
            "spread": meta.get("spread"),
            "rsi": inds.get("rsi", "N/A"),
            "adx": inds.get("adx", "N/A"),
            "safe_dist_pts": dist_safe,
            "actual_dist_pts": dist_actual,
            "stop_level": tick.get("stop_level"),
            "freeze_level": tick.get("freeze_level"),
            "tick_lag": lag,
            "warnings": "; ".join(meta.get("warnings", []))
        }

        # 4. Tulis ke CSV
        try:
            with open(file_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                if not file_exists:
                    writer.writeheader() # Tulis header kalau file baru
                writer.writerow(row)
        except Exception as e:
            print(f"❌ Logger Error: {e}")
