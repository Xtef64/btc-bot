import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from config import Config

logger = logging.getLogger(__name__)

# Shared reference updated by orchestrator after each cycle
_latest_signals: dict = {}


def update_signals_ref(signals: dict):
    global _latest_signals
    _latest_signals = signals


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*BTC Trading Bot*\n\n"
        "Available commands:\n"
        "/status   — Bot & portfolio overview\n"
        "/position — Current open position\n"
        "/portfolio — Detailed portfolio\n"
        "/trades   — Last 5 trades\n"
        "/signals  — Latest signal scores",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from execution.state_manager import StateManager
    state = StateManager()
    p   = state.get_portfolio()
    pos = state.get_position()
    mode = "PAPER" if Config.PAPER_TRADING else "LIVE"

    msg = (
        f"*BTC Bot [{mode}]*\n\n"
        f"Portfolio : ${p.get('total_value', 0):,.2f}\n"
        f"Cash      : ${p.get('cash', 0):,.2f}\n"
        f"BTC       : {p.get('btc_balance', 0):.6f}\n"
        f"P\\&L      : ${p.get('pnl', 0):+,.2f} ({p.get('pnl_pct', 0):+.2%})\n"
        f"Position  : {'🟢 OPEN' if pos.get('status') == 'OPEN' else '⚪ NONE'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from execution.state_manager import StateManager
    pos = StateManager().get_position()

    if pos.get("status") != "OPEN":
        await update.message.reply_text("No open position.")
        return

    msg = (
        f"*Open Position*\n\n"
        f"Entry       : ${pos.get('entry_price', 0):,.2f}\n"
        f"Quantity    : {pos.get('quantity', 0):.6f} BTC\n"
        f"Stop Loss   : ${pos.get('stop_loss', 0):,.2f}\n"
        f"Take Profit : ${pos.get('take_profit', 0):,.2f}\n"
        f"Opened      : {pos.get('opened_at', 'N/A')}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from execution.state_manager import StateManager
    p = StateManager().get_portfolio()

    msg = (
        f"*Portfolio*\n\n"
        f"Total Value    : ${p.get('total_value', 0):,.2f}\n"
        f"Cash           : ${p.get('cash', 0):,.2f}\n"
        f"BTC            : {p.get('btc_balance', 0):.6f}\n"
        f"Initial Capital: ${p.get('initial_capital', 0):,.2f}\n"
        f"P\\&L           : ${p.get('pnl', 0):+,.2f} ({p.get('pnl_pct', 0):+.2%})"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from execution.state_manager import StateManager
    trades = StateManager().get_trades(limit=5)

    if not trades:
        await update.message.reply_text("No trades yet.")
        return

    msg = "*Last Trades*\n\n"
    for t in reversed(trades):
        icon = "🟢" if t["type"] == "BUY" else "🔴"
        msg += f"{icon} {t['type']}  {t.get('quantity', 0):.4f} BTC @ ${t.get('price', 0):,.0f}"
        if t["type"] == "SELL":
            pnl = t.get("pnl", 0)
            msg += f"  →  P\\&L ${pnl:+,.2f}"
        reason = t.get("reason", "")
        if reason and reason != "SIGNAL":
            msg += f"  \\({reason}\\)"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _latest_signals:
        await update.message.reply_text("No signals computed yet — wait for the next cycle.")
        return

    s = _latest_signals
    fng = s.get("sentiment", {}).get("fear_greed_value", "—")
    fng_label = s.get("sentiment", {}).get("fear_greed_label", "")

    msg = (
        f"*Latest Signals*\n\n"
        f"Decision      : *{s.get('action', '—')}*\n"
        f"Aggregate     : `{s.get('aggregate_score', 0):.4f}`\n"
        f"Confidence    : {s.get('confidence', 0):.1%}\n\n"
        f"Technical     : `{s.get('technical', {}).get('score', 0):.4f}`\n"
        f"Institutional : `{s.get('institutional', {}).get('score', 0):.4f}`\n"
        f"Sentiment     : `{s.get('sentiment', {}).get('score', 0):.4f}`\n\n"
        f"Fear & Greed  : {fng}/100 — {fng_label}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ------------------------------------------------------------------
# Notification helper (called by orchestrator)
# ------------------------------------------------------------------

async def _send(message: str):
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return
    try:
        bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_message(
                chat_id=Config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"Telegram send error: {e}")


def send_notification(message: str):
    """Thread-safe fire-and-forget notification."""
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return
    try:
        asyncio.run(_send(message))
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")


# ------------------------------------------------------------------
# Bot runner (called in its own thread)
# ------------------------------------------------------------------

def run_telegram_bot():
    if not Config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return

    async def _main():
        app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start",     cmd_start))
        app.add_handler(CommandHandler("status",    cmd_status))
        app.add_handler(CommandHandler("position",  cmd_position))
        app.add_handler(CommandHandler("portfolio", cmd_portfolio))
        app.add_handler(CommandHandler("trades",    cmd_trades))
        app.add_handler(CommandHandler("signals",   cmd_signals))
        logger.info("Telegram bot polling started.")
        await app.run_polling(drop_pending_updates=True)

    asyncio.run(_main())
