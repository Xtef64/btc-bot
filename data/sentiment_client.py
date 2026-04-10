import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

FEAR_GREED_URL = "https://api.alternative.me/fng/"
CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"


class SentimentClient:
    def __init__(self):
        self.cryptopanic_key = Config.CRYPTOPANIC_API_KEY

    # ------------------------------------------------------------------
    # Fear & Greed Index  (alternative.me — free, no auth needed)
    # ------------------------------------------------------------------

    def get_fear_greed_index(self) -> dict:
        """
        Returns: { value: int(0-100), classification: str, timestamp: str }
        Falls back to neutral (50) on error.
        """
        try:
            resp = requests.get(
                FEAR_GREED_URL,
                params={"limit": 1, "format": "json"},
                timeout=10,
            )
            if resp.status_code == 200:
                entry = resp.json()["data"][0]
                return {
                    "value": int(entry["value"]),
                    "classification": entry["value_classification"],
                    "timestamp": entry["timestamp"],
                }
        except Exception as e:
            logger.error(f"Fear & Greed fetch error: {e}")

        return {"value": 50, "classification": "Neutral", "timestamp": None}

    # ------------------------------------------------------------------
    # News sentiment  (CryptoPanic — optional, requires API key)
    # ------------------------------------------------------------------

    def get_news_sentiment(self) -> dict:
        """
        Returns: { bullish, bearish, neutral, score: float(-1..+1) }
        """
        if not self.cryptopanic_key:
            return {"bullish": 0, "bearish": 0, "neutral": 0, "score": 0.0}

        try:
            resp = requests.get(
                CRYPTOPANIC_URL,
                params={
                    "auth_token": self.cryptopanic_key,
                    "currencies": "BTC",
                    "filter": "hot",
                    "public": "true",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                bullish = sum(
                    1 for r in results
                    if r.get("votes", {}).get("positive", 0)
                    > r.get("votes", {}).get("negative", 0)
                )
                bearish = sum(
                    1 for r in results
                    if r.get("votes", {}).get("negative", 0)
                    > r.get("votes", {}).get("positive", 0)
                )
                neutral = len(results) - bullish - bearish
                total = len(results) or 1
                return {
                    "bullish": bullish,
                    "bearish": bearish,
                    "neutral": neutral,
                    "score": round((bullish - bearish) / total, 4),
                }
        except Exception as e:
            logger.error(f"CryptoPanic fetch error: {e}")

        return {"bullish": 0, "bearish": 0, "neutral": 0, "score": 0.0}
