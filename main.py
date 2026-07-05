"""
main.py — CyanTrack Bot entry point
Run: python main.py
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

from config import BOT_TOKEN, INITIAL_STOCK
from bot.keyboards import main_menu_keyboard
from bot.helpers import md_escape
from bot.handlers.arrival import build_arrival_handler
from bot.handlers.treatment import build_start_treatment_handler, build_end_treatment_handler
from bot.handlers.stock import build_stock_handlers
from bot.handlers.report import build_report_handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

HELP_TEXT = (
    "🧪 *CyanTrack — Operations Bot*\n\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🚛 */arrival* — Log a cyanide delivery\n"
    "⏱ */start\\_treatment* — Begin treatment timer\n"
    "✅ */end\\_treatment* — Complete treatment\n"
    "🪣 */stock* — Hypochlorite inventory\n"
    "📦 */add\\_stock* `<n>` — Restock inventory\n"
    "🌱 */seed\\_stock* `<n>` — Set initial stock (pilot)\n"
    "📌 */status* — Active batch status\n"
    "📊 */report* — Monthly summary\n"
    "❌ */cancel* — Cancel current action\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "_Use the menu buttons below for the fastest experience._"
)

WORKFLOW_TEXT = (
    "📋 *Typical shift workflow*\n\n"
    "1️⃣ Seed or restock hypochlorite (`/seed_stock` or `/add_stock`)\n"
    "2️⃣ *🚛 Log Arrival* when the truck delivers\n"
    "3️⃣ *⏱ Start Treatment* when work begins\n"
    "4️⃣ *✅ End Treatment* when done — confirm buckets & staff\n"
    "5️⃣ Check *📌 Status* or *🪣 Stock Level* anytime\n\n"
    "_Data resets if the bot restarts — normal during pilot._"
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    name = md_escape(update.effective_user.first_name)
    await update.message.reply_text(
        f"👋 Welcome, *{name}!*\n\n"
        f"I'm your CyanTrack operations assistant.\n"
        f"I track cyanide deliveries, treatment cycles, "
        f"and hypochlorite inventory.\n\n"
        f"{WORKFLOW_TEXT}\n\n"
        f"{HELP_TEXT}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❌ Action cancelled.",
        reply_markup=main_menu_keyboard(),
    )


async def cb_goto_arrival(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers.arrival import arrival_start
    await arrival_start(update, ctx)


async def cb_goto_end_treatment(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers.treatment import end_start
    await end_start(update, ctx)


async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤔 I didn't understand that.\n"
        "Use the menu buttons or type /help.",
        reply_markup=main_menu_keyboard(),
    )


def main() -> None:
    log.info("🚀 Starting CyanTrack bot...")

    if INITIAL_STOCK:
        from data.store import get_stock, add_stock
        if get_stock() == 0:
            add_stock(INITIAL_STOCK, "system", notes="startup seed")
            log.info("Seeded initial stock: %s buckets", INITIAL_STOCK)

    app = Application.builder().token(BOT_TOKEN).build()

    # core
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))

    # global inline navigation callbacks
    app.add_handler(CallbackQueryHandler(cb_goto_arrival,       pattern=r"^goto_arrival$"))
    app.add_handler(CallbackQueryHandler(cb_goto_end_treatment, pattern=r"^goto_end_treatment$"))

    # arrival (ConversationHandler — must be before catch-all)
    app.add_handler(build_arrival_handler())

    # treatment
    app.add_handler(build_end_treatment_handler())
    for h in build_start_treatment_handler():
        app.add_handler(h)

    # stock
    for h in build_stock_handlers():
        app.add_handler(h)

    # report + status
    for h in build_report_handlers():
        app.add_handler(h)

    # /cancel when not inside a conversation (conv handlers register their own fallbacks)
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # catch-all
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    log.info("✅ Bot is live and polling.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
