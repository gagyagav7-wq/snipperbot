import os
from dotenv import load_dotenv

# Load variable dari .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SYMBOL = os.getenv("SYMBOL", "GC=F")
