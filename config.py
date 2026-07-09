import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "20"))
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "54000"))
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "CyanTrack Operations")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
DISPLAY_TZ = os.getenv("DISPLAY_TZ", "Africa/Accra")


def _parse_alert_chat_id(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw.lstrip("-").isdigit():
        return raw
    log.warning("ALERT_CHAT_ID=%r is not a valid numeric chat ID — alerts disabled", raw)
    return ""


def _parse_allowed_users(raw: str) -> set[int]:
    users: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if part.lstrip("-").isdigit():
            users.add(int(part))
        else:
            log.warning("ALLOWED_USERS: ignoring invalid entry %r", part)
    return users


ALERT_CHAT_ID = _parse_alert_chat_id(os.getenv("ALERT_CHAT_ID", ""))

_initial = os.getenv("INITIAL_STOCK", "")
INITIAL_STOCK: int | None = int(_initial) if _initial.strip().isdigit() else None

_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = _parse_allowed_users(_raw) if _raw.strip() else set()


def validate_config() -> None:
    """Fail fast on missing production configuration."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing — set it in .env or Railway variables")

    if not SPREADSHEET_ID:
        log.warning("SPREADSHEET_ID not set — using in-memory store (not for production)")
        return

    if GOOGLE_CREDENTIALS_JSON.strip():
        try:
            json.loads(GOOGLE_CREDENTIALS_JSON)
        except json.JSONDecodeError as e:
            raise ValueError(f"GOOGLE_CREDENTIALS_JSON is not valid JSON: {e}") from e
        return

    if not os.path.isfile(GOOGLE_CREDENTIALS_PATH):
        raise ValueError(
            "SPREADSHEET_ID is set but no Google credentials found. "
            "Set GOOGLE_CREDENTIALS_JSON (Railway) or GOOGLE_CREDENTIALS_PATH (local file)."
        )
