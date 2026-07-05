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

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode

from data.api import log_arrival, get_active_batch, ActiveBatchError
from data.exceptions import SheetsWriteError
from bot.keyboards import volume_inline, main_menu_keyboard
from bot.helpers import username, username_md, md_escape, restricted, divider, broadcast_alert, restore_menu

# conversation states
WAIT_CUSTOM_VOLUME = 0


def _active_batch_message(batch: dict) -> tuple[str, InlineKeyboardMarkup]:
    status = batch["status"]
    if status == "treating":
        actions = [[InlineKeyboardButton("✅ End treatment", callback_data="goto_end_treatment")]]
    else:
        actions = [[InlineKeyboardButton("⏱ Start treatment", callback_data=f"treat_start_{batch['batch_id']}")]]
    actions.append([InlineKeyboardButton("📌 View status", callback_data="status_refresh")])

    text = (
        f"⚠️ *Batch #{batch['batch_id']} is still active*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{batch['volume_l']:,.0f} L*\n"
        f"📌 Status: *{status.upper()}*\n\n"
        f"Finish or complete this batch before logging a new arrival."
    )
    return text, InlineKeyboardMarkup(actions)


# ── ENTRY ─────────────────────────────────────────────────────────────────────

@restricted
async def arrival_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: show inline volume picker."""
    active = get_active_batch()
    if active:
        text, markup = _active_batch_message(active)
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup,
            )
        else:
            await update.message.reply_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup,
            )
        return ConversationHandler.END

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
        f"👤 Logged by: {username_md(update)}\n\n"
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


@restricted
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
        f"👤 Logged by: {username_md(update)}\n\n"
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
    try:
        batch = log_arrival(volume, username(update))
    except ActiveBatchError as e:
        text, markup = _active_batch_message(e.batch)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup,
        )
        ctx.user_data.clear()
        return ConversationHandler.END
    except SheetsWriteError:
        await query.edit_message_text(
            "❌ *Could not save to Google Sheets*\n\nPlease try again in a moment.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ *Arrival logged — Batch #{batch['batch_id']}*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{volume:,.0f} L*\n"
        f"🕐 Time: {batch['arrived_at']}\n"
        f"👤 Logged by: {md_escape(batch['logged_by'])}\n\n"
        f"Tap *⏱ Start Treatment* in the menu when ready.",
        parse_mode=ParseMode.MARKDOWN,
    )
    await query.message.reply_text(
        "Use the menu below to continue.",
        reply_markup=main_menu_keyboard(),
    )

    alert = (
        f"🚛 *Cyanide arrival logged*\n\n"
        f"Batch #{batch['batch_id']} — *{volume:,.0f} L*\n"
        f"🕐 {batch['arrived_at']}\n"
        f"👤 {md_escape(batch['logged_by'])}"
    )
    await broadcast_alert(ctx.bot, alert)

    ctx.user_data.clear()
    return ConversationHandler.END


async def cb_arrival_cancelled(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer("Cancelled")
    ctx.user_data.clear()
    await restore_menu(update, "❌ Arrival cancelled.")
    return ConversationHandler.END


# ── HELPER ────────────────────────────────────────────────────────────────────

def _confirm_inline(volume: float):
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
