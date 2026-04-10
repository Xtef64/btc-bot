import logging
from flask import Flask, jsonify, render_template
from config import Config

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Shared in-memory store — written by orchestrator, read by API endpoints
_latest_signals: dict = {}


def update_signals(signals: dict):
    """Called by the orchestrator after every trading cycle."""
    global _latest_signals
    _latest_signals = signals


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    from execution.state_manager import StateManager
    state = StateManager()
    return jsonify({
        "portfolio":     state.get_portfolio(),
        "position":      state.get_position(),
        "recent_trades": state.get_trades(limit=10),
        "signals":       _latest_signals,
        "paper_trading": Config.PAPER_TRADING,
    })


@app.route("/api/trades")
def api_trades():
    from execution.state_manager import StateManager
    return jsonify(StateManager().get_trades(limit=100))


@app.route("/api/portfolio")
def api_portfolio():
    from execution.state_manager import StateManager
    return jsonify(StateManager().get_portfolio())


@app.route("/api/signals")
def api_signals():
    return jsonify(_latest_signals)


# ------------------------------------------------------------------
# Entry point for thread
# ------------------------------------------------------------------

def run_dashboard():
    app.run(host="0.0.0.0", port=Config.PORT, debug=False, use_reloader=False)
