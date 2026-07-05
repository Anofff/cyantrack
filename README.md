# CyanTrack

Telegram bot for cyanide delivery tracking, treatment cycles, and hypochlorite inventory. Data is stored in Google Sheets.

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | From [@BotFather](https://t.me/BotFather) |
| `GOOGLE_CREDENTIALS_PATH` | Yes | Path to service account JSON (default `./credentials.json`) |
| `SPREADSHEET_ID` | Yes | Sheet ID from the Google Sheets URL |
| `ALLOWED_USERS` | No | Comma-separated Telegram user IDs for write access |
| `ALERT_CHAT_ID` | No | Group chat ID for arrival/low-stock alerts |
| `DISPLAY_TZ` | No | Timezone for display (default `Africa/Accra`) |
| `INITIAL_STOCK` | No | Auto-seed buckets on startup if stock is empty |

### 3. Google Sheets

1. Create a Google Cloud service account and download `credentials.json`
2. Share your spreadsheet with the service account email (Editor access)
3. Tab names are created automatically on first run if missing: **Batches**, **Treatments**, **Inventory**
   (empty spreadsheets get a full skeleton with formatted header rows)

### 4. Run

```bash
uv run python main.py
```

## Workflow

1. `/seed_stock 20` or `/add_stock 20` — set hypochlorite inventory
2. **Log Arrival** — record cyanide delivery
3. **Start Treatment** — begin timer
4. **End Treatment** — buckets → staff → confirm → save
5. **Status** / **Stock Level** / **Monthly Report**

## Development

Without `SPREADSHEET_ID`, the bot uses an in-memory store (data lost on restart).
