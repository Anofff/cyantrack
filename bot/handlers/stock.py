"""
bot/handlers/stock.py
─────────────────────
/stock     → live inventory display with action buttons
/add_stock → inline quantity picker → confirm → save
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

from data.store import get_stock, add_stock
from bot.keyboards import restock_inline, stock_actions_inline, main_menu_keyboard
from bot.helpers import username, username_md, md_escape, stock_bar, low_stock_warning, divider, restricted, restore_menu
from config import LOW_STOCK_THRESHOLD

WAIT_CUSTOM_RESTOCK = 30


# ── /stock ────────────────────────────────────────────────────────────────────

async def cmd_stock(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_stock_view(update, ctx)


async def _send_stock_view(update: Update, ctx, edit: bool = False) -> None:
    current = get_stock()
    bar     = stock_bar(current)
    warning = low_stock_warning(current)

    pct = min(100, int(current / max(current, LOW_STOCK_THRESHOLD * 2) * 100))

    status = (
        f"🔴 *Critical — reorder immediately!*"
        if current <= 0 else
        f"🟠 *Low — reorder soon* (threshold: {LOW_STOCK_THRESHOLD})"
        if current <= LOW_STOCK_THRESHOLD else
        f"🟢 *Healthy* (reorder at {LOW_STOCK_THRESHOLD} buckets)"
    )

    text = (
        f"🪣 *Hypochlorite Inventory*\n\n"
        f"{divider()}\n"
        f"Stock level: *{current} buckets*\n"
        f"{bar} {pct}%\n\n"
        f"Status: {status}"
        f"{warning}"
    )

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=stock_actions_inline()
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=stock_actions_inline()
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=stock_actions_inline()
        )


async def cb_refresh_stock(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer("🔄 Refreshed")
    await _send_stock_view(update, ctx, edit=True)


# ── /add_stock ────────────────────────────────────────────────────────────────

@restricted
async def add_stock_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    # allow inline: /add_stock 50
    if ctx.args:
        try:
            qty = int(ctx.args[0])
            if qty > 0:
                await _save_restock(update, ctx, qty)
                return ConversationHandler.END
        except ValueError:
            pass

    current = get_stock()
    text = (
        f"📦 *Restock hypochlorite*\n\n"
        f"{divider()}\n"
        f"Current stock: *{current} buckets*\n\n"
        f"How many buckets are being added?"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=restock_inline())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=restock_inline())

    return WAIT_CUSTOM_RESTOCK


async def cb_restock_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    qty = int(query.data.replace("rst_", ""))
    await _save_restock_query(query, ctx, qty, username(update))
    return ConversationHandler.END


async def cb_restock_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ *Enter number of buckets to add:*", parse_mode=ParseMode.MARKDOWN)
    return WAIT_CUSTOM_RESTOCK


async def receive_custom_restock(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a positive whole number, e.g. *60*", parse_mode=ParseMode.MARKDOWN)
        return WAIT_CUSTOM_RESTOCK
    await _save_restock(update, ctx, qty)
    return ConversationHandler.END


async def _save_restock(update: Update, ctx, qty: int) -> None:
    new_total = add_stock(qty, username(update))
    bar = stock_bar(new_total)
    text = (
        f"✅ *Stock updated!*\n\n"
        f"{divider()}\n"
        f"➕ Added: *{qty} buckets*\n"
        f"📦 New total: *{new_total} buckets*\n"
        f"{bar}\n"
        f"👤 By: {username_md(update)}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())


async def _save_restock_query(query, ctx, qty: int, user: str) -> None:
    new_total = add_stock(qty, user)
    bar = stock_bar(new_total)
    await query.edit_message_text(
        f"✅ *Stock updated!*\n\n"
        f"{divider()}\n"
        f"➕ Added: *{qty} buckets*\n"
        f"📦 New total: *{new_total} buckets*\n"
        f"{bar}\n"
        f"👤 By: {md_escape(user)}",
        parse_mode=ParseMode.MARKDOWN,
    )
    await query.message.reply_text(
        "Use the menu below to continue.",
        reply_markup=main_menu_keyboard(),
    )


@restricted
async def cmd_seed_stock(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """One-time seed for pilot sessions: /seed_stock 50"""
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/seed_stock 50` — sets initial bucket count.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
        return
    try:
        qty = int(ctx.args[0])
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Enter a positive number, e.g. `/seed_stock 50`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
        return

    current = get_stock()
    if current > 0:
        await update.message.reply_text(
            f"⚠️ Stock is already *{current} buckets*.\n"
            f"Use `/add_stock` to add more, or restart the bot to re-seed.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
        return

    new_total = add_stock(qty, username(update), notes="initial seed")
    bar = stock_bar(new_total)
    await update.message.reply_text(
        f"✅ *Stock seeded for pilot*\n\n"
        f"{divider()}\n"
        f"📦 Starting stock: *{new_total} buckets*\n"
        f"{bar}\n"
        f"👤 By: {username_md(update)}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def restock_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer("Cancelled")
    await restore_menu(update, "❌ Restock cancelled.")
    return ConversationHandler.END


# ── REGISTER ──────────────────────────────────────────────────────────────────

def build_stock_handlers() -> list:
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("add_stock", add_stock_start),
            CallbackQueryHandler(add_stock_start, pattern=r"^action_addstock$"),
        ],
        states={
            WAIT_CUSTOM_RESTOCK: [
                CallbackQueryHandler(cb_restock_selected, pattern=r"^rst_\d+$"),
                CallbackQueryHandler(cb_restock_custom,   pattern=r"^rst_custom$"),
                CallbackQueryHandler(restock_cancel,      pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_restock),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", restock_cancel),
            CallbackQueryHandler(restock_cancel, pattern=r"^cancel$"),
        ],
        per_message=False,
    )
    return [
        CommandHandler("stock", cmd_stock),
        CommandHandler("seed_stock", cmd_seed_stock),
        MessageHandler(filters.Regex(r"^🪣 Stock Level$"), cmd_stock),
        CallbackQueryHandler(cb_refresh_stock, pattern=r"^action_refreshstock$"),
        conv,
    ]
