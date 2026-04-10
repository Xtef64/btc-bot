import logging
import ta

logger = logging.getLogger(__name__)


class TechnicalSignals:
    """
    Aggregates five technical indicators into a single score in [-1, +1].

    Weights
    -------
    RSI             25 %
    MACD            25 %
    Bollinger Bands 20 %
    EMA trend       20 %
    Volume          10 %
    """

    WEIGHTS = {
        "rsi": 0.25,
        "macd": 0.25,
        "bollinger": 0.20,
        "ema_trend": 0.20,
        "volume": 0.10,
    }

    def __init__(self, binance_client):
        self.binance = binance_client

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def compute(self) -> dict:
        df = self.binance.get_klines(interval="15m", limit=220)
        if df is None or len(df) < 60:
            logger.warning("Insufficient OHLCV data — returning neutral technical signals")
            return self._neutral()

        sigs = {
            "rsi":       self._rsi(df),
            "macd":      self._macd(df),
            "bollinger": self._bollinger(df),
            "ema_trend": self._ema_trend(df),
            "volume":    self._volume(df),
        }

        score = sum(sigs[k] * self.WEIGHTS[k] for k in sigs)

        rsi_raw = ta.momentum.RSIIndicator(df["close"], window=14).rsi().iloc[-1]

        return {
            "score": round(score, 4),
            "signals": sigs,
            "rsi_value": round(float(rsi_raw), 2),
        }

    # ------------------------------------------------------------------
    # Individual indicators  (each returns float in [-1, +1])
    # ------------------------------------------------------------------

    def _rsi(self, df) -> float:
        try:
            rsi = ta.momentum.RSIIndicator(df["close"], window=14).rsi().iloc[-1]
            if rsi < 25:
                return 1.0
            if rsi < 35:
                return 0.6
            if rsi < 45:
                return 0.2
            if rsi > 75:
                return -1.0
            if rsi > 65:
                return -0.6
            if rsi > 55:
                return -0.2
            return 0.0
        except Exception as e:
            logger.error(f"RSI error: {e}")
            return 0.0

    def _macd(self, df) -> float:
        try:
            macd_obj = ta.trend.MACD(df["close"])
            hist = macd_obj.macd_diff()
            last = hist.iloc[-1]
            prev = hist.iloc[-2]

            # Bullish crossover
            if prev < 0 < last:
                return 1.0
            # Bearish crossover
            if prev > 0 > last:
                return -1.0
            # Trend continuation (clamp)
            return max(-0.5, min(0.5, last / 50.0))
        except Exception as e:
            logger.error(f"MACD error: {e}")
            return 0.0

    def _bollinger(self, df) -> float:
        try:
            bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
            upper = bb.bollinger_hband().iloc[-1]
            lower = bb.bollinger_lband().iloc[-1]
            close = df["close"].iloc[-1]

            band = upper - lower
            if band <= 0:
                return 0.0

            pos = (close - lower) / band  # 0 = at lower, 1 = at upper

            if pos < 0.05:
                return 1.0
            if pos < 0.25:
                return 0.5
            if pos > 0.95:
                return -1.0
            if pos > 0.75:
                return -0.5
            return 0.0
        except Exception as e:
            logger.error(f"Bollinger error: {e}")
            return 0.0

    def _ema_trend(self, df) -> float:
        try:
            ema50 = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator().iloc[-1]
            ema200 = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator().iloc[-1]
            close = df["close"].iloc[-1]

            if ema50 > ema200:
                # Uptrend
                return 0.8 if close > ema50 else 0.3
            else:
                # Downtrend
                return -0.8 if close < ema50 else -0.3
        except Exception as e:
            logger.error(f"EMA trend error: {e}")
            return 0.0

    def _volume(self, df) -> float:
        try:
            avg_vol = df["volume"].rolling(20).mean().iloc[-1]
            last_vol = df["volume"].iloc[-1]
            price_change = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]

            if avg_vol <= 0:
                return 0.0

            ratio = last_vol / avg_vol

            if ratio > 1.5:
                return 0.7 if price_change > 0 else -0.7
            if ratio > 1.0:
                return 0.3 if price_change > 0 else -0.3
            return 0.0   # Low-volume moves carry little weight
        except Exception as e:
            logger.error(f"Volume error: {e}")
            return 0.0

    @staticmethod
    def _neutral() -> dict:
        return {
            "score": 0.0,
            "signals": {"rsi": 0.0, "macd": 0.0, "bollinger": 0.0, "ema_trend": 0.0, "volume": 0.0},
            "rsi_value": 50.0,
        }
