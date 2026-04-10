import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Aggregates technical, institutional and sentiment scores into a
    final trading decision: BUY | SELL | HOLD.

    Weights
    -------
    Technical      50 %
    Institutional  25 %
    Sentiment      25 %

    Thresholds
    ----------
    score >= +0.25  → BUY
    score <= -0.25  → SELL
    otherwise       → HOLD
    """

    BUY_THRESHOLD  =  0.25
    SELL_THRESHOLD = -0.25

    WEIGHTS = {
        "technical":     0.50,
        "institutional": 0.25,
        "sentiment":     0.25,
    }

    def __init__(self, technical, institutional, sentiment):
        self.technical     = technical
        self.institutional = institutional
        self.sentiment     = sentiment

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def evaluate(self) -> dict:
        logger.info("Evaluating all signals…")

        tech = self.technical.compute()
        inst = self.institutional.compute()
        sent = self.sentiment.compute()

        score = (
            tech["score"] * self.WEIGHTS["technical"]
            + inst["score"] * self.WEIGHTS["institutional"]
            + sent["score"] * self.WEIGHTS["sentiment"]
        )

        action, confidence = self._decide(score)

        result = {
            "action":          action,
            "confidence":      round(confidence, 4),
            "aggregate_score": round(score, 4),
            "technical":       tech,
            "institutional":   inst,
            "sentiment":       sent,
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Decision: {action} | score={score:+.4f} | confidence={confidence:.1%}"
        )
        return result

    # ------------------------------------------------------------------

    def _decide(self, score: float) -> tuple[str, float]:
        if score >= self.BUY_THRESHOLD:
            span = 1.0 - self.BUY_THRESHOLD
            confidence = min((score - self.BUY_THRESHOLD) / span, 1.0)
            return "BUY", confidence

        if score <= self.SELL_THRESHOLD:
            span = 1.0 - abs(self.SELL_THRESHOLD)
            confidence = min((abs(score) - abs(self.SELL_THRESHOLD)) / span, 1.0)
            return "SELL", confidence

        return "HOLD", 0.0
