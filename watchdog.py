import time
import os
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def alert(msg):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except: pass

def is_bot_running():
    try:
        # Cek apakah ada proses python yang menjalankan run_bot.py
        output = subprocess.check_output(["pgrep", "-f", "run_bot.py"])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

print("🐕 WATCHDOG ACTIVATED: Guarding Gold Killer Bot...")
alert("🐕 Watchdog Started: I will notify you if the bot crashes.")

while True:
    if not is_bot_running():
        print("🚨 ALERT: BOT IS DOWN!")
        alert("🚨 <b>CRITICAL ALERT</b>\n\nGold Killer Bot is DOWN/CRASHED!\nPlease check your server immediately.")
        
        # Opsional: Coba restart otomatis (Uncomment kalau berani)
        # os.system("nohup python run_bot.py &")
        
        # Sleep lama biar gak spam notif kalau lu lagi benerin
        time.sleep(600) 
    else:
        # print("✅ Bot is running...")
        pass
    
    time.sleep(60) # Cek tiap 1 menit
