import requests
import pandas as pd
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import Config

logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


class BinanceClient:
    def __init__(self):
        self.symbol = Config.TRADING_PAIR
        self.client = None
        try:
            self.client = Client(
                Config.BINANCE_API_KEY,
                Config.BINANCE_SECRET_KEY,
                tld="com",
                requests_params={"timeout": 30},
            )
            # Use the global endpoint to bypass geo-restrictions (e.g. Railway US servers)
            self.client.API_URL = "https://api1.binance.com/api"
            logger.info("Binance client initialised (api1.binance.com)")
        except Exception as e:
            logger.error(f"Binance client init error: {e} — price fallback to CoinGecko")

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_klines(self, interval: str = "15m", limit: int = 200) -> pd.DataFrame | None:
        """Return OHLCV DataFrame or None on failure."""
        try:
            klines = self.client.get_klines(
                symbol=self.symbol, interval=interval, limit=limit
            )
            df = pd.DataFrame(
                klines,
                columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "trades",
                    "taker_buy_base", "taker_buy_quote", "ignore",
                ],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ("open", "high", "low", "close", "volume"):
                df[col] = df[col].astype(float)
            return df
        except BinanceAPIException as e:
            logger.error(f"Binance get_klines error: {e}")
            return None

    def get_current_price(self) -> float | None:
        """Return latest BTC price, with CoinGecko as fallback."""
        # Primary: Binance
        if self.client:
            try:
                ticker = self.client.get_symbol_ticker(symbol=self.symbol)
                return float(ticker["price"])
            except Exception as e:
                logger.warning(f"Binance get_price failed: {e} — trying CoinGecko")

        # Fallback: CoinGecko (free, no auth, no geo-restriction)
        return self._coingecko_price()

    def _coingecko_price(self) -> float | None:
        try:
            resp = requests.get(
                COINGECKO_URL,
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            if resp.status_code == 200:
                price = resp.json()["bitcoin"]["usd"]
                logger.info(f"CoinGecko price: ${price:,.2f}")
                return float(price)
        except Exception as e:
            logger.error(f"CoinGecko fallback error: {e}")
        return None

    def get_orderbook(self, limit: int = 20) -> dict | None:
        try:
            return self.client.get_order_book(symbol=self.symbol, limit=limit)
        except BinanceAPIException as e:
            logger.error(f"Binance get_orderbook error: {e}")
            return None

    def get_exchange_flows(self) -> dict:
        """
        Approximate buy/sell pressure from recent trades.
        Returns: { buy_volume, sell_volume, ratio }  (ratio: 0=all sells, 1=all buys)
        """
        try:
            trades = self.client.get_recent_trades(symbol=self.symbol, limit=500)
            df = pd.DataFrame(trades)
            df["price"] = df["price"].astype(float)
            df["qty"] = df["qty"].astype(float)
            df["value"] = df["price"] * df["qty"]

            buys = df[df["isBuyerMaker"] == False]["value"].sum()  # noqa: E712
            sells = df[df["isBuyerMaker"] == True]["value"].sum()   # noqa: E712
            total = buys + sells

            return {
                "buy_volume": buys,
                "sell_volume": sells,
                "ratio": buys / total if total > 0 else 0.5,
            }
        except BinanceAPIException as e:
            logger.error(f"Binance exchange_flows error: {e}")
            return {"buy_volume": 0, "sell_volume": 0, "ratio": 0.5}

    # ------------------------------------------------------------------
    # Account / execution
    # ------------------------------------------------------------------

    def get_account_balance(self) -> dict:
        try:
            account = self.client.get_account()
            balances = {
                b["asset"]: float(b["free"])
                for b in account["balances"]
                if float(b["free"]) > 0
            }
            return {"BTC": balances.get("BTC", 0.0), "USDT": balances.get("USDT", 0.0)}
        except BinanceAPIException as e:
            logger.error(f"Binance get_balance error: {e}")
            return {"BTC": 0.0, "USDT": 0.0}

    def place_market_order(self, side: str, quantity: float) -> dict | None:
        """side: 'BUY' or 'SELL'"""
        try:
            return self.client.create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
            )
        except BinanceAPIException as e:
            logger.error(f"Binance place_order error: {e}")
            return None
