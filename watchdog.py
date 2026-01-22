import time
import os
import subprocess
import requests
import sys

from dotenv import load_dotenv

# --- CONFIG ---
# Gunakan absolute path biar watchdog bisa dijalankan dari mana saja
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True) # Pastikan folder logs ada

# Load .env dari project dir
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
        # Regex lebih spesifik biar gak false positive
        # Mengecek proses python yang menjalankan run_bot.py
        output = subprocess.check_output(["pgrep", "-f", "python.*run_bot.py"])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

def restart_bot():
    """Restart bot dengan lingkungan yang benar (VENV safe)"""
    log_file = os.path.join(LOG_DIR, "restart.log")
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[Watchdog] Restarting bot at {time.ctime()}...\n")
            # Gunakan sys.executable agar menggunakan Python VENV yang sama
            subprocess.Popen(
                [sys.executable, "run_bot.py"],
                cwd=PROJECT_DIR, # Pastikan jalan di folder project
                stdout=f,
                stderr=f
            )
        return True
    except Exception as e:
        alert(f"🚨 <b>RESTART FAILED:</b> {str(e)}")
        return False

# --- MAIN LOOP ---
print(f"🐕 WATCHDOG GUARDING: {PROJECT_DIR}")
alert("🐕 <b>WATCHDOG STARTED</b>\nMonitoring Gold Killer Bot...")

error_count = 0
last_alert_ts = 0
ALERT_COOLDOWN = 300 # 5 Menit cooldown notif "Recovered"

while True:
    if not is_bot_running():
        error_count += 1
        print(f"🚨 BOT DOWN! Attempt {error_count}/3")
        
        if error_count <= 3:
            alert(f"⚠️ <b>BOT CRASHED</b> (x{error_count})\nAttempting auto-restart...")
            if restart_bot():
                time.sleep(10) # Kasih waktu bot buat napas/booting
            else:
                time.sleep(60)
        else:
            # Kalau udah 3x gagal, nyerah & spam admin
            alert(f"🚨 <b>CRITICAL FAILURE</b>\nAuto-restart failed 3 times.\nCheck server manually!")
            time.sleep(600) # Tidur panjang biar admin bangun
            
    else:
        # Bot jalan normal
        if error_count > 0:
            # Cek cooldown biar gak spam notif kalau bot flapping (nyala-mati-nyala)
            if time.time() - last_alert_ts > ALERT_COOLDOWN:
                alert("✅ <b>BOT RECOVERED</b>\nSystem running normally.")
                last_alert_ts = time.time()
            
            error_count = 0 # Reset counter
            
    time.sleep(60) # Cek tiap 1 menit
