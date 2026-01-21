import zmq
import json

class ZMQClient:
    def __init__(self, host_ip, port=5555):
        self.address = f"tcp://{host_ip}:{port}"
        self.context = zmq.Context()
        self.socket = None
        self.connect()

    def connect(self):
        # Bikin socket baru
        if self.socket:
            self.socket.close()
        
        self.socket = self.context.socket(zmq.REQ)
        # Timeout 2000ms (2 detik). Biar gak nge-hang.
        self.socket.setsockopt(zmq.RCVTIMEO, 2000)
        self.socket.setsockopt(zmq.SNDTIMEO, 2000)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect(self.address)

    def request(self, action, payload=None):
        req = {"action": action}
        if payload: req.update(payload)

        try:
            self.socket.send_json(req)
            return self.socket.recv_json()
        except zmq.error.Again:
            print("⚠️ Timeout! Reconnecting...")
            self.connect() # Reconnect otomatis
            return None
        except Exception as e:
            print(f"❌ Socket Error: {e}")
            self.connect()
            return None
