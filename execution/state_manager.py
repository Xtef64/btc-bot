import json
import os
import logging
from datetime import datetime, timezone
from config import Config

logger = logging.getLogger(__name__)


class StateManager:
    """
    Persists bot state (portfolio, open position, trade history) as JSON
    files inside data_store/.  All methods are synchronous and thread-safe
    via simple read-modify-write on small files.
    """

    def __init__(self):
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        self._bootstrap()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bootstrap(self):
        """Create default files if they don't exist yet."""
        defaults = [
            (Config.TRADES_FILE, []),
            (Config.POSITIONS_FILE, {}),
            (
                Config.PORTFOLIO_FILE,
                {
                    "initial_capital": Config.INITIAL_CAPITAL,
                    "cash":            Config.INITIAL_CAPITAL,
                    "btc_balance":     0.0,
                    "total_value":     Config.INITIAL_CAPITAL,
                    "pnl":             0.0,
                    "pnl_pct":         0.0,
                    "created_at":      datetime.now(timezone.utc).isoformat(),
                },
            ),
        ]
        for path, default in defaults:
            if not os.path.exists(path):
                self._write(path, default)

    def _read(self, path: str):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"State read error ({path}): {e}")
            return None

    def _write(self, path: str, data):
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"State write error ({path}): {e}")

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    def get_portfolio(self) -> dict:
        return self._read(Config.PORTFOLIO_FILE) or {}

    def update_portfolio(
        self,
        cash: float | None = None,
        btc_balance: float | None = None,
        current_price: float | None = None,
    ) -> dict:
        p = self.get_portfolio()
        if cash is not None:
            p["cash"] = round(cash, 8)
        if btc_balance is not None:
            p["btc_balance"] = round(btc_balance, 8)
        if current_price is not None and p.get("btc_balance") is not None:
            btc_value = p["btc_balance"] * current_price
            p["total_value"] = round(p["cash"] + btc_value, 2)
            p["pnl"]         = round(p["total_value"] - p["initial_capital"], 2)
            p["pnl_pct"]     = round(p["pnl"] / p["initial_capital"], 6)
            p["current_price"] = current_price
        p["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(Config.PORTFOLIO_FILE, p)
        return p

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    def get_position(self) -> dict:
        return self._read(Config.POSITIONS_FILE) or {}

    def has_open_position(self) -> bool:
        return self.get_position().get("status") == "OPEN"

    def open_position(
        self, entry_price: float, quantity: float, stop_loss: float, take_profit: float
    ) -> dict:
        position = {
            "status":      "OPEN",
            "entry_price": entry_price,
            "quantity":    quantity,
            "stop_loss":   stop_loss,
            "take_profit": take_profit,
            "opened_at":   datetime.now(timezone.utc).isoformat(),
        }
        self._write(Config.POSITIONS_FILE, position)
        logger.info(f"Position opened: {quantity:.6f} BTC @ ${entry_price:,.2f}")
        return position

    def close_position(self, exit_price: float) -> dict:
        position = self.get_position()
        if position.get("status") != "OPEN":
            return position

        pnl     = (exit_price - position["entry_price"]) * position["quantity"]
        pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"]

        position.update({
            "status":     "CLOSED",
            "exit_price": exit_price,
            "pnl":        round(pnl, 2),
            "pnl_pct":    round(pnl_pct, 6),
            "closed_at":  datetime.now(timezone.utc).isoformat(),
        })
        self._write(Config.POSITIONS_FILE, position)
        logger.info(f"Position closed @ ${exit_price:,.2f} | PnL ${pnl:+,.2f}")
        return position

    # ------------------------------------------------------------------
    # Trade history
    # ------------------------------------------------------------------

    def get_trades(self, limit: int = 50) -> list:
        trades = self._read(Config.TRADES_FILE) or []
        return trades[-limit:]

    def add_trade(self, trade: dict) -> dict:
        trades = self._read(Config.TRADES_FILE) or []
        trade["id"]        = len(trades) + 1
        trade["timestamp"] = datetime.now(timezone.utc).isoformat()
        trades.append(trade)
        if len(trades) > 1000:
            trades = trades[-1000:]
        self._write(Config.TRADES_FILE, trades)
        return trade
