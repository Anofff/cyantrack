import base64
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
GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH",
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./credentials.json"),
)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
DISPLAY_TZ = os.getenv("DISPLAY_TZ", "Africa/Accra")


def _normalize_credentials_json(raw: str) -> str:
    """Accept JSON pasted as raw object or wrapped in outer quotes."""
    text = raw.strip()
    if not text:
        return ""

    if text[0] in "\"'":
        try:
            unwrapped = json.loads(text)
            if isinstance(unwrapped, str):
                text = unwrapped
            elif isinstance(unwrapped, dict):
                return json.dumps(unwrapped)
        except json.JSONDecodeError:
            pass

    return text


def _load_credentials_json() -> str:
    """Resolve Google service account JSON from env (Railway-friendly)."""
    raw = _normalize_credentials_json(os.getenv("GOOGLE_CREDENTIALS_JSON", ""))
    if raw:
        return raw

    b64 = os.getenv("GOOGLE_CREDENTIALS_JSON_B64", "").strip()
    if b64:
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception as e:
            raise ValueError(f"GOOGLE_CREDENTIALS_JSON_B64 is not valid base64: {e}") from e

    return ""


GOOGLE_CREDENTIALS_JSON = _load_credentials_json()


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
            info = json.loads(GOOGLE_CREDENTIALS_JSON)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"GOOGLE_CREDENTIALS_JSON is not valid JSON: {e}\n"
                "Tip: paste the raw file contents starting with { and ending with }"
            ) from e
        if info.get("type") != "service_account":
            raise ValueError("GOOGLE_CREDENTIALS_JSON must be a Google service account JSON file")
        log.info("Google credentials loaded from env (%d chars)", len(GOOGLE_CREDENTIALS_JSON))
        return

    if os.path.isfile(GOOGLE_CREDENTIALS_PATH):
        return

    raise ValueError(
        "Google credentials missing.\n"
        "  Railway: add GOOGLE_CREDENTIALS_JSON (paste full credentials.json)\n"
        "           or GOOGLE_CREDENTIALS_JSON_B64 (run: base64 -w0 credentials.json)\n"
        "  Local:   keep credentials.json and set GOOGLE_CREDENTIALS_PATH=./credentials.json\n"
        "Note: GOOGLE_CREDENTIALS_PATH alone does not work on Railway — the file is not deployed."
    )
