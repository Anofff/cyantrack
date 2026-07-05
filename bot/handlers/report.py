"""
bot/handlers/report.py
──────────────────────
/status → live batch status with inline actions
/report → month picker inline → renders full monthly summary
"""

from datetime import datetime, timezone

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode

from data.store import get_active_batch, get_active_treatment, monthly_report, get_stock
from bot.keyboards import report_month_inline, main_menu_keyboard
from bot.helpers import fmt_duration, low_stock_warning, divider, stock_bar
from config import LOW_STOCK_THRESHOLD


# ── /status ───────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    batch = get_active_batch()
    stock = get_stock()

    if not batch:
        bar = stock_bar(stock)
        await update.message.reply_text(
            f"✅ *All clear — no active batch*\n\n"
            f"{divider()}\n"
            f"🪣 Stock: *{stock} buckets*\n"
            f"{bar}\n\n"
            f"Waiting for next delivery."
            f"{low_stock_warning(stock)}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚛 Log new arrival", callback_data="goto_arrival"),
                InlineKeyboardButton("🪣 Stock details",   callback_data="action_refreshstock"),
            ]]),
        )
        return

    status_emoji = {"pending": "⏳", "treating": "⚙️"}.get(batch["status"], "❓")
    elapsed_line = ""

    if batch["status"] == "treating":
        treatment = get_active_treatment(batch["batch_id"])
        if treatment:
            mins = round((datetime.now(timezone.utc) - treatment["started_at_raw"]).total_seconds() / 60)
            elapsed_line = f"\n⏱️ Treating for: *{fmt_duration(mins)}*"

    # inline actions depend on current status
    if batch["status"] == "pending":
        action_row = [[
            InlineKeyboardButton("⏱ Start treatment", callback_data=f"treat_start_{batch['batch_id']}"),
        ]]
    else:
        action_row = [[
            InlineKeyboardButton("✅ End treatment", callback_data="goto_end_treatment"),
            InlineKeyboardButton("🔄 Refresh",       callback_data="status_refresh"),
        ]]

    await update.message.reply_text(
        f"{status_emoji} *Batch #{batch['batch_id']}*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{batch['volume_l']:,.0f} L*\n"
        f"🕐 Arrived: {batch['arrived_at']}\n"
        f"📌 Status: *{batch['status'].upper()}*\n"
        f"👤 By: {batch['logged_by']}"
        f"{elapsed_line}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(action_row),
    )


async def cb_status_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh the status message in place."""
    query = update.callback_query
    await query.answer("🔄 Refreshed")
    batch = get_active_batch()

    if not batch:
        await query.edit_message_text("✅ *All clear — no active batch.*", parse_mode=ParseMode.MARKDOWN)
        return

    treatment   = get_active_treatment(batch["batch_id"]) if batch["status"] == "treating" else None
    elapsed_str = ""
    if treatment:
        mins        = round((datetime.now(timezone.utc) - treatment["started_at_raw"]).total_seconds() / 60)
        elapsed_str = f"\n⏱️ Treating for: *{fmt_duration(mins)}*"

    status_emoji = {"pending": "⏳", "treating": "⚙️"}.get(batch["status"], "❓")
    action_row = (
        [[InlineKeyboardButton("✅ End treatment", callback_data="goto_end_treatment"),
          InlineKeyboardButton("🔄 Refresh",       callback_data="status_refresh")]]
        if batch["status"] == "treating" else
        [[InlineKeyboardButton("⏱ Start treatment", callback_data=f"treat_start_{batch['batch_id']}")]]
    )

    await query.edit_message_text(
        f"{status_emoji} *Batch #{batch['batch_id']}*\n\n"
        f"{divider()}\n"
        f"📦 Volume: *{batch['volume_l']:,.0f} L*\n"
        f"🕐 Arrived: {batch['arrived_at']}\n"
        f"📌 Status: *{batch['status'].upper()}*"
        f"{elapsed_str}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(action_row),
    )


# ── /report ───────────────────────────────────────────────────────────────────

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show month picker."""
    await update.message.reply_text(
        "📊 *Monthly Report*\n\nSelect a month:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=report_month_inline(),
    )


async def cb_report_month(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Render the report for the selected month."""
    query = update.callback_query
    await query.answer("Loading report...")

    _, month_str, year_str = query.data.split("_")
    month = int(month_str)
    year  = int(year_str)

    r          = monthly_report(month, year)
    month_name = datetime(year, month, 1).strftime("%B %Y")
    stock      = r["current_stock"]
    bar        = stock_bar(stock)
    warning    = low_stock_warning(stock)

    stock_status = (
        "🔴 *Low stock — reorder needed*"
        if stock <= LOW_STOCK_THRESHOLD
        else "🟢 Stock healthy"
    )

    no_data = r["arrivals"] == 0 and r["treatments_done"] == 0

    if no_data:
        body = f"_No data recorded for {month_name}_"
    else:
        body = (
            f"🚛 Deliveries: *{r['arrivals']}*\n"
            f"💧 Total volume: *{r['total_volume']:,.0f} L*\n\n"
            f"⚙️ Treatments done: *{r['treatments_done']}*\n"
            f"🪣 Hypochlorite used: *{r['total_buckets']} buckets*\n"
            f"⏱️ Avg treatment: *{fmt_duration(r['avg_duration_mins'])}*\n"
            f"⏱️ Fastest: *{fmt_duration(r['min_duration'])}*\n"
            f"⏱️ Slowest: *{fmt_duration(r['max_duration'])}*\n"
            f"👷 Avg staff: *{r['avg_staff']}*"
        )

    await query.edit_message_text(
        f"📊 *Report — {month_name}*\n\n"
        f"{divider()}\n"
        f"{body}\n\n"
        f"{divider()}\n"
        f"🪣 Current stock: *{stock} buckets*\n"
        f"{bar}\n"
        f"{stock_status}"
        f"{warning}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Pick another month", callback_data="report_back"),
        ]]),
    )


async def cb_report_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 *Monthly Report*\n\nSelect a month:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=report_month_inline(),
    )


# ── REGISTER ──────────────────────────────────────────────────────────────────

def build_report_handlers() -> list:
    return [
        CommandHandler("status", cmd_status),
        CommandHandler("report", cmd_report),
        MessageHandler(filters.Regex(r"^📌 Status$"),          cmd_status),
        MessageHandler(filters.Regex(r"^📊 Monthly Report$"),   cmd_report),
        CallbackQueryHandler(cb_status_refresh, pattern=r"^status_refresh$"),
        CallbackQueryHandler(cb_report_month,   pattern=r"^report_\d+_\d+$"),
        CallbackQueryHandler(cb_report_back,    pattern=r"^report_back$"),
    ]
