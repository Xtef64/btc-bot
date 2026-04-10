import logging

logger = logging.getLogger(__name__)


class SentimentSignals:
    """
    Combines Fear & Greed Index (contrarian) and news sentiment into a
    score in [-1, +1].

    Weights
    -------
    Fear & Greed  70 %
    News          30 %
    """

    WEIGHTS = {"fear_greed": 0.70, "news": 0.30}

    def __init__(self, sentiment_client):
        self.client = sentiment_client

    def compute(self) -> dict:
        fng_data = self.client.get_fear_greed_index()
        news_data = self.client.get_news_sentiment()

        sigs = {
            "fear_greed": self._fear_greed(fng_data["value"]),
            "news":       float(news_data["score"]),
        }

        score = sum(sigs[k] * self.WEIGHTS[k] for k in sigs)

        return {
            "score": round(score, 4),
            "signals": sigs,
            "fear_greed_value": fng_data["value"],
            "fear_greed_label": fng_data["classification"],
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _fear_greed(value: int) -> float:
        """
        Contrarian interpretation:
          Extreme Fear  (<= 20) → strong buy  (+1.0)
          Extreme Greed (>= 80) → strong sell (-1.0)
        """
        if value <= 20:
            return 1.0
        if value <= 30:
            return 0.6
        if value <= 45:
            return 0.2
        if value <= 55:
            return 0.0
        if value <= 70:
            return -0.2
        if value <= 80:
            return -0.6
        return -1.0
