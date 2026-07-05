"""
bot/helpers.py
──────────────
Shared utilities: auth guard, formatting, alerts.
"""

import functools
import logging
from datetime import datetime, timezone

from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from bot.keyboards import main_menu_keyboard
from config import LOW_STOCK_THRESHOLD, ALLOWED_USERS, ALERT_CHAT_ID

log = logging.getLogger(__name__)


# ── AUTH ──────────────────────────────────────────────────────────────────────

def is_allowed(update: Update) -> bool:
    if not ALLOWED_USERS:
        return True
    return update.effective_user.id in ALLOWED_USERS


def restricted(func):
    """Decorator: blocks unauthorised users from write commands."""
    @functools.wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not is_allowed(update):
            target = update.callback_query or update.message
            await target.answer("⛔ Not authorised.") if update.callback_query else \
                  await update.message.reply_text("⛔ You are not authorised to use this command.")
            return
        return await func(update, ctx, *args, **kwargs)
    return wrapper


# ── FORMATTING ────────────────────────────────────────────────────────────────

def username(update: Update) -> str:
    """Plain name for storage (Sheets, audit fields)."""
    user = update.effective_user
    return f"@{user.username}" if user.username else user.full_name


def md_escape(text: str) -> str:
    """Escape dynamic text for Telegram legacy Markdown messages."""
    return escape_markdown(text, version=1)


def username_md(update: Update) -> str:
    """Username safe to embed in Markdown message bodies."""
    return md_escape(username(update))


def fmt_duration(minutes: float) -> str:
    if not minutes:
        return "—"
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m" if h else f"{m}m"


def stock_bar(stock: int) -> str:
    """10-block visual bar. Green when healthy, red when low."""
    if stock <= 0:
        return "🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥"
    if stock <= LOW_STOCK_THRESHOLD:
        filled = max(1, min(10, stock * 10 // (LOW_STOCK_THRESHOLD * 2)))
        return "🟧" * filled + "⬜" * (10 - filled)
    filled = min(10, stock // 10)
    return "🟩" * filled + "⬜" * (10 - filled)


def low_stock_warning(stock: int) -> str:
    if stock <= 0:
        return "\n\n🚨 *STOCK EMPTY — Halt operations and restock immediately!*"
    if stock <= LOW_STOCK_THRESHOLD:
        return (
            f"\n\n⚠️ *LOW STOCK ALERT*\n"
            f"Only *{stock} buckets* remaining.\n"
            f"Request a restock now!"
        )
    return ""


def divider() -> str:
    return "━━━━━━━━━━━━━━━━━━"


async def restore_menu(update: Update, text: str) -> None:
    """Edit or send text and restore the persistent bottom menu."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        await update.callback_query.message.reply_text(
            "Use the menu below to continue.",
            reply_markup=main_menu_keyboard(),
        )
    elif update.message:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )


# ── GROUP BROADCAST ALERT ────────────────────────────────────────────────────

async def broadcast_alert(bot: Bot, text: str) -> None:
    """
    Sends a message to the group chat (ALERT_CHAT_ID).
    Used for low-stock warnings and treatment completions.
    Safe to call — silently logs if ALERT_CHAT_ID is not set.
    """
    if not ALERT_CHAT_ID:
        log.warning("ALERT_CHAT_ID not set — skipping broadcast.")
        return
    try:
        await bot.send_message(
            chat_id=int(ALERT_CHAT_ID),
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.error(f"Broadcast failed: {e}")
