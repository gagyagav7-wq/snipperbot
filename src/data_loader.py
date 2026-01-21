import zmq
import json
import os
import pandas as pd
import subprocess

ZMQ_SOCKET = None
CONTEXT = zmq.Context()

def get_wsl_ip():
    """Auto-detect IP Windows dari WSL2"""
    manual_ip = os.getenv("WINDOWS_HOST")
    if manual_ip: return manual_ip
    try:
        # Baca resolv.conf untuk dapet IP Host Windows
        out = subprocess.check_output("cat /etc/resolv.conf | grep nameserver | awk '{print $2}'", shell=True)
        return out.decode('utf-8').strip()
    except:
        return "127.0.0.1"

def process_df(data_list):
    """Ubah list of dict menjadi DataFrame UTC-Aware (Fix iloc bug)"""
    if not data_list: return pd.DataFrame()
    df = pd.DataFrame(data_list)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    df.sort_index(inplace=True)
    return df

def get_market_data():
    global ZMQ_SOCKET
    host = get_wsl_ip()
    address = f"tcp://{host}:5555"

    if ZMQ_SOCKET is None:
        ZMQ_SOCKET = CONTEXT.socket(zmq.REQ)
        # Saran Pro: Tambah SNDTIMEO & LINGER
        ZMQ_SOCKET.setsockopt(zmq.SNDTIMEO, 2000)
        ZMQ_SOCKET.setsockopt(zmq.RCVTIMEO, 2000)
        ZMQ_SOCKET.setsockopt(zmq.LINGER, 0)
        ZMQ_SOCKET.connect(address)
        print(f"📡 Connected to MT5 Server at {address}")

    try:
        ZMQ_SOCKET.send_json({"action": "GET_ALL_DATA"})
        raw = ZMQ_SOCKET.recv_json()
        
        if raw.get("status") == "OK":
            # Process raw data jadi DataFrame di sini
            raw['m5'] = process_df(raw.get('m5'))
            raw['m15'] = process_df(raw.get('m15'))
            return raw
        return None
    except:
        if ZMQ_SOCKET: ZMQ_SOCKET.close()
        ZMQ_SOCKET = None
        return None
