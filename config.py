import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Binance ---
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
    BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "false").lower() == "true"

    # --- Trading ---
    TRADING_PAIR = os.getenv("TRADING_PAIR", "BTCUSDT")
    PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
    INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "10000"))
    POSITION_SIZE_PCT = float(os.getenv("POSITION_SIZE_PCT", "0.90"))  # 90% of available cash
    STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.02"))          # 2% stop loss
    TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.04"))      # 4% take profit
    MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", "0.10"))    # 10% max drawdown

    # --- Arkham Intelligence ---
    ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY", "")

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- CryptoPanic (optional news sentiment) ---
    CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")

    # --- Bot behaviour ---
    CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # --- Flask dashboard ---
    PORT = int(os.getenv("PORT", "5000"))
    SECRET_KEY = os.getenv("SECRET_KEY", "btc-bot-secret-key-change-in-prod")

    # --- Data store paths ---
    DATA_DIR = "data_store"
    TRADES_FILE = f"{DATA_DIR}/trades.json"
    POSITIONS_FILE = f"{DATA_DIR}/positions.json"
    PORTFOLIO_FILE = f"{DATA_DIR}/portfolio.json"
