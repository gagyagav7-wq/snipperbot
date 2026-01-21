import zmq
import pandas as pd
import json

# Konfigurasi Koneksi ke Windows
CONTEXT = zmq.Context()
SOCKET = CONTEXT.socket(zmq.REQ)
SOCKET.connect("tcp://localhost:5555") # Ganti IP Windows kalo beda PC

def get_realtime_data(symbol="XAUUSD"):
    try:
        # Request Data Paket Lengkap (M1, M5, M15, Spread)
        request = {
            "action": "GET_ANALYSIS_DATA",
            "symbol": symbol
        }
        SOCKET.send_json(request)
        
        # Terima Balasan
        response = SOCKET.recv_json()
        
        if "error" in response:
            print(f"❌ MT5 Error: {response['error']}")
            return None
            
        # Parsing Data jadi DataFrame
        df_1m = pd.DataFrame(response['m1']).set_index('time')
        df_5m = pd.DataFrame(response['m5']).set_index('time')
        df_15m = pd.DataFrame(response['m15']).set_index('time')
        
        # Convert index ke datetime
        for df in [df_1m, df_5m, df_15m]:
            df.index = pd.to_datetime(df.index, unit='s')
            
        return {
            "1m": df_1m,
            "5m": df_5m,
            "15m": df_15m,
            "spread": response['spread'],     # PENTING: Spread Realtime
            "tick_value": response['tick_val'] # Nilai per pip
        }

    except Exception as e:
        print(f"❌ ZMQ Error: {e}")
        # Reset Socket kalau hang
        return None
