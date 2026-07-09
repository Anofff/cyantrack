# CyanTrack

Telegram bot for cyanide delivery tracking, treatment cycles, and hypochlorite inventory. Data is stored in Google Sheets.

## Setup (local)

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | From [@BotFather](https://t.me/BotFather) |
| `SPREADSHEET_ID` | Yes (prod) | Sheet ID from the Google Sheets URL |
| `GOOGLE_CREDENTIALS_PATH` | Local | Path to service account JSON (default `./credentials.json`) |
| `GOOGLE_CREDENTIALS_JSON` | Railway | Full service account JSON (overrides path when set) |
| `ALLOWED_USERS` | Recommended | Comma-separated Telegram user IDs for write access |
| `ALERT_CHAT_ID` | No | Numeric group chat ID for arrival/low-stock alerts |
| `DISPLAY_TZ` | No | Timezone for display (default `Africa/Accra`) |
| `INITIAL_STOCK` | No | Auto-seed buckets on startup if stock is empty |
| `LOW_STOCK_THRESHOLD` | No | Alert when stock falls below this (default `20`) |
| `DEFAULT_VOLUME` | No | Default cyanide volume in litres (default `54000`) |

### 3. Google Sheets

1. Create a Google Cloud service account and download `credentials.json`
2. Share your spreadsheet with the service account email (Editor access)
3. Tabs are created automatically on first run: **Batches**, **Treatments**, **Inventory**

To wipe test data before go-live:

```bash
uv run python scripts/clear_sheet.py
```

### 4. Run

```bash
uv run python main.py
```

## Deploy on Railway

CyanTrack is a **long-running worker** (Telegram polling) — not a web service.

1. Push this repo to GitHub and create a new **Railway** project from it
2. Railway detects `railway.toml` and runs `uv run python main.py`
3. Set these **Variables** in the Railway dashboard:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | Your BotFather token |
| `SPREADSHEET_ID` | Google Sheets ID |
| `GOOGLE_CREDENTIALS_JSON` | Paste the entire `credentials.json` contents |
| `ALLOWED_USERS` | Comma-separated Telegram user IDs |
| `ALERT_CHAT_ID` | Your ops group chat ID (optional) |
| `DISPLAY_TZ` | e.g. `Africa/Accra` |

Do **not** upload `credentials.json` to the repo — use `GOOGLE_CREDENTIALS_JSON` on Railway.

4. Deploy. The service should stay running and log `Bot is live and polling.`

## Workflow

1. `/seed_stock 20` or `/add_stock 20` — set hypochlorite inventory
2. **Log Arrival** — record cyanide delivery
3. **Start Treatment** — begin timer
4. **End Treatment** — buckets → staff → confirm → save
5. **Status** / **Stock Level** / **Monthly Report**

## Development

Without `SPREADSHEET_ID`, the bot uses an in-memory store (data lost on restart).
