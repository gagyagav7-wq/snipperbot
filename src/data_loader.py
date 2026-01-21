import zmq
import pandas as pd
import json
import time

# --- KONFIGURASI ZMQ ---
SERVER_ADDR = "tcp://localhost:5555"
TIMEOUT_MS  = 2000  # 2 Detik Timeout (Biar gak nge-freeze selamanya)

CONTEXT = zmq.Context()
SOCKET = None

def _init_socket():
    """Helper untuk inisialisasi/reset socket dengan aman"""
    global SOCKET
    if SOCKET:
        SOCKET.close()
    
    SOCKET = CONTEXT.socket(zmq.REQ)
    # Set Timeout biar bot gak macet kalau MT5 hang
    SOCKET.setsockopt(zmq.RCVTIMEO, TIMEOUT_MS)
    SOCKET.setsockopt(zmq.SNDTIMEO, TIMEOUT_MS)
    SOCKET.setsockopt(zmq.LINGER, 0) # Langsung kill kalau close
    SOCKET.connect(SERVER_ADDR)
    print(f"🔌 ZMQ Connected to {SERVER_ADDR}")

# Init pertama kali saat script load
_init_socket()

def get_market_data():
    """
    Mengambil data market (Candle + Tick + Meta) dari Server MT5.
    Output: Dictionary data_pack atau None jika gagal.
    """
    global SOCKET
    
    try:
        # 1. Request Data dengan JSON Protocol yang BENAR
        # Server mengharapkan action: GET_ALL_DATA
        request_payload = {"action": "GET_ALL_DATA"}
        SOCKET.send_json(request_payload)
        
        # 2. Receive Response
        resp = SOCKET.recv_json()
        
        if resp.get("status") != "OK":
            print(f"⚠️ Server Error: {resp.get('error')}")
            return None

        # 3. Konversi JSON ke DataFrame Pandas (UTC AWARE)
        def process_df(data_list):
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list)
            # [FIX] Wajib utc=True biar bisa di-convert ke WIB nanti
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True) # Pastikan urutan bener
            return df

        df_5m = process_df(resp.get("m5", []))
        df_15m = process_df(resp.get("m15", []))

        # 4. Return Data Pack Lengkap
        # Pastikan META terbawa untuk Logger
        return {
            "tick": resp.get("tick", {}),
            "m5": df_5m,
            "m15": df_15m,
            "history": resp.get("history", {}),
            "meta": resp.get("meta", {}) 
        }

    except (zmq.Again, zmq.ZMQError) as e:
        print(f"❌ ZMQ Timeout/Error: {e}. Reconnecting...")
        # [FIX] Reconnect Logic yang Benar
        _init_socket() 
        return None
        
    except Exception as e:
        print(f"❌ Data Loader General Error: {e}")
        return None
