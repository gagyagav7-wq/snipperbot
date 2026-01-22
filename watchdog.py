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
    """Smart Terminator: Anti-Suicide & Sopan."""
    my_pid = str(os.getpid()) # PID Watchdog sendiri
    try:
        pids = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"]).decode().split()
        if not pids: return

        # Filter PID Watchdog biar gak bunuh diri
        target_pids = [p for p in pids if p != my_pid]
        if not target_pids: return

        # Tahap 1: Sopan (SIGTERM)
        for pid in target_pids: subprocess.run(["kill", "-TERM", pid], check=False)
        time.sleep(3)

        # Tahap 2: Paksa (SIGKILL)
        pids_left = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"]).decode().split()
        target_left = [p for p in pids_left if p != my_pid]
        
        for pid in target_left: subprocess.run(["kill", "-KILL", pid], check=False)
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
        
        # Grace period awal
        time.sleep(20) 
        if is_bot_running(): return True
        return False
    except Exception as e:
        alert(f"🚨 <b>RESTART FAILED:</b> {str(e)}")
        return False

# --- MAIN LOOP ---
print(f"🐕 WATCHDOG GUARDING: {PROJECT_DIR}")
alert("🐕 <b>WATCHDOG STARTED</b>\nSystem: Self-Preservation Mode")

error_count = 0
last_critical_ts = 0
last_recovered_ts = 0
ALERT_COOLDOWN = 300 

while True:
    if not is_bot_running():
        error_count += 1
        print(f"🚨 BOT DOWN! Attempt {error_count}/3")
        
        if error_count <= 3:
            alert(f"⚠️ <b>BOT CRASHED</b> (x{error_count})\nRestarting...")
            
            if restart_bot():
                # FIX: Quick Re-Check buat deteksi Crash-on-Boot
                time.sleep(10)
                if is_bot_running():
                    alert("✅ <b>RESTART SUCCESS</b>\nEngine stable.")
                else:
                    alert("🚨 <b>BOOT FAILED</b>\nBot died immediately after restart.")
                    # Biarkan error_count nambah di loop berikutnya
            else:
                alert("❌ <b>RESTART STALLED</b>")
        else:
            if time.time() - last_critical_ts > 60:
                alert(f"🚨 <b>CRITICAL FAILURE</b>\nAuto-restart failed 3 times.\nMANUAL INTERVENTION NEEDED!")
                last_critical_ts = time.time()
            time.sleep(60)
            
    else:
        if error_count > 0:
            if time.time() - last_recovered_ts > ALERT_COOLDOWN:
                alert("✅ <b>BOT RECOVERED</b>\nRunning normally.")
                last_recovered_ts = time.time()
            error_count = 0 
            
    time.sleep(60)
