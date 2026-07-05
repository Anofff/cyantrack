import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "20"))
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID", "")
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "54000"))
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "CyanTrack Operations")

_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = (
    {int(uid.strip()) for uid in _raw.split(",") if uid.strip()}
    if _raw.strip()
    else set()
)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing from your .env file")
