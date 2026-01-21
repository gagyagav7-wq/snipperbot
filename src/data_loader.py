import zmq
import json
import os

# Pakai Huruf Besar (Global Constant)
ZMQ_SOCKET = None
CONTEXT = zmq.Context()

def get_market_data():
    global ZMQ_SOCKET
    
    # Ambil IP dari .env atau hardcode
    host = os.getenv("WINDOWS_HOST", "192.168.101.13")
    address = f"tcp://{host}:5555"

    # Inisialisasi awal jika belum ada
    if ZMQ_SOCKET is None:
        ZMQ_SOCKET = CONTEXT.socket(zmq.REQ)
        ZMQ_SOCKET.setsockopt(zmq.RCVTIMEO, 2000)
        ZMQ_SOCKET.setsockopt(zmq.LINGER, 0)
        ZMQ_SOCKET.connect(address)
        print(f"📡 Connected to MT5 Server at {address}")

    try:
        ZMQ_SOCKET.send_json({"action": "GET_ALL_DATA"})
        return ZMQ_SOCKET.recv_json()
    except zmq.Again:
        print("⚠️ Timeout - Reconnecting...")
        ZMQ_SOCKET.close()
        ZMQ_SOCKET = None # Trigger re-init di loop depan
        return None
    except Exception as e:
        print(f"❌ ZMQ Error: {e}")
        ZMQ_SOCKET = None
        return None
