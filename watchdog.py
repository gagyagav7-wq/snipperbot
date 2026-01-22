import time
import os
import subprocess
import requests
import sys
from dotenv import load_dotenv

# --- CONFIG ---
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

load_dotenv(os.path.join(PROJECT_DIR, ".env"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def alert(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass

def is_bot_running():
    try:
        output = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

def kill_zombies():
    """Smart Terminator: Sopan dulu, baru kasar."""
    try:
        # Coba ambil PID
        pids = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"]).decode().split()
        
        if not pids: return

        # Tahap 1: SIGTERM (Kasih kesempatan cleanup)
        for pid in pids:
            subprocess.run(["kill", "-TERM", pid], check=False)
        time.sleep(3) # Tunggu 3 detik

        # Tahap 2: Cek sisa & SIGKILL (Paksa mati)
        pids_left = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"]).decode().split()
        if pids_left:
            for pid in pids_left:
                subprocess.run(["kill", "-KILL", pid], check=False)
            time.sleep(1)
            
    except subprocess.CalledProcessError:
        pass # Aman, berarti sudah tidak ada proses
    except Exception as e:
        print(f"⚠️ Kill Error: {e}")

def restart_bot():
    kill_zombies() # Bersihkan dulu
    
    log_file = os.path.join(LOG_DIR, "restart.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[Watchdog] Restarting bot at {time.ctime()}...\n")
            subprocess.Popen(
                [sys.executable, "run_bot.py"],
                cwd=PROJECT_DIR,
                stdout=f,
                stderr=f
            )
        
        time.sleep(10) # Verify window
        if is_bot_running(): return True
        return False
            
    except Exception as e:
        alert(f"🚨 <b>RESTART FAILED:</b> {str(e)}")
        return False

# --- MAIN LOOP ---
print(f"🐕 WATCHDOG GUARDING: {PROJECT_DIR}")
alert("🐕 <b>WATCHDOG STARTED</b>\nSystem: Smart Terminator Mode")

error_count = 0
last_alert_ts = 0
ALERT_COOLDOWN = 300 

while True:
    if not is_bot_running():
        error_count += 1
        print(f"🚨 BOT DOWN! Attempt {error_count}/3")
        
        if error_count <= 3:
            alert(f"⚠️ <b>BOT CRASHED</b> (x{error_count})\nRestarting...")
            if restart_bot():
                alert("✅ <b>RESTART SUCCESS</b>")
            else:
                alert("❌ <b>RESTART STALLED</b>")
        else:
            if time.time() - last_alert_ts > 60:
                alert(f"🚨 <b>CRITICAL FAILURE</b>\nManual check required!")
                last_alert_ts = time.time()
            time.sleep(60)
            
    else:
        if error_count > 0:
            if time.time() - last_alert_ts > ALERT_COOLDOWN:
                alert("✅ <b>BOT RECOVERED</b>")
                last_alert_ts = time.time()
            error_count = 0 
            
    time.sleep(60)
