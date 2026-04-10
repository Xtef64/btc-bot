import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

EXCHANGE_TAGS = {"exchange", "cex", "binance", "coinbase", "kraken", "bybit", "okx", "huobi"}


class ArkhamClient:
    BASE_URL = "https://api.arkhamintelligence.com"

    def __init__(self):
        self.api_key = Config.ARKHAM_API_KEY
        self.headers = {"API-Key": self.api_key} if self.api_key else {}

    def _available(self) -> bool:
        if not self.api_key:
            logger.debug("Arkham API key not configured — skipping.")
            return False
        return True

    def get_whale_transfers(self, min_usd: int = 1_000_000, limit: int = 20) -> list:
        """Fetch recent large BTC transfers."""
        if not self._available():
            return []
        try:
            resp = requests.get(
                f"{self.BASE_URL}/transfers",
                headers=self.headers,
                params={"base": "BTC", "usdGte": min_usd, "limit": limit,
                        "sortKey": "time", "sortDir": "desc"},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("transfers", [])
            logger.warning(f"Arkham API returned {resp.status_code}")
            return []
        except Exception as e:
            logger.error(f"Arkham get_whale_transfers error: {e}")
            return []

    def get_exchange_inflows_outflows(self) -> dict:
        """
        Classify large transfers as inflows (→ exchange, bearish) or
        outflows (← exchange, bullish).

        Returns: { inflows, outflows, net_flow, transfers }
        net_flow > 0  →  bullish (coins leaving exchanges)
        net_flow < 0  →  bearish (coins entering exchanges)
        """
        transfers = self.get_whale_transfers()

        inflows = 0.0   # USD value flowing INTO exchanges
        outflows = 0.0  # USD value flowing OUT of exchanges

        for t in transfers:
            amount_usd = float(t.get("unitValue", 0) or 0)
            to_type = str(
                t.get("toAddress", {}).get("arkhamEntity", {}).get("type", "")
            ).lower()
            from_type = str(
                t.get("fromAddress", {}).get("arkhamEntity", {}).get("type", "")
            ).lower()

            to_exchange = any(tag in to_type for tag in EXCHANGE_TAGS)
            from_exchange = any(tag in from_type for tag in EXCHANGE_TAGS)

            if to_exchange and not from_exchange:
                inflows += amount_usd
            elif from_exchange and not to_exchange:
                outflows += amount_usd

        return {
            "inflows": inflows,
            "outflows": outflows,
            "net_flow": outflows - inflows,
            "transfers": transfers,
        }
