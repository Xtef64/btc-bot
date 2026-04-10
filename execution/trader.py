import logging
from datetime import datetime, timezone
from config import Config

logger = logging.getLogger(__name__)


class Trader:
    """
    Executes BUY / SELL orders based on engine decisions.

    Risk management
    ---------------
    • Stop loss  : entry × (1 - STOP_LOSS_PCT)
    • Take profit: entry × (1 + TAKE_PROFIT_PCT)
    • Max drawdown guard: if portfolio value drops > MAX_DRAWDOWN_PCT
      below initial capital, no new trades are opened.
    • Position size: POSITION_SIZE_PCT × available cash.

    Paper-trading mode (PAPER_TRADING=true, default) simulates orders
    without touching Binance.
    """

    def __init__(self, binance_client, state_manager):
        self.binance      = binance_client
        self.state        = state_manager
        self.paper        = Config.PAPER_TRADING

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(self, decision: dict, current_price: float) -> dict | None:
        """
        Called every trading cycle.  Returns the executed trade dict or
        None if nothing happened.
        """
        # 1. Always check SL/TP first, regardless of signal
        sl_tp = self._check_sl_tp(current_price)
        if sl_tp:
            return sl_tp

        action = decision["action"]

        # 2. Signal-driven trade
        if action == "BUY" and not self.state.has_open_position():
            if self._drawdown_exceeded():
                logger.warning("Max drawdown reached — BUY blocked.")
                return None
            return self._buy(current_price, decision)

        if action == "SELL" and self.state.has_open_position():
            return self._sell(current_price, decision, reason="SIGNAL")

        return None

    # ------------------------------------------------------------------
    # Stop-loss / take-profit
    # ------------------------------------------------------------------

    def _check_sl_tp(self, price: float) -> dict | None:
        if not self.state.has_open_position():
            return None
        pos = self.state.get_position()
        if price <= pos["stop_loss"]:
            logger.warning(f"STOP LOSS hit @ ${price:,.2f} (SL=${pos['stop_loss']:,.2f})")
            return self._sell(price, {}, reason="STOP_LOSS")
        if price >= pos["take_profit"]:
            logger.info(f"TAKE PROFIT hit @ ${price:,.2f} (TP=${pos['take_profit']:,.2f})")
            return self._sell(price, {}, reason="TAKE_PROFIT")
        return None

    # ------------------------------------------------------------------
    # Buy / Sell
    # ------------------------------------------------------------------

    def _buy(self, price: float, decision: dict) -> dict | None:
        portfolio  = self.state.get_portfolio()
        cash       = portfolio.get("cash", 0.0)
        trade_usd  = cash * Config.POSITION_SIZE_PCT
        quantity   = round(trade_usd / price, 6)

        if quantity <= 0 or trade_usd < 10:
            logger.warning(f"Insufficient cash to buy (available ${cash:.2f})")
            return None

        stop_loss   = round(price * (1 - Config.STOP_LOSS_PCT), 2)
        take_profit = round(price * (1 + Config.TAKE_PROFIT_PCT), 2)

        if self.paper:
            order_id = f"PAPER_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            logger.info(f"[PAPER] BUY {quantity:.6f} BTC @ ${price:,.2f}")
        else:
            order = self.binance.place_market_order("BUY", quantity)
            if not order:
                return None
            order_id = str(order["orderId"])
            fills    = order.get("fills", [])
            if fills:
                price = round(float(fills[0]["price"]), 2)

        self.state.open_position(price, quantity, stop_loss, take_profit)
        self.state.update_portfolio(
            cash=cash - quantity * price,
            btc_balance=quantity,
            current_price=price,
        )

        trade = {
            "type":        "BUY",
            "price":       price,
            "quantity":    quantity,
            "value":       round(price * quantity, 2),
            "stop_loss":   stop_loss,
            "take_profit": take_profit,
            "order_id":    order_id,
            "confidence":  decision.get("confidence", 0),
            "score":       decision.get("aggregate_score", 0),
            "paper":       self.paper,
        }
        return self.state.add_trade(trade)

    def _sell(self, price: float, decision: dict, reason: str = "SIGNAL") -> dict | None:
        portfolio = self.state.get_portfolio()
        position  = self.state.get_position()
        quantity  = position.get("quantity", 0.0)

        if quantity <= 0:
            return None

        if self.paper:
            order_id = f"PAPER_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            logger.info(f"[PAPER] SELL {quantity:.6f} BTC @ ${price:,.2f} ({reason})")
        else:
            order = self.binance.place_market_order("SELL", quantity)
            if not order:
                return None
            order_id = str(order["orderId"])
            fills    = order.get("fills", [])
            if fills:
                price = round(float(fills[0]["price"]), 2)

        closed = self.state.close_position(price)
        self.state.update_portfolio(
            cash=portfolio.get("cash", 0.0) + quantity * price,
            btc_balance=0.0,
            current_price=price,
        )

        trade = {
            "type":      "SELL",
            "reason":    reason,
            "price":     price,
            "quantity":  quantity,
            "value":     round(price * quantity, 2),
            "pnl":       closed.get("pnl", 0),
            "pnl_pct":   closed.get("pnl_pct", 0),
            "order_id":  order_id,
            "confidence": decision.get("confidence", 0),
            "score":     decision.get("aggregate_score", 0),
            "paper":     self.paper,
        }
        return self.state.add_trade(trade)

    # ------------------------------------------------------------------

    def _drawdown_exceeded(self) -> bool:
        p = self.state.get_portfolio()
        dd = (p.get("total_value", p["initial_capital"]) - p["initial_capital"]) / p["initial_capital"]
        return dd < -Config.MAX_DRAWDOWN_PCT
