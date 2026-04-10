import logging

logger = logging.getLogger(__name__)


class InstitutionalSignals:
    """
    Combines on-chain exchange flows (Arkham) and order-book buy/sell
    pressure (Binance) into a score in [-1, +1].

    Weights
    -------
    Exchange flow (Arkham)  60 %
    Order pressure (Binance) 40 %
    """

    WEIGHTS = {"exchange_flow": 0.60, "order_pressure": 0.40}

    def __init__(self, arkham_client, binance_client):
        self.arkham = arkham_client
        self.binance = binance_client

    def compute(self) -> dict:
        sigs = {
            "exchange_flow":   self._exchange_flow(),
            "order_pressure":  self._order_pressure(),
        }

        score = sum(sigs[k] * self.WEIGHTS[k] for k in sigs)

        return {"score": round(score, 4), "signals": sigs}

    # ------------------------------------------------------------------

    def _exchange_flow(self) -> float:
        """
        Net outflow (coins leaving exchanges) → bullish (+)
        Net inflow  (coins entering exchanges) → bearish (-)
        """
        try:
            data = self.arkham.get_exchange_inflows_outflows()
            total = data["inflows"] + data["outflows"]
            if total == 0:
                return 0.0
            # Normalise net_flow to [-1, +1]
            return max(-1.0, min(1.0, data["net_flow"] / total))
        except Exception as e:
            logger.error(f"Exchange flow signal error: {e}")
            return 0.0

    def _order_pressure(self) -> float:
        """
        Recent trade ratio (0 = all sells, 1 = all buys) → mapped to [-1, +1].
        """
        try:
            flows = self.binance.get_exchange_flows()
            # ratio 0.5 → neutral (0), ratio 1.0 → strong buy (+1)
            return round((flows["ratio"] - 0.5) * 2, 4)
        except Exception as e:
            logger.error(f"Order pressure signal error: {e}")
            return 0.0
