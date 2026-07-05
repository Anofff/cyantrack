"""
bot/handlers/treatment.py
─────────────────────────
/start_treatment — begins timer
/end_treatment   — multi-step: buckets → staff → confirm → save

UI: fully inline. Messages edit in place. No chat clutter.
"""

from datetime import datetime, timezone

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

from data.store import (
    get_active_batch,
    get_active_treatment,
    start_treatment,
    end_treatment,
    validate_stock_deduction,
    InvalidBatchStateError,
)
from bot.keyboards import bucket_inline, staff_inline, main_menu_keyboard
from bot.helpers import username, username_md, md_escape, fmt_duration, low_stock_warning, divider, restricted, broadcast_alert

# states
WAIT_BUCKETS        = 10
WAIT_STAFF          = 11
WAIT_CUSTOM_BUCKETS = 12
WAIT_CUSTOM_STAFF   = 13


# ── /start_treatment ──────────────────────────────────────────────────────────

@restricted
async def cmd_start_treatment(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    batch = get_active_batch()

    if not batch:
        msg = (
            "⚠️ *No pending batch*\n\n"
            "Log a cyanide delivery first using *🚛 Log Arrival*."
        )
        await _reply(update, msg)
        return

    if batch["status"] == "treating":
        treatment = get_active_treatment(batch["batch_id"])
        started   = treatment["started_at"] if treatment else "unknown"
        elapsed   = ""
        if treatment:
            mins    = round((datetime.now(timezone.utc) - treatment["started_at_raw"]).total_seconds() / 60)
            elapsed = f"\n⏱️ Running for: *{fmt_duration(mins)}*"

        await _reply(
            update,
            f"⚙️ *Treatment already in progress*\n\n"
            f"{divider()}\n"
            f"📦 Batch #{batch['batch_id']} — {batch['volume_l']:,.0f} L\n"
            f"🕐 Started: {started}"
            f"{elapsed}\n\n"
            f"Use *✅ End Treatment* to complete it.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ End treatment now", callback_data="goto_end_treatment")
            ]]),
        )
        return

    # show confirmation before starting
    await _reply(
        update,
        f"⏱️ *Start treatment?*\n\n"
        f"{divider()}\n"
        f"📦 Batch #{batch['batch_id']} — *{batch['volume_l']:,.0f} L*\n"
        f"🕐 Arrived: {batch['arrived_at']}\n\n"
        f"This will start the treatment timer now.",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶️ Start now", callback_data=f"treat_start_{batch['batch_id']}"),
                InlineKeyboardButton("❌ Cancel",     callback_data="cancel"),
            ]
        ]),
    )


