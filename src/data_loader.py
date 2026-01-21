import pandas as pd
import os
from src.zmq_client import ZMQClient

def get_windows_ip():
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line: return line.split()[1]
    except: pass
    return "localhost"

CLIENT = ZMQClient(get_windows_ip())

def get_market_data():
    response = CLIENT.request("GET_ALL_DATA")
    
    if not response or "error" in response:
        # Bisa return None kalau market tutup atau server down
        return None

    try:
        def parse_tf(data_list):
            if not data_list: return pd.DataFrame()
            df = pd.DataFrame(data_list)
            # Patch 4: Konversi Epoch ke DateTime UTC Aware DI SINI
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True) # Double safety sorting
            return df

        df_5m = parse_tf(response['m5'])
        df_15m = parse_tf(response['m15'])
        
        return {
            "m5": df_5m,
            "m15": df_15m,
            "tick": response['tick'],
            "history": response['history']
        }
    except Exception as e:
        print(f"❌ Loader Error: {e}")
        return None
