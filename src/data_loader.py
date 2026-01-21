import zmq
import pandas as pd
import json
import time
import os

# --- KONFIGURASI NETWORK ---
# Auto-detect IP Windows jika jalan di WSL2
def get_windows_host_ip():
    if "WSL_DISTRO_NAME" in os.environ:
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if "nameserver" in line:
                        # IP nameserver di WSL2 biasanya adalah IP Host Windows
                        ip = line.split()[1]
                        print(f"🖥️  Detected WSL2. Connecting to Windows Host: {ip}")
                        return ip
        except:
            pass
    return "localhost"

# Setup Address
HOST_IP = get_windows_host_ip()
SERVER_ADDR = f"tcp://{HOST_IP}:5555"
TIMEOUT_MS  = 2000 

CONTEXT = zmq.Context()
SOCKET = None

def _init_socket():
    """Helper untuk inisialisasi/reset socket dengan aman"""
    global SOCKET
    if SOCKET:
        SOCKET.close()
    
    SOCKET = CONTEXT.socket(zmq.REQ)
    # Set Timeout & Linger (Anti-Hang)
    SOCKET.setsockopt(zmq.RCVTIMEO, TIMEOUT_MS)
    SOCKET.setsockopt(zmq.SNDTIMEO, TIMEOUT_MS)
    SOCKET.setsockopt(zmq.LINGER, 0)
    
    try:
        SOCKET.connect(SERVER_ADDR)
        print(f"🔌 ZMQ Connected to {SERVER_ADDR}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

# Init pertama kali
_init_socket()

def get_market_data():
    """
    Mengambil data market. Thread-unsafe (panggil dari main thread only).
    """
    global SOCKET
    
    try:
        # 1. Request Data (Protocol Match dengan Server)
        SOCKET.send_json({"action": "GET_ALL_DATA"})
        
        # 2. Receive Response
        resp = SOCKET.recv_json()
        
        if resp.get("status") != "OK":
            # Silent error kalau cuma belum siap, print kalau error beneran
            err = resp.get("error", "")
            if "Not Ready" not in err:
                print(f"⚠️ Server Error: {err}")
            return None

        # 3. Helper Processing (UTC Aware)
        def process_df(data_list):
            if not data_list: return pd.DataFrame()
            df = pd.DataFrame(data_list)
            # Wajib utc=True biar konsisten sama indicators.py
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)
            return df

        df_5m = process_df(resp.get("m5", []))
        df_15m = process_df(resp.get("m15", []))

        # [FIX] Validation Strict: Kalau data kosong, jangan diproses
        if df_5m.empty or df_15m.empty:
            return None

        # 4. Return Data Pack
        return {
            "tick": resp.get("tick", {}),
            "m5": df_5m,
            "m15": df_15m,
            "history": resp.get("history", {}),
            "meta": resp.get("meta", {}) # Penting buat Logger
        }

    except (zmq.Again, zmq.ZMQError):
        # [FIX] Anti-Spam Reconnect
        # Kalau timeout, jangan langsung hajar. Napas dulu 1 detik.
        time.sleep(1.0)
        _init_socket() 
        return None
        
    except Exception as e:
        print(f"❌ Data Loader Error: {e}")
        time.sleep(1.0)
        return None
