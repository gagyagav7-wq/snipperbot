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
        # Cek spesifik ke file run_bot.py biar gak salah kill process lain
        output = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

def kill_zombies():
    """Membunuh sisa-sisa bot yang nge-hang sebelum restart"""
    try:
        # Pkill force (-9) ke semua yang mengandung run_bot.py
        subprocess.run(["pkill", "-9", "-f", "python.*run_bot.py"], check=False)
        time.sleep(2) # Kasih waktu buat OS bersih-bersih
    except: pass

def restart_bot():
    """Restart dengan Kill Switch & VENV Safe"""
    kill_zombies() # WAJIB KILL DULU
    
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
        
        # --- VERIFY WINDOW (Cek apakah beneran nyala?) ---
        time.sleep(10)
        if is_bot_running():
            return True
        else:
            return False
            
    except Exception as e:
        alert(f"🚨 <b>RESTART FAILED:</b> {str(e)}")
        return False

# --- MAIN LOOP ---
print(f"🐕 WATCHDOG GUARDING: {PROJECT_DIR}")
alert("🐕 <b>WATCHDOG STARTED</b>\nSystem: Terminator Mode (Anti-Ghost)")

error_count = 0
last_alert_ts = 0
ALERT_COOLDOWN = 300 

while True:
    if not is_bot_running():
        error_count += 1
        print(f"🚨 BOT DOWN! Attempt {error_count}/3")
        
        if error_count <= 3:
            alert(f"⚠️ <b>BOT CRASHED</b> (x{error_count})\nKilling zombies & restarting...")
            
            if restart_bot():
                alert("✅ <b>RESTART SUCCESS</b>\nBot is back online.")
                # Jangan reset error_count langsung, tunggu stable dulu di loop berikutnya
            else:
                alert("❌ <b>RESTART STALLED</b>\nBot failed to launch.")
        else:
            # Spam admin kalau udah 3x gagal total
            if time.time() - last_alert_ts > 60: # Spam tiap menit
                alert(f"🚨 <b>CRITICAL FAILURE</b>\nAuto-restart failed 3 times.\nServer requires MANUAL intervention!")
                last_alert_ts = time.time()
            
            time.sleep(60) # Tidur sebentar
            
    else:
        # Bot jalan normal
        if error_count > 0:
            error_count = 0 # Reset counter kalau stabil
            
    time.sleep(60)
