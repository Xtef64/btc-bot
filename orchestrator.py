"""
orchestrator.py — Main entry point for the BTC trading bot.

Architecture
------------
Main thread   : schedule loop (trading cycles every CHECK_INTERVAL_MINUTES)
Thread 1      : Flask dashboard (binds to $PORT for Railway)
Thread 2      : Telegram bot polling (optional, graceful skip if no token)

Each trading cycle:
  1. Fetch current BTC price from Binance
  2. Update portfolio valuation
  3. Compute technical / institutional / sentiment signals
  4. Run decision engine → BUY | SELL | HOLD
  5. Execute trade via Trader (paper or live)
  6. Push updated signals to dashboard and Telegram
"""

import sys
import threading
import logging
import schedule
import time
from datetime import datetime, timezone

from config import Config

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("orchestrator")

# ── Component initialisation ──────────────────────────────────────────────────
from data.binance_client    import BinanceClient
from data.arkham_client     import ArkhamClient
from data.sentiment_client  import SentimentClient
from signals.technical      import TechnicalSignals
from signals.institutional  import InstitutionalSignals
from signals.sentiment      import SentimentSignals
from engine.decision        import DecisionEngine
from execution.trader       import Trader
from execution.state_manager import StateManager
from dashboard.app          import run_dashboard, update_signals
from bot_telegram.telegram_bot import run_telegram_bot, update_signals_ref, send_notification

binance   = BinanceClient()
arkham    = ArkhamClient()
sentiment_client = SentimentClient()
state     = StateManager()
trader    = Trader(binance, state)

technical     = TechnicalSignals(binance)
institutional = InstitutionalSignals(arkham, binance)
sentiment     = SentimentSignals(sentiment_client)
engine        = DecisionEngine(technical, institutional, sentiment)

# ── Trading cycle ─────────────────────────────────────────────────────────────

def trading_cycle():
    try:
        logger.info("=" * 55)
        logger.info(f"Cycle start  {datetime.now(timezone.utc).isoformat()}")

        # 1. Price
        price = binance.get_current_price()
        if price is None:
            logger.error("Could not fetch BTC price — skipping cycle.")
            return
        logger.info(f"BTC/USDT = ${price:,.2f}")

        # 2. Portfolio mark-to-market
        state.update_portfolio(current_price=price)

        # 3–4. Signals + decision
        decision = engine.evaluate()
        decision["current_price"] = price  # pass price to dashboard

        # 5. Push to dashboard / Telegram
        update_signals(decision)
        update_signals_ref(decision)

        # 6. Execute
        trade = trader.execute(decision, price)

        if trade:
            _notify_trade(trade)

        # 7. Log summary
        p = state.get_portfolio()
        logger.info(
            f"Portfolio ${p.get('total_value', 0):,.2f} | "
            f"P&L ${p.get('pnl', 0):+,.2f} ({p.get('pnl_pct', 0):+.2%})"
        )

    except Exception:
        logger.exception("Unhandled exception in trading cycle")


def _notify_trade(trade: dict):
    if trade["type"] == "BUY":
        msg = (
            f"*BUY executed*\n"
            f"Price : ${trade['price']:,.2f}\n"
            f"Qty   : {trade['quantity']:.6f} BTC\n"
            f"SL    : ${trade['stop_loss']:,.2f}\n"
            f"TP    : ${trade['take_profit']:,.2f}\n"
            f"Score : {trade['score']:.4f}"
        )
    else:
        pnl = trade.get("pnl", 0)
        msg = (
            f"*SELL executed* \\({trade.get('reason', 'SIGNAL')}\\)\n"
            f"Price : ${trade['price']:,.2f}\n"
            f"Qty   : {trade['quantity']:.6f} BTC\n"
            f"P\\&L  : ${pnl:+,.2f} ({trade.get('pnl_pct', 0):+.2%})"
        )
    send_notification(msg)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 55)
    logger.info("BTC Trading Bot starting up")
    logger.info(f"Mode     : {'PAPER TRADING' if Config.PAPER_TRADING else '⚠️  LIVE TRADING'}")
    logger.info(f"Pair     : {Config.TRADING_PAIR}")
    logger.info(f"Interval : {Config.CHECK_INTERVAL_MINUTES} min")
    logger.info(f"Capital  : ${Config.INITIAL_CAPITAL:,.2f}")
    logger.info("=" * 55)

    # Flask dashboard thread
    t_dash = threading.Thread(target=run_dashboard, daemon=True, name="dashboard")
    t_dash.start()
    logger.info(f"Dashboard → http://0.0.0.0:{Config.PORT}")

    # Telegram bot thread
    t_tg = threading.Thread(target=run_telegram_bot, daemon=True, name="telegram")
    t_tg.start()
    logger.info("Telegram bot thread started")

    # Run first cycle immediately (don't wait for the interval)
    trading_cycle()

    # Schedule recurring cycles
    schedule.every(Config.CHECK_INTERVAL_MINUTES).minutes.do(trading_cycle)
    logger.info(f"Scheduler armed — next cycle in {Config.CHECK_INTERVAL_MINUTES} min")

    # Keep main thread alive
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
