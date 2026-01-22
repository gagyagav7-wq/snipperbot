import time
import os
import subprocess
import requests
import sys
from dotenv import load_dotenv

# Load Env dari folder project (sesuaikan path kalau perlu)
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def alert(msg):
    """Kirim notif Telegram dengan mode HTML dan Timeout aman"""
    if not TELEGRAM_TOKEN or not CHAT_ID: 
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    
    try:
        # Timeout penting biar watchdog gak macet kalau internet lemot
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Watchdog gagal kirim alert: {e}")

def is_bot_running():
    try:
        # Cek apakah proses 'run_bot.py' ada di daftar proses
        # '-f' match full command line
        output = subprocess.check_output(["pgrep", "-f", "run_bot.py"])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

# --- LOGIKA UTAMA ---
print("🐕 WATCHDOG ACTIVATED: Guarding Gold Killer Bot...")
print("   Tekan Ctrl+C untuk mematikan Watchdog.")
alert("🐕 <b>WATCHDOG STARTED</b>\nSaya akan memantau bot Anda 24/7.")

error_count = 0

while True:
    if not is_bot_running():
        error_count += 1
        print(f"🚨 ALERT: BOT IS DOWN! (Count: {error_count})")
        
        # Kirim notif, tapi jangan spam brutal (maksimal notif tiap loop)
        alert(f"🚨 <b>CRITICAL ALERT</b>\n\nGold Killer Bot is <b>DOWN/CRASHED!</b>\nCheck server immediately.\n<i>Fail count: {error_count}</i>")
        
        # Opsional: Auto-Restart setelah 3x gagal berturut-turut
        if error_count == 3:
             alert("🔄 <b>Attempting Auto-Restart...</b>")
             os.system("nohup python run_bot.py > logs/restart.log 2>&1 &")
        
        # Tunggu 5 menit sebelum cek lagi biar lu punya waktu benerin
        time.sleep(300) 
    else:
        # Reset counter kalau bot jalan normal
        if error_count > 0:
            alert("✅ <b>BOT RECOVERED</b>\nBot terdeteksi berjalan kembali.")
            error_count = 0
        
        # Cek setiap 60 detik
        time.sleep(60)
