import zmq
import pandas as pd
import json

# Konfigurasi ZMQ
CONTEXT = zmq.Context()
SOCKET = CONTEXT.socket(zmq.REQ)
SOCKET.connect("tcp://localhost:5555")

def get_market_data():
    """
    Mengambil data market (Candle + Tick + Meta) dari Server MT5.
    Output: Dictionary data_pack atau None jika gagal.
    """
    try:
        # 1. Request Data
        SOCKET.send_string("DATA")
        
        # 2. Receive Response (Block mode, timeout via Poller kalau mau canggih)
        # Di sini kita pakai simple recv_json
        resp = SOCKET.recv_json()
        
        if resp.get("status") != "OK":
            print(f"⚠️ Server Error: {resp.get('error')}")
            return None

        # 3. Konversi JSON ke DataFrame Pandas
        # M5 Data
        m5_data = resp.get("m5", [])
        df_5m = pd.DataFrame(m5_data)
        if not df_5m.empty:
            df_5m['time'] = pd.to_datetime(df_5m['time'], unit='s')
            df_5m.set_index('time', inplace=True)
        
        # M15 Data
        m15_data = resp.get("m15", [])
        df_15m = pd.DataFrame(m15_data)
        if not df_15m.empty:
            df_15m['time'] = pd.to_datetime(df_15m['time'], unit='s')
            df_15m.set_index('time', inplace=True)

        # 4. Return Data Pack Lengkap (TERMASUK META)
        # [FIX] Pastikan key 'meta' disertakan agar Logger bisa hitung Lag
        return {
            "tick": resp.get("tick", {}),
            "m5": df_5m,
            "m15": df_15m,
            "history": resp.get("history", {}),
            "meta": resp.get("meta", {})  # <--- INI KUNCI PENTINGNYA
        }

    except zmq.ZMQError as e:
        print(f"❌ ZMQ Error: {e}")
        # Reconnect logic simple
        global SOCKET
        SOCKET.close()
        SOCKET = CONTEXT.socket(zmq.REQ)
        SOCKET.connect("tcp://localhost:5555")
        return None
    except Exception as e:
        print(f"❌ Data Loader Error: {e}")
        return None