@restricted
async def cb_treat_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline confirm → start the treatment."""
    query    = update.callback_query
    await query.answer("⏱️ Starting...")
    batch_id = query.data.replace("treat_start_", "")

    try:
        treatment = start_treatment(batch_id, username(update))
    except InvalidBatchStateError:
        await query.edit_message_text(
            "⚠️ *Cannot start treatment*\n\n"
            "This batch is no longer pending — check *📌 Status* for the current state.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await query.edit_message_text(
        f"⏱️ *Treatment started!*\n\n"
        f"{divider()}\n"
        f"📦 Batch #{batch_id}\n"
        f"🕐 Started: {treatment['started_at']}\n"
        f"👤 By: {username_md(update)}\n\n"
        f"Tap *✅ End Treatment* when done.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── /end_treatment ────────────────────────────────────────────────────────────

@restricted
async def end_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    batch = get_active_batch()

    if not batch or batch["status"] != "treating":
        await _reply(
            update,
            "⚠️ *No active treatment*\n\nStart one with *⏱ Start Treatment* first.",
        )
        return ConversationHandler.END

    treatment = get_active_treatment(batch["batch_id"])
    if not treatment:
        await _reply(update, "⚠️ Could not find active treatment record.")
        return ConversationHandler.END

    ctx.user_data["treatment_id"] = treatment["treatment_id"]
    ctx.user_data["batch_id"]     = batch["batch_id"]
    ctx.user_data["batch_vol"]    = batch["volume_l"]

    elapsed = round((datetime.now(timezone.utc) - treatment["started_at_raw"]).total_seconds() / 60)

    msg = (
        f"✅ *Complete treatment — Batch #{batch['batch_id']}*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{batch['volume_l']:,.0f} L*\n"
        f"⏱️ Running for: *{fmt_duration(elapsed)}*\n\n"
        f"🪣 *How many buckets of Ca(OCl)₂ were used?*"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=bucket_inline())
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=bucket_inline())

    return WAIT_BUCKETS


# bucket callbacks
@restricted
async def cb_bucket_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    buckets = int(query.data.replace("bkt_", ""))
    ctx.user_data["buckets"] = buckets
    await query.edit_message_text(
        f"🪣 Buckets used: *{buckets}*\n\n👷 *How many staff worked this treatment?*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=staff_inline(),
    )
    return WAIT_STAFF


@restricted
async def cb_bucket_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ *Enter number of buckets used:*", parse_mode=ParseMode.MARKDOWN)
    return WAIT_CUSTOM_BUCKETS


@restricted
async def receive_custom_buckets(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        buckets = int(update.message.text.strip())
        if buckets <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a whole number e.g. *14*", parse_mode=ParseMode.MARKDOWN)
        return WAIT_CUSTOM_BUCKETS
    ctx.user_data["buckets"] = buckets
    await update.message.reply_text(
        f"🪣 Buckets used: *{buckets}*\n\n👷 *How many staff worked this treatment?*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=staff_inline(),
    )
    return WAIT_STAFF


# staff callbacks
@restricted
async def cb_staff_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    staff = int(query.data.replace("stf_", ""))
    ctx.user_data["staff"] = staff
    saved = await _show_treatment_summary(update, query, ctx, edit=True)
    if saved:
        ctx.user_data.clear()
        return ConversationHandler.END
    return WAIT_BUCKETS


@restricted
async def cb_staff_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ *Enter number of staff on duty:*", parse_mode=ParseMode.MARKDOWN)
    return WAIT_CUSTOM_STAFF


@restricted
async def receive_custom_staff(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        staff = int(update.message.text.strip())
        if staff <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a whole number e.g. *4*", parse_mode=ParseMode.MARKDOWN)
        return WAIT_CUSTOM_STAFF
    ctx.user_data["staff"] = staff
    saved = await _show_treatment_summary(update, update.message, ctx, edit=False)
    if saved:
        ctx.user_data.clear()
        return ConversationHandler.END
    return WAIT_BUCKETS


async def _show_treatment_summary(
    update: Update, target, ctx: ContextTypes.DEFAULT_TYPE, edit: bool,
) -> bool:
    """Save treatment and display the summary. Returns True if saved."""
    treatment_id = ctx.user_data["treatment_id"]
    buckets      = ctx.user_data["buckets"]
    staff        = ctx.user_data["staff"]
    volume       = ctx.user_data["batch_vol"]

    stock_err = validate_stock_deduction(buckets)
    if stock_err:
        msg = f"⚠️ *Cannot complete treatment*\n\n{stock_err}"
        if edit:
            await target.edit_message_text(
                msg, parse_mode=ParseMode.MARKDOWN, reply_markup=bucket_inline(),
            )
        else:
            await target.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN, reply_markup=bucket_inline(),
            )
        return False

    result    = end_treatment(treatment_id, buckets, staff, username(update))
    duration  = fmt_duration(result["duration_minutes"])
    new_stock = result["new_stock"]
    warning   = low_stock_warning(new_stock)

    text = (
        f"✅ *Treatment complete!*\n\n"
        f"{divider()}\n"
        f"📦 Volume treated: *{volume:,.0f} L*\n"
        f"⏱️ Duration: *{duration}*\n"
        f"🪣 Ca(OCl)₂ used: *{buckets} buckets*\n"
        f"👷 Staff on duty: *{staff}*\n"
        f"📊 Stock remaining: *{new_stock} buckets*"
        f"{warning}"
    )

    if edit:
        await target.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        await target.message.reply_text(
            "Use the menu below to continue.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await target.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())

    # broadcast to group if stock is low
    if new_stock <= 0 or warning:
        try:
            bot = ctx.bot
            alert = (
                f"🚨 *CyanTrack Alert*\n\n"
                f"Treatment completed — Batch #{ctx.user_data['batch_id']}\n"
                f"⏱️ Duration: {duration}\n"
                f"{warning}"
            )
            await broadcast_alert(bot, alert)
        except Exception:
            pass

    return True


async def end_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer("Cancelled")
        await update.callback_query.edit_message_text("❌ Treatment completion cancelled.")
        await update.callback_query.message.reply_text(
            "Use the menu below to continue.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "❌ Treatment completion cancelled.",
            reply_markup=main_menu_keyboard(),
        )
    return ConversationHandler.END


# ── HELPERS ───────────────────────────────────────────────────────────────────

async def _reply(update: Update, text: str, reply_markup=None) -> None:
    kwargs = dict(text=text, parse_mode=ParseMode.MARKDOWN)
    if update.callback_query:
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        await update.callback_query.edit_message_text(**kwargs)
    else:
        kwargs["reply_markup"] = reply_markup or main_menu_keyboard()
        await update.message.reply_text(**kwargs)


# ── REGISTER ──────────────────────────────────────────────────────────────────

def build_start_treatment_handler():
    return [
        CommandHandler("start_treatment", cmd_start_treatment),
        MessageHandler(filters.Regex(r"^⏱ Start Treatment$"), cmd_start_treatment),
        CallbackQueryHandler(cb_treat_start, pattern=r"^treat_start_"),
        CallbackQueryHandler(end_start,      pattern=r"^goto_end_treatment$"),
    ]


def build_end_treatment_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("end_treatment", end_start),
            MessageHandler(filters.Regex(r"^✅ End Treatment$"), end_start),
        ],
        states={
            WAIT_BUCKETS: [
                CallbackQueryHandler(cb_bucket_selected, pattern=r"^bkt_\d+$"),
                CallbackQueryHandler(cb_bucket_custom,   pattern=r"^bkt_custom$"),
            ],
            WAIT_CUSTOM_BUCKETS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_buckets),
            ],
            WAIT_STAFF: [
                CallbackQueryHandler(cb_staff_selected, pattern=r"^stf_\d+$"),
                CallbackQueryHandler(cb_staff_custom,   pattern=r"^stf_custom$"),
            ],
            WAIT_CUSTOM_STAFF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_staff),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", end_cancel),
            CallbackQueryHandler(end_cancel, pattern=r"^cancel$"),
        ],
        per_message=False,
    )
