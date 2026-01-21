import zmq
import pandas as pd
import json
import time
import os

# ==========================================
# ⚙️ KONFIGURASI NETWORK
# ==========================================

# [OPSIONAL] Isi IP Windows manual di sini jika Auto-Detect gagal (misal: "192.168.1.5")
# Biarkan None jika ingin menggunakan Auto-Detect.
MANUAL_HOST_IP = None 

def get_windows_host_ip():
    """
    Auto-detect IP Windows Host dari dalam WSL2 via resolv.conf.
    Fallback ke 'localhost' jika bukan WSL atau jika MANUAL_HOST_IP diisi.
    """
    # 1. Cek Manual Override dulu
    if MANUAL_HOST_IP:
        print(f"⚙️ Using Manual Host IP: {MANUAL_HOST_IP}")
        return MANUAL_HOST_IP

    # 2. Cek WSL Auto-Detect
    if "WSL_DISTRO_NAME" in os.environ:
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if "nameserver" in line:
                        # IP nameserver di WSL2 biasanya adalah IP Host Windows
                        ip = line.split()[1]
                        print(f"🖥️  Detected WSL2. Connecting to Windows Host: {ip}")
                        return ip
        except Exception as e:
            print(f"⚠️ WSL IP Detect Failed: {e}. Using localhost.")
    
    return "localhost"

# Setup Address
HOST_IP = get_windows_host_ip()
SERVER_ADDR = f"tcp://{HOST_IP}:5555"
TIMEOUT_MS  = 2000  # 2 Detik Timeout (Cukup buat local network)

CONTEXT = zmq.Context()
SOCKET = None

def _init_socket():
    """Helper untuk inisialisasi/reset socket dengan aman"""
    global SOCKET
    
    # [FIX] Clean Cleanup: Close dan set None biar gak jadi 'zombie'
    if SOCKET:
        try:
            SOCKET.close()
        except:
            pass
        SOCKET = None
    
    # Re-create Socket
    SOCKET = CONTEXT.socket(zmq.REQ)
    
    # Set Socket Options (Anti-Hang & Anti-Linger)
    SOCKET.setsockopt(zmq.RCVTIMEO, TIMEOUT_MS)
    SOCKET.setsockopt(zmq.SNDTIMEO, TIMEOUT_MS)
    SOCKET.setsockopt(zmq.LINGER, 0) # Langsung putus kalau close
    
    try:
        SOCKET.connect(SERVER_ADDR)
        print(f"🔌 ZMQ Connected to {SERVER_ADDR}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

# Init pertama kali
_init_socket()

def get_market_data():
    """
    Mengambil data market (Thread-Unsafe: Panggil dari Main Thread).
    """
    global SOCKET
    
    try:
        # 1. Request Data (Protocol Match: JSON Action)
        SOCKET.send_json({"action": "GET_ALL_DATA"})
        
        # 2. Receive Response
        resp = SOCKET.recv_json()
        
        # Validasi Basic Response
        if resp.get("status") != "OK":
            err = resp.get("error", "")
            # Kalau errornya cuma "Not Ready" (lagi warming up), jangan spam log
            if "Not Ready" not in err:
                print(f"⚠️ Server Error: {err}")
            return None

        # 3. Helper Processing (UTC Aware wajib!)
        def process_df(data_list):
            if not data_list: return pd.DataFrame()
            df = pd.DataFrame(data_list)
            # Convert timestamp ke UTC datetime object
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)
            return df

        df_5m = process_df(resp.get("m5", []))
        df_15m = process_df(resp.get("m15", []))

        # [FIX] Strict Gatekeeper: Tolak kalau DataFrame kosong
        if df_5m.empty or df_15m.empty:
            return None

        # 4. Return Data Pack Lengkap (Bawa META untuk Logger)
        return {
            "tick": resp.get("tick", {}),
            "m5": df_5m,
            "m15": df_15m,
            "history": resp.get("history", {}),
            "meta": resp.get("meta", {}) 
        }

    except (zmq.Again, zmq.ZMQError):
        # Backoff Reconnect: Napas dulu 1 detik sebelum reconnect
        time.sleep(1.0)
        _init_socket() 
        return None
        
    except Exception as e:
        # [FIX CRITICAL] Reset socket juga kalau error aneh (JSON parse error, dll)
        # Biar state ZMQ REQ/REP gak macet (deadlock)
        print(f"❌ Data Loader Error: {e}")
        time.sleep(1.0)
        _init_socket()
        return None
