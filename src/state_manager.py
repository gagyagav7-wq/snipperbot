import json
import os

STATE_FILE = "bot_state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_processed_time": None}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_processed_time": None}

def save_state(timestamp):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_processed_time": str(timestamp)}, f)
