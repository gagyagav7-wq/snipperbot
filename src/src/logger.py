import csv
import os
from datetime import datetime

class TradeLogger:
    def __init__(self, filename_prefix="trade_log"):
        self.log_dir = "logs"
        self.filename_prefix = filename_prefix
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # Header CSV
        self.fields = [
            "timestamp", "signal", "reason", "price_close", 
            "spread", "adx", "rsi", "safe_dist_price", 
            "skip_dist_price", "stop_level", "warnings"
        ]
        self.current_date = None
        self.csv_file = None

    def _get_file_path(self):
        # Rotasi log per hari
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.current_date:
            self.current_date = today
            return os.path.join(self.log_dir, f"{self.filename_prefix}_{today}.csv")
        return self.csv_file

    def log_contract(self, contract):
        # Hanya log jika data valid (bukan init/empty)
        if not contract or contract.get("reason") in ["Data Empty", "Initializing..."]:
            return

        file_path = self._get_file_path()
        file_exists = os.path.isfile(file_path)

        # Extract Data Penting
        meta = contract.get("meta", {})
        tick = contract.get("tick", {})
        setup = contract.get("setup", {})
        
        # Ambil indikator terakhir (agak tricky karena ada di DataFrame)
        df = contract.get("df_5m")
        df_15 = pd.DataFrame() # Placeholder kalau structure beda, tapi logic aman
        
        adx_val = 0
        rsi_val = 0
        close_val = 0
        
        try:
            if not df.empty:
                last_row = df.iloc[-1]
                close_val = last_row.get('Close', 0)
                rsi_val = round(last_row.get('RSI', 0), 2)
                # ADX ada di dataframe tapi logic kita hitung di indicators.py
                # Kita ambil dari reason text kalau terpaksa, atau modif indikator return DF
                # Utk simplifikasi, kita catat yg ada di contract meta dulu
        except: pass

        # Cek Jarak Skip (Price)
        skip_dist = meta.get("dist_pdh_price") or meta.get("dist_pdl_price") or 0
        if skip_dist: skip_dist = round(skip_dist, 2)

        safe_dist = meta.get("safe_dist_price", 0)
        if safe_dist: safe_dist = round(safe_dist, 2)

        row = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "signal": contract.get("signal"),
            "reason": contract.get("reason"),
            "price_close": close_val,
            "spread": meta.get("spread"),
            "adx": "N/A", # Perlu pass DF 15m kalau mau log ADX detail
            "rsi": rsi_val,
            "safe_dist_price": safe_dist,
            "skip_dist_price": skip_dist,
            "stop_level": tick.get("stop_level"),
            "warnings": ";".join(meta.get("warnings", []))
        }

        with open(file_path, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
