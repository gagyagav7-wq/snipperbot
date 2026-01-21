import pandas as pd
import os
from src.zmq_client import ZMQClient

# Cari IP Windows otomatis
def get_windows_ip():
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line: return line.split()[1]
    except: pass
    return "localhost"

# Inisialisasi Client SEKALI aja (Global)
CLIENT = ZMQClient(get_windows_ip())

def get_market_data():
    response = CLIENT.request("GET_ALL_DATA")
    
    if not response or "error" in response:
        return None

    try:
        # Parsing M5 & M15
        df_5m = pd.DataFrame(response['m5']).set_index('time')
        df_15m = pd.DataFrame(response['m15']).set_index('time')
        
        # Convert Epoch ke Datetime UTC (Nanti di indicator convert ke WIB)
        df_5m.index = pd.to_datetime(df_5m.index, unit='s')
        df_15m.index = pd.to_datetime(df_15m.index, unit='s')

        # Parsing History (PDH/PDL dari Broker!)
        df_d1 = pd.DataFrame(response['history']['d1'])
        last_day = df_d1.iloc[0] # Karena server kirim urut, index 0 itu kemarin (closed)
        
        history_ctx = {
            "pdh": last_day['high'],
            "pdl": last_day['low'],
            "pdc": last_day['close']
        }

        return {
            "m5": df_5m,
            "m15": df_15m,
            "tick": response['tick'],
            "history": history_ctx
        }
    except Exception as e:
        print(f"❌ Parse Error: {e}")
        return None
