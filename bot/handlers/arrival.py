"""
bot/handlers/arrival.py
───────────────────────
/arrival — Log a cyanide delivery.

UI flow:
  1. Bot sends message with inline volume buttons
  2. Worker taps a volume (or taps "Enter custom")
  3. If standard → confirmation inline appears, bot edits the same message
  4. Worker confirms → batch saved, group notified
  5. If custom → bot asks for typed input
"""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode

from data.store import log_arrival
from bot.keyboards import volume_inline, main_menu_keyboard, REMOVE
from bot.helpers import username, restricted, divider

# conversation states
WAIT_CUSTOM_VOLUME = 0


# ── ENTRY ─────────────────────────────────────────────────────────────────────

@restricted
async def arrival_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: show inline volume picker."""
    text = (
        "🚛 *New cyanide delivery*\n\n"
        f"{divider()}\n"
        "Select the volume that arrived:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=volume_inline())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=volume_inline())
    return WAIT_CUSTOM_VOLUME


# ── INLINE CALLBACKS ──────────────────────────────────────────────────────────

@restricted
async def cb_volume_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Worker tapped a standard volume button."""
    query = update.callback_query
    await query.answer()

    volume = float(query.data.replace("vol_", ""))
    ctx.user_data["pending_volume"] = volume

    await query.edit_message_text(
        f"🚛 *Confirm delivery*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{volume:,.0f} L*\n"
        f"👤 Logged by: {username(update)}\n\n"
        f"Is this correct?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_confirm_inline(volume),
    )
    return WAIT_CUSTOM_VOLUME


@restricted
async def cb_volume_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Worker wants to type a custom volume."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ *Enter the volume in litres:*\n\n_e.g. 54000_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return WAIT_CUSTOM_VOLUME


async def receive_custom_volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle typed custom volume."""
    text = update.message.text.strip().replace(",", "")
    try:
        volume = float(text)
        if volume <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Enter a number e.g. *54000*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return WAIT_CUSTOM_VOLUME

    ctx.user_data["pending_volume"] = volume
    await update.message.reply_text(
        f"🚛 *Confirm delivery*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{volume:,.0f} L*\n"
        f"👤 Logged by: {username(update)}\n\n"
        f"Is this correct?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_confirm_inline(volume),
    )
    return WAIT_CUSTOM_VOLUME


@restricted
async def cb_arrival_confirmed(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Worker confirmed — save the batch."""
    query = update.callback_query
    await query.answer("✅ Saving...")

    volume = ctx.user_data.get("pending_volume", 54000.0)
    batch  = log_arrival(volume, username(update))

    await query.edit_message_text(
        f"✅ *Arrival logged — Batch #{batch['batch_id']}*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{volume:,.0f} L*\n"
        f"🕐 Time: {batch['arrived_at']}\n"
        f"👤 Logged by: {batch['logged_by']}\n\n"
        f"Tap *⏱ Start Treatment* in the menu when ready.",
        parse_mode=ParseMode.MARKDOWN,
    )
    ctx.user_data.clear()
    return ConversationHandler.END


async def cb_arrival_cancelled(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Cancelled")
    await query.edit_message_text("❌ Arrival cancelled.")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── HELPER ────────────────────────────────────────────────────────────────────

def _confirm_inline(volume: float):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ Yes, save {volume:,.0f} L", callback_data="arrival_confirm"),
            InlineKeyboardButton("✏️ Change",                      callback_data="vol_custom"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="arrival_cancel")],
    ])


# ── REGISTER ──────────────────────────────────────────────────────────────────

def build_arrival_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("arrival", arrival_start),
            MessageHandler(filters.Regex(r"^🚛 Log Arrival$"), arrival_start),
        ],
        states={
            WAIT_CUSTOM_VOLUME: [
                CallbackQueryHandler(cb_volume_selected,   pattern=r"^vol_\d+$"),
                CallbackQueryHandler(cb_volume_custom,     pattern=r"^vol_custom$"),
                CallbackQueryHandler(cb_arrival_confirmed, pattern=r"^arrival_confirm$"),
                CallbackQueryHandler(cb_arrival_cancelled, pattern=r"^arrival_cancel$"),
                CallbackQueryHandler(cb_arrival_cancelled, pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_volume),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cb_arrival_cancelled),
        ],
        per_message=False,
    )
