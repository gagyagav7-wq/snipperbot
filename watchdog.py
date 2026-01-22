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
    try:
        pids = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"]).decode().split()
        if not pids: return
        # Tahap 1: Sopan
        for pid in pids: subprocess.run(["kill", "-TERM", pid], check=False)
        time.sleep(3)
        # Tahap 2: Paksa
        pids_left = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"]).decode().split()
        for pid in pids_left: subprocess.run(["kill", "-KILL", pid], check=False)
        time.sleep(1)
    except: pass

def restart_bot():
    kill_zombies()
    log_file = os.path.join(LOG_DIR, "restart.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[Watchdog] Restarting bot at {time.ctime()}...\n")
            subprocess.Popen(
                [sys.executable, "run_bot.py"],
                cwd=PROJECT_DIR,
                stdout=f, stderr=f
            )
        
        # FIX: Grace period dinaikkan jadi 20 detik biar bot sempat loading modul
        time.sleep(20) 
        if is_bot_running(): return True
        return False
    except Exception as e:
        alert(f"🚨 <b>RESTART FAILED:</b> {str(e)}")
        return False

# --- MAIN LOOP ---
print(f"🐕 WATCHDOG GUARDING: {PROJECT_DIR}")
alert("🐕 <b>WATCHDOG STARTED</b>\nSystem: Final No-Drama Edition")

error_count = 0
last_critical_ts = 0  # Timer khusus Critical
last_recovered_ts = 0 # Timer khusus Recovered
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
            # FIX: Gunakan timer terpisah buat Critical Spam
            if time.time() - last_critical_ts > 60:
                alert(f"🚨 <b>CRITICAL FAILURE</b>\nAuto-restart failed 3 times.\nManual Check Required!")
                last_critical_ts = time.time()
            time.sleep(60)
            
    else:
        if error_count > 0:
            # FIX: Gunakan timer terpisah buat Recovered
            if time.time() - last_recovered_ts > ALERT_COOLDOWN:
                alert("✅ <b>BOT RECOVERED</b>\nSystem stable.")
                last_recovered_ts = time.time()
            error_count = 0 
            
    time.sleep(60)
