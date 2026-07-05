"""
bot/keyboards.py
────────────────
All keyboards in one place.

Two types used throughout:
  - ReplyKeyboardMarkup  → persistent bottom menu, always visible
  - InlineKeyboardMarkup → buttons attached to a specific message (most interactive)
"""

from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

REMOVE = ReplyKeyboardRemove()


# ── PERSISTENT BOTTOM MENU ────────────────────────────────────────────────────

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Always-visible bottom menu. Shows after every major action."""
    return ReplyKeyboardMarkup(
        [
            ["🚛 Log Arrival",     "⏱ Start Treatment"],
            ["✅ End Treatment",   "🪣 Stock Level"],
            ["📊 Monthly Report",  "📌 Status"],
        ],
        resize_keyboard=True,
        input_field_placeholder="Tap a button or type a command...",
    )


# ── INLINE: ARRIVAL ───────────────────────────────────────────────────────────

def volume_inline() -> InlineKeyboardMarkup:
    """Inline volume selector — tapping sends callback, no text clutter."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("54,000 L  (standard)", callback_data="vol_54000"),
        ],
        [
            InlineKeyboardButton("27,000 L",  callback_data="vol_27000"),
            InlineKeyboardButton("81,000 L",  callback_data="vol_81000"),
        ],
        [
            InlineKeyboardButton("✏️ Enter custom amount", callback_data="vol_custom"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ])


def arrival_confirm_inline(volume: float, batch_id: str) -> InlineKeyboardMarkup:
    """Confirm or cancel an arrival before it's saved."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ Confirm {volume:,.0f} L", callback_data=f"arrival_confirm_{volume}_{batch_id}"),
            InlineKeyboardButton("❌ Cancel",                    callback_data="arrival_cancel"),
        ],
    ])


# ── INLINE: TREATMENT ─────────────────────────────────────────────────────────

def start_treatment_inline(batch_id: str) -> InlineKeyboardMarkup:
    """Confirm starting a treatment on a specific batch."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱ Start treatment now", callback_data=f"treat_start_{batch_id}"),
            InlineKeyboardButton("❌ Cancel",              callback_data="cancel"),
        ],
    ])


def bucket_inline() -> InlineKeyboardMarkup:
    """Inline bucket count selector."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10", callback_data="bkt_10"),
            InlineKeyboardButton("12", callback_data="bkt_12"),
            InlineKeyboardButton("14", callback_data="bkt_14"),
        ],
        [
            InlineKeyboardButton("16", callback_data="bkt_16"),
            InlineKeyboardButton("18", callback_data="bkt_18"),
            InlineKeyboardButton("20", callback_data="bkt_20"),
        ],
        [
            InlineKeyboardButton("✏️ Enter custom number", callback_data="bkt_custom"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ])


def staff_inline() -> InlineKeyboardMarkup:
    """Inline staff count selector."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("2", callback_data="stf_2"),
            InlineKeyboardButton("3", callback_data="stf_3"),
            InlineKeyboardButton("4", callback_data="stf_4"),
        ],
        [
            InlineKeyboardButton("5", callback_data="stf_5"),
            InlineKeyboardButton("6", callback_data="stf_6"),
            InlineKeyboardButton("7", callback_data="stf_7"),
        ],
        [
            InlineKeyboardButton("✏️ Enter custom number", callback_data="stf_custom"),
        ],
        [
            InlineKeyboardButton("◀️ Back to buckets", callback_data="stf_back"),
            InlineKeyboardButton("❌ Cancel",           callback_data="cancel"),
        ],
    ])


def treatment_confirm_inline() -> InlineKeyboardMarkup:
    """Final confirm before saving a completed treatment."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & save", callback_data="treat_confirm")],
        [InlineKeyboardButton("◀️ Back to staff",  callback_data="treat_back_staff")],
        [InlineKeyboardButton("❌ Cancel",          callback_data="cancel")],
    ])


# ── INLINE: STOCK ─────────────────────────────────────────────────────────────

def restock_inline() -> InlineKeyboardMarkup:
    """Common restock quantities."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("25",  callback_data="rst_25"),
            InlineKeyboardButton("50",  callback_data="rst_50"),
            InlineKeyboardButton("100", callback_data="rst_100"),
        ],
        [
            InlineKeyboardButton("✏️ Enter custom amount", callback_data="rst_custom"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ])


def stock_actions_inline() -> InlineKeyboardMarkup:
    """Actions available from the stock screen."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Add stock",   callback_data="action_addstock"),
            InlineKeyboardButton("🔄 Refresh",     callback_data="action_refreshstock"),
        ],
    ])


# ── INLINE: REPORT ────────────────────────────────────────────────────────────

def report_month_inline() -> InlineKeyboardMarkup:
    """Quick month picker for reports."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    months = []
    row = []
    for i in range(6):
        # last 6 months
        m = (now.month - i - 1) % 12 + 1
        y = now.year if now.month - i > 0 else now.year - 1
        label = datetime(y, m, 1).strftime("%b %Y")
        row.append(InlineKeyboardButton(label, callback_data=f"report_{m}_{y}"))
        if len(row) == 2:
            months.append(row)
            row = []
    if row:
        months.append(row)
    months.append([InlineKeyboardButton("📊 Current month", callback_data=f"report_{now.month}_{now.year}")])
    return InlineKeyboardMarkup(months)
