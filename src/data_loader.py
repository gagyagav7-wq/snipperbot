import zmq
import json
import time

# --- KONFIGURASI KONEKSI ---
WINDOWS_HOST = "192.168.101.13" 
PORT = 5555
ADDRESS = f"tcp://{WINDOWS_HOST}:{PORT}"

# Setup ZMQ Context
context = zmq.Context()
socket = context.socket(zmq.REQ)

# Set Timeout
socket.setsockopt(zmq.RCVTIMEO, 2000)
socket.setsockopt(zmq.LINGER, 0)

print(f"📡 Connecting to MT5 Server at {ADDRESS}...")
socket.connect(ADDRESS)

def get_market_data():
    """
    Mengambil data dari Server MT5 via ZMQ.
    """
    # [FIX] Posisi global socket WAJIB di baris pertama fungsi
    global socket 

    try:
        # 1. Kirim Request
        socket.send_json({"action": "GET_ALL_DATA"})
        
        # 2. Terima Reply
        response = socket.recv_json()
        
        if response.get("status") == "OK":
            return response
        else:
            print(f"⚠️ Server Error: {response.get('error')}")
            return None

    except zmq.Again:
        print("⚠️ Connection Timeout - Reconnecting...")
        try:
            socket.close()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 2000)
            socket.setsockopt(zmq.LINGER, 0)
            socket.connect(ADDRESS)
        except Exception as e:
            print(f"❌ Reconnect Failed: {e}")
        return None
        
    except Exception as e:
        print(f"❌ ZMQ Error: {e}")
        return None
