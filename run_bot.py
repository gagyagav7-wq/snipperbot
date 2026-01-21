import zmq
import json

# --- KONFIGURASI KONEKSI (HARDCODED BIAR PATEN) ---
# Ganti ini dengan IP Windows lu yang tadi
WINDOWS_HOST = "192.168.101.13" 
PORT = 5555
ADDRESS = f"tcp://{WINDOWS_HOST}:{PORT}"

# Setup ZMQ Context (Sekali di awal biar efisien)
context = zmq.Context()
socket = context.socket(zmq.REQ)

# Set Timeout (PENTING: Biar gak nge-hang selamanya kalau server mati)
socket.setsockopt(zmq.RCVTIMEO, 2000) # 2 detik timeout
socket.setsockopt(zmq.LINGER, 0)

print(f"📡 Connecting to MT5 Server at {ADDRESS}...")
socket.connect(ADDRESS)

def get_market_data():
    """
    Mengambil data dari Server MT5 via ZMQ.
    """
    try:
        # 1. Kirim Request
        socket.send_json({"action": "GET_ALL_DATA"})
        
        # 2. Terima Reply
        response = socket.recv_json()
        
        if response.get("status") == "OK":
            return response
        else:
            # Kalau status ERROR dari server
            print(f"⚠️ Server Error: {response.get('error')}")
            return None

    except zmq.Again:
        # Timeout (Server gak bales / Mati / Firewall Blokir)
        # Kita reconnect biar socket gak stuck
        global socket
        print("⚠️ Connection Timeout (Server Down/Firewall Block?) Reconnecting...")
        socket.close()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.RCVTIMEO, 2000)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(ADDRESS)
        return None
        
    except Exception as e:
        print(f"❌ ZMQ Error: {e}")
        return None
