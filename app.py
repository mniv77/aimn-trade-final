# app.py (Flask — pages + rescue API)
from flask import Flask, render_template, redirect, abort, request, jsonify
import os, time, random
import sys

# Ensure the project root directory is in the Python path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from sqlalchemy import text
from shared_models import Base, Trade
from app_sub.db import engine, db_session
from engine.tuning.auto_tuner import run_analysis, tune_symbol # KISS V3

# 1. Initialize Flask app ONCE with your settings
app = Flask(__name__, template_folder="templates", static_folder="static")

# 2. Map 'db' to your session (or adjust if your routes expect a cursor-based DB object)
db = db_session

# 3. Register your route blueprints/functions safely after app and db exist
from backtest_routes import register_backtest_routes
register_backtest_routes(app, db)

from backtest_feedback_routes import register_feedback_routes
register_feedback_routes(app, db)

# Lazy singleton for quote provider (Alpaca -> Binance/yfinance -> SIM)
_quote_provider = None
def _get_provider():
    global _quote_provider
    if _quote_provider is None:
        from services.quote_provider import get_provider
        _quote_provider = get_provider()
    return _quote_provider

# Separate public provider for crypto (Binance API) — Alpaca can't fetch crypto prices
_pub_provider = None
def _get_pub_provider():
    global _pub_provider
    if _pub_provider is None:
        from services.quote_provider import PublicQuoteProvider
        _pub_provider = PublicQuoteProvider()
    return _pub_provider

# Scanner snapshot cache (real RSI + ATR from candles, cached 10 min)
_scanner_snapshot_cache = None
_scanner_snapshot_ts = 0.0

from flask import Blueprint
from flask import  url_for

@app.route("/system-overview")
def system_overview():
    return redirect(url_for("aiml.aiml_home"), code=302)

# --- AI/ML blueprint ---
aiml = Blueprint("aiml", __name__, template_folder="templates")


# HOME / DASH
@app.route("/")
def home():
    symbol = request.args.get('symbol', 'BTCUSDT')
    direction = request.args.get('direction', 'LONG')
    return render_template('dashboard.html', symbol=symbol, direction=direction)

@aiml.route("/manual")
def manual_tune():
    # show a simple page now; you can replace with real UI later
    return render_or_404("aiml/manual.html")

@aiml.route("/auto")
def auto_tune():
    return render_or_404("aiml/auto.html")

@aiml.route("/results")
def results():
    return render_or_404("aiml/results.html")

# register the blueprint at /aiml
app.register_blueprint(aiml, url_prefix="/aiml")

# Register the full AI/ML dashboard blueprint (manual-tune, backtest, trades)
try:
    from AImnMLResearch.aiml_dashboard import aiml_bp
    app.register_blueprint(aiml_bp)
except Exception as _aiml_err:
    print(f"[app] aiml_bp not registered: {_aiml_err}")




# -------- helper: render with explicit error if template missing --------
def render_or_404(name: str):
    path = os.path.join(app.template_folder, name)
    if not os.path.exists(path):
        return f"Template not found: {name}  (looked in {path})", 404
    return render_template(name)

# ===================== PAGE ROUTES =====================



@app.route('/dashboard')
def dashboard():
    # Get them from request args or session, with safe fallbacks
    symbol = request.args.get('symbol', 'BTCUSDT')
    direction = request.args.get('direction', 'LONG')
    return render_template('dashboard.html', symbol=symbol, direction=direction)

# TOP MENU TARGETS
@app.route("/scanner")
def scanner_primary():
    return render_or_404("aimn_flowing_scanner_auto.html")

@app.route("/tuning")
def tuning():
    return render_or_404("tuning.html")

@app.route("/orders")
def orders():
    return render_or_404("orders.html")

@app.route("/tuning_ori")
def tuning_ori():
    return render_or_404("tuning_ori.html")

@app.route("/test_scanner")
def test_scanner():
    return render_or_404("test_dashboard.html")

@app.route("/trade-tester")
def trade_tester():
    return render_or_404("trade_tester.html")

@app.route("/symbols")
def symbols():
    return render_or_404("symbols.html")

@app.route("/diagnostics")
def diagnostics():
    # choose your preferred diagnostics landing:
    return render_or_404("functional_scanner_diagnostics.html")
    # alternatives you also have:
    # return render_or_404("scanner-analysis.html")
    # return render_or_404("aimn_scanner_debug.html")
    # return render_or_404("aimn_diagnostic_scanner.html")

# AI/ML home (uses templates/aiml/home.html)
@app.route("/aiml")
def aiml_home():
    return render_or_404("aiml/home.html")

# Optional alias: System Overview points to the same page


# EXTRA / ALIASES
@app.route("/symbol-api-manager")
def symbol_api_manager():
    broker_symbols = {
        'GEMINI':     ['BTC/USD','ETH/USD','SOL/USD','DOGE/USD','LTC/USD','LINK/USD','AVAX/USD','XRP/USD'],
        'COINBASE':   ['BTC/USD','ETH/USD','SOL/USD','DOGE/USD','ADA/USD','DOT/USD','MATIC/USD','XRP/USD'],
        'ALPACA':     ['AAPL','TSLA','NVDA','MSFT','AMZN','GOOGL','META','NFLX','AMD','INTC'],
        'ALPACA-ETF': ['SPY','QQQ','IWM','GLD','TLT','XLF','XLK','ARKK','VTI','VOO'],
        'WEBULL':     ['AAPL','TSLA','NVDA','AMC','GME','PLTR','SOFI','NIO','RIVN','LCID'],
        'FOREX':      ['EUR/USD','GBP/USD','USD/JPY','AUD/USD','USD/CHF','NZD/USD','USD/CAD','EUR/GBP'],
        'FUTURES':    ['GC-GOLD','ES-SPX','CL-OIL','NQ-NDX','YM-DOW','SI-SILVER','ZB-TBOND']
    }
    return render_template("symbol_api_manager.html", broker_symbols=broker_symbols)

@app.route("/api/broker-products", methods=["POST"])
def api_add_broker_product():
    from db import get_db_connection
    data = request.get_json(force=True, silent=True) or {}
    symbol = (data.get("symbol") or "").strip().upper()
    broker_id = data.get("broker_id")
    if not symbol or not broker_id:
        return jsonify({"error": "symbol and broker_id required"}), 400
    try:
        conn, cursor = get_db_connection()
        cursor.execute(
            "INSERT INTO broker_products (broker_id, local_ticker) VALUES (%s, %s)",
            (broker_id, symbol)
        )
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"ok": True, "id": new_id, "symbol": symbol, "broker_id": int(broker_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/broker-products/<int:product_id>", methods=["DELETE"])
def api_delete_broker_product(product_id):
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("DELETE FROM broker_products WHERE id=%s", (product_id,))
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/trade_tester")
def trade_tester_legacy():
    return redirect("/trade-tester", code=302)

@app.route("/scanner/analysis")
def scanner_analysis():
    return render_or_404("scanner-analysis.html")

# POPUPS / FULL
@app.route("/trade-popup")
def trade_popup():
    return render_or_404("aimn_trade_popup.html")

@app.route("/trade-popup-fixed")
def trade_popup_fixed():
    return render_or_404("trade-popup-fixed.html")

@app.route("/trade-full")
def trade_full():
    return render_or_404("trade-full.html")

# ROUTE INSPECTOR (for quick debugging)
@app.route("/routes")
def list_routes():
    lines = []
    for r in app.url_map.iter_rules():
        methods = ",".join(sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS")))
        lines.append(f"{r.rule:35s} -> {r.endpoint} [{methods}]")
    lines.sort()
    return "<pre>" + "\n".join(lines) + "</pre>"


import pandas as pd
import numpy as np




#======================================================
#     SYMBOLS FOR TUNER SELETCT SYAMBOL
#======================================================

from flask import request, jsonify
from sqlalchemy import text

@app.route('/get_symbols', methods=['GET'])
def get_symbols():
    broker_id = request.args.get('broker_id')
    if not broker_id:
        return jsonify([]), 200

    try:
        from app import db
        bid = int(broker_id) if str(broker_id).isdigit() else broker_id

        query = text("SELECT local_ticker AS symbol FROM broker_products WHERE broker_id = :bid")

        try:
            result = db.execute(query, {"bid": bid})
        except Exception as e:
            db.rollback()
            result = db.execute(query, {"bid": bid})
        rows = result.fetchall()
        symbols = [row[0] for row in rows if row[0]]

        print(f"DB QUERY SUCCESS: broker_id={bid} found {len(symbols)} symbols -> {symbols}")
        return jsonify(symbols), 200

    except Exception as e:
        err_msg = str(e)
        print(f"CRITICAL ERROR in /get_symbols: {err_msg}")
        import traceback
        traceback.print_exc()
        return jsonify([f"ERROR: {err_msg[:50]}"]), 200



# ==========================================
# DYNAMIC RISK MANAGEMENT HELPERS
# ==========================================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates the current Average True Range (ATR)."""
    df = df.copy()
    df['high_low'] = df['High'] - df['Low']
    df['high_close'] = (df['High'] - df['Close'].shift()).abs()
    df['low_close'] = (df['Low'] - df['Close'].shift()).abs()

    tr = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    atr = tr.rolling(window=period).mean()
    return float(atr.iloc[-1])

def calculate_dynamic_targets(entry_price: float, atr: float, direction: str,
                               sl_multiplier: float = 1.5,
                               tp1_multiplier: float = 2.0,
                               tp2_multiplier: float = 3.5) -> dict:
    """Computes dynamic Stop Loss and Take Profit levels based on ATR multiples."""
    direction = direction.upper()

    if direction in ['LONG', 'BUY']:
        stop_loss = entry_price - (atr * sl_multiplier)
        take_profit_1 = entry_price + (atr * tp1_multiplier)
        take_profit_2 = entry_price + (atr * tp2_multiplier)
    elif direction in ['SHORT', 'SELL']:
        stop_loss = entry_price + (atr * sl_multiplier)
        take_profit_1 = entry_price - (atr * tp1_multiplier)
        take_profit_2 = entry_price - (atr * tp2_multiplier)
    else:
        raise ValueError("Direction must be 'LONG' or 'SHORT'")

    risk = abs(entry_price - stop_loss)
    reward_tp1 = abs(take_profit_1 - entry_price)
    rr_ratio_tp1 = round(reward_tp1 / risk, 2) if risk > 0 else 0

    return {
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit_1": round(take_profit_1, 2),
        "take_profit_2": round(take_profit_2, 2),
        "risk_amount_pts": round(risk, 2),
        "rr_ratio_tp1": rr_ratio_tp1
    }


# ==========================================
# IMPORTS & FLASK APP INITIALIZATION
# ==========================================
import json
import pandas as pd
import numpy as np



# ==========================================
# 1. ATR & DYNAMIC RISK HELPERS (PASTE HERE)
# ==========================================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates the current Average True Range (ATR) from OHLC data."""
    df = df.copy()
    # Normalize column names to title case
    df.columns = [col.title() for col in df.columns]

    df['prev_close'] = df['Close'].shift(1)
    df['tr1'] = df['High'] - df['Low']
    df['tr2'] = (df['High'] - df['prev_close']).abs()
    df['tr3'] = (df['Low'] - df['prev_close']).abs()

    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=period).mean()

    return float(df['atr'].iloc[-1])


def calculate_dynamic_targets(entry_price: float, atr: float, direction: str,
                               sl_multiplier: float = 1.5,
                               tp1_multiplier: float = 2.0,
                               tp2_multiplier: float = 3.5) -> dict:
    """Computes dynamic Stop Loss and Take Profit levels based on ATR multiples."""
    direction = direction.upper()

    if direction in ['LONG', 'BUY']:
        stop_loss = entry_price - (atr * sl_multiplier)
        take_profit_1 = entry_price + (atr * tp1_multiplier)
        take_profit_2 = entry_price + (atr * tp2_multiplier)
    elif direction in ['SHORT', 'SELL']:
        stop_loss = entry_price + (atr * sl_multiplier)
        take_profit_1 = entry_price - (atr * tp1_multiplier)
        take_profit_2 = entry_price - (atr * tp2_multiplier)
    else:
        raise ValueError("Direction must be 'LONG' or 'SHORT'")

    risk = abs(entry_price - stop_loss)
    reward_tp1 = abs(take_profit_1 - entry_price)
    rr_ratio_tp1 = round(reward_tp1 / risk, 2) if risk > 0 else 0

    return {
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit_1": round(take_profit_1, 2),
        "take_profit_2": round(take_profit_2, 2),
        "risk_amount_pts": round(risk, 2),
        "rr_ratio_tp1": rr_ratio_tp1
    }


# ==========================================
# 2. FLASK ROUTES & TRADE LOGIC (CALL HERE)
# ==========================================

@app.route('/check_trade', methods=['GET', 'POST'])
def check_trade():
    # A. Fetch or parse incoming trade params
    symbol = request.args.get('symbol', 'BTC/USD')
    direction = request.args.get('direction', 'LONG')

    # B. Fetch your historical OHLC DataFrame (Replace with your actual data loader)
    # df = load_ohlc_data(symbol)

    # --- DEMO DATAFRAME FOR EXECUTION ---
    df = pd.DataFrame({
        'High': [63500, 63800, 64100, 64300],
        'Low': [63100, 63300, 63600, 63900],
        'Close': [63400, 63750, 64000, 64250]
    })

    # C. CALL ATR CALCULATION HERE
    current_price = float(df['Close'].iloc[-1])
    current_atr = calculate_atr(df, period=14)

    # D. CALCULATE DYNAMIC SL / TP TARGETS HERE
    targets = calculate_dynamic_targets(
        entry_price=current_price,
        atr=current_atr,
        direction=direction,
        sl_multiplier=1.5, # Risk buffer
        tp1_multiplier=2.0 # Minimum 1.33+ R:R Target
    )

    # E. (Optional) Risk/Reward Gatekeeper
    if targets['rr_ratio_tp1'] < 1.3:
        return jsonify({
            "status": "REJECTED",
            "reason": f"Risk-to-Reward ratio too low ({targets['rr_ratio_tp1']}). Skipping setup."
        })

    # F. Pass calculated targets to template or return JSON
    return render_template(
        'backtest.html',
        symbol=symbol,
        direction=direction,
        targets=targets,
        atr=round(current_atr, 2)
    )


@app.route('/backtest', methods=['GET', 'POST'])
def backtest():
# A. Parse incoming parameters safely
    if request.method == 'POST' and request.is_json:
        data = request.get_json()
        symbol = data.get('symbol', 'BTC/USD')
        direction = str(data.get('direction', 'LONG')).upper()
    else:
        symbol = request.args.get('symbol', 'BTC/USD')
        direction = str(request.args.get('direction', 'LONG')).upper()

    # Ensure direction is strictly LONG or SHORT
    if direction not in ['LONG', 'SHORT']:
        direction = 'LONG'

    # B. Historical OHLC DataFrame
    demo_prices = [62000 + (i * 150) for i in range(20)]
    df = pd.DataFrame({
        'High': [p + 200 for p in demo_prices],
        'Low': [p - 150 for p in demo_prices],
        'Close': demo_prices
    })

    # C. Calculate ATR
    atr_period = 14 if len(df) >= 15 else max(1, len(df) - 1)
    current_price = float(df['Close'].iloc[-1])
    current_atr = calculate_atr(df, period=atr_period)

    # D. Compute Dynamic SL / TP Targets
    targets = calculate_dynamic_targets(
        entry_price=current_price,
        atr=current_atr,
        direction=direction,
        sl_multiplier=1.5,
        tp1_multiplier=2.0,
        tp2_multiplier=3.5
    )

    # E. Risk/Reward Gatekeeper
    gatekeeper_passed = True
    rejection_reason = None
    if targets['rr_ratio_tp1'] < 1.3:
        gatekeeper_passed = False
        rejection_reason = f"Risk-to-Reward ratio too low ({targets['rr_ratio_tp1']}). Skipping setup."

    # F. Render the backtest view
    return render_template(
        'backtest.html',
        symbol=symbol,
        direction=direction,
        targets=targets,
        atr=round(current_atr, 2),
        gatekeeper_passed=gatekeeper_passed,
        rejection_reason=rejection_reason
    )

# ===================== RESCUE API (stubs so UI has data) =====================

@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "ts": int(time.time())})

# Symbols
_SYMBOLS = ["BTCUSD", "ETHUSD", "LTCUSD", "AAPL", "TSLA"]

@app.route("/api/symbols", methods=["GET", "POST"])
def api_symbols():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        sym = (data.get("symbol") or "").strip().upper()
        if sym and sym not in _SYMBOLS:
            _SYMBOLS.append(sym)
        return jsonify({"symbols": _SYMBOLS})
    return jsonify(_SYMBOLS)

@app.route("/api/symbols/<symbol>", methods=["DELETE"])
def api_symbols_delete(symbol):
    s = symbol.strip().upper()
    if s in _SYMBOLS:
        _SYMBOLS.remove(s)
    return jsonify({"symbols": _SYMBOLS})

# Simple price — uses real provider (Binance for crypto, Alpaca/yfinance for stocks)
@app.route("/api/price")
def api_price():
    sym = (request.args.get("symbol") or "BTCUSD").upper()
    exchange = request.args.get("exchange", "").upper()
    try:
        quote = _get_provider().get_price(sym, exchange)
        if quote and quote.price:
            return jsonify({"symbol": sym, "price": quote.price, "ts": quote.ts_ms, "feed": quote.feed})
    except Exception:
        pass
    base = {"BTCUSD": 68000, "ETHUSD": 3400, "LTCUSD": 70, "AAPL": 190, "TSLA": 240}.get(sym, 100)
    return jsonify({"symbol": sym, "price": round(base * (1 + random.uniform(-0.002, 0.002)), 2), "ts": int(time.time()*1000), "feed": "SIM"})

# Orders
@app.route("/api/order", methods=["POST"])
def api_order():
    data = request.get_json(force=True, silent=True) or {}
    order_id = f"SIM-{int(time.time())}-{random.randint(100,999)}"
    return jsonify({"ok": True, "order_id": order_id, "received": data})

@app.route("/api/stop_now", methods=["POST"])
def api_stop_now():
    return jsonify({"ok": True, "action": "STOP_NOW"})

@app.route("/api/panic_close", methods=["POST"])
def api_panic_close():
    return jsonify({"ok": True, "action": "PANIC_CLOSE"})

# Scanner simulate + last
_last_scan = {"ts": int(time.time()*1000), "best": None, "scores": []}

@app.route("/api/scanner/simulate", methods=["POST"])
def api_scanner_sim():
    global _last_scan
    payload = request.get_json(force=True, silent=True) or {}
    symbols = payload.get("symbols") or _SYMBOLS
    scores, best = [], None
    for s in symbols:
        score = int(random.uniform(40, 95))
        scores.append({"symbol": s, "score": score})
        if not best or score > best["score"]:
            best = {"symbol": s, "score": score}
    _last_scan = {"ts": int(time.time()*1000), "best": best, "scores": scores}
    return jsonify(_last_scan)

@app.route("/api/scanner/last")
def api_scanner_last():
    return jsonify(_last_scan or {"ts": int(time.time()*1000), "best": None, "scores": []})

@app.route("/api/scanner/symbols")
def api_scanner_symbols():
    try:
        from db import get_db_connection
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT DISTINCT bp.local_ticker as symbol, b.name as broker
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1
            AND b.name NOT IN ('Futures', 'Forex', 'webull')
            ORDER BY bp.local_ticker
        """)
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"symbols": rows})
    except Exception as e:
        return jsonify({"symbols": [], "error": str(e)}), 500

@app.route("/api/scanner/strategies")
def api_scanner_strategies():
    try:
        from db import get_db_connection
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT bp.local_ticker as symbol, b.name as broker,
                   sp.direction, sp.candle_time,
                   sp.rsi_entry, sp.rsi_exit, sp.stop_loss,
                   sp.trailing_start, sp.trailing_drop, sp.init_profit,
                   sp.decay_start, sp.decay_rate,
                   sp.macd_fast, sp.macd_slow, sp.macd_signal,
                   sp.volume_spike, sp.current_volume, sp.avg_volume
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1
            ORDER BY bp.local_ticker, sp.direction,
                     CASE sp.candle_time WHEN '5m' THEN 1 WHEN '30m' THEN 2 ELSE 3 END
        """)
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"strategies": rows})
    except Exception as e:
        return jsonify({"strategies": [], "error": str(e)}), 500

#======================================================================

@app.route('/finalize_order', methods=['POST'])
def finalize_order():
    """Save completed trade to orders table and clear active_order_id"""
    try:
        data = request.json
        strategy_id = data.get('strategy_id')
        exit_price = data.get('exit_price')
        pnl = data.get('pnl')
        duration = data.get('duration')
        symbol = data.get('symbol')
        broker = data.get('broker')
        direction = data.get('direction')
        candle_time = data.get('candle_time')
        entry_price = data.get('entry_price')

        from db import get_db_connection
        conn, cursor = get_db_connection()
        if isinstance(conn, tuple):
            conn = conn[0]


        if isinstance(conn, tuple):
            conn = conn[0]
#        cursor = conn.cursor()

        # Insert into orders table
        cursor.execute("""
            INSERT INTO orders
            (strategy_id, symbol, broker, side, candle_time,
             entry_price, exit_price, pnl_percent, duration_seconds,
             status, exit_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            strategy_id,
            symbol,
            broker,
            direction,
            candle_time,
            entry_price,
            exit_price,
            pnl,
            duration,
            'CLOSED',
            'PANIC_EXIT'
        ))

        # Clear the active order from strategy
        cursor.execute("""
            UPDATE strategy_params
            SET active_order_id = NULL,
                entry_price = NULL,
                entry_time = NULL,
                cooldown_until = DATE_ADD(NOW(), INTERVAL 2 HOUR)
            WHERE id = %s
        """, (strategy_id,))

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Order saved: {symbol} {direction} | P&L: {pnl}%")
        return jsonify({'success': True})

    except Exception as e:
        print(f"❌ Error finalizing order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

#=================================================================

# Basic strategy/tuning settings
_DEFAULT_SETTINGS = {
    "tp_percent": 5.0, "sl_percent": 2.0,
    "trailing_start_percent": 1.0, "trailing_minus_percent": 0.5,
    "rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9
}


#----- added
# --- DB health + init (temporary) ---

@app.route("/api/db/health")
def api_db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Use ONCE, then comment/remove
@app.route("/api/db/init")
def api_db_init():
    try:
        Base.metadata.create_all(bind=engine)
        return jsonify({"ok": True, "created": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===================== ENTRY POINT =====================
# ---- EXTRA STUBS FOR POPUP/DIAGNOSTICS ----
from flask import request, jsonify
import time, random

@app.route("/api/brokers")
def api_brokers():
    # for dropdowns in popup/UIs
    return jsonify(["Auto", "Alpaca", "Gemini"])

@app.route("/api/position")
def api_position():
    # simulate "no open position"
    return jsonify({"has_position": False, "symbol": None, "side": None, "qty": 0, "avg_price": None})

@app.route("/api/open_orders")
def api_open_orders():
    # empty list is OK; UI should handle it
    return jsonify([])

@app.route("/api/trades/active")
def api_trades_active():
    try:
        from db import get_db_connection
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT id, symbol, direction, entry_price, entry_time,
                   last_price, peak_profit, status, broker_name, candle_time,
                   exit_price, exit_time, exit_reason
            FROM active_trades
            WHERE status = 'OPEN'
               OR (status = 'CLOSED' AND exit_time > DATE_SUB(NOW(), INTERVAL 2 MINUTE))
            ORDER BY entry_time DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        result = []
        for r in rows:
            import datetime
            import time as time_module
            entry_ms = int(r['entry_time'].timestamp() * 1000) if isinstance(r['entry_time'], datetime.datetime) else int(time_module.time() * 1000)
            exit_ms = int(r['exit_time'].timestamp() * 1000) if r.get('exit_time') else None
            result.append({
            "id": r['id'], "symbol": r['symbol'],
            "direction": r['direction'],
            "side": "BUY" if r['direction'] == "LONG" else "SELL",
            "entry_price": r['entry_price'], "last_price": r['last_price'],
            "peak_profit": r['peak_profit'], "broker": r['broker_name'],
            "broker_name": r['broker_name'],
            "entry_time": entry_ms or str(r['entry_time']),
            "status": r['status'],
            "candle_time": r['candle_time'] or "--",
            "exit_price": float(r['exit_price']) if r.get('exit_price') else None,
            "exit_time": exit_ms,
            "exit_reason": r.get('exit_reason') or '',
        })
        return jsonify(result)
    except Exception as e:
        return jsonify([])

@app.route("/api/ticker")
def api_ticker():
    sym = (request.args.get("symbol") or "BTCUSD").upper()
    exchange = request.args.get("exchange", "").upper()
    try:
        quote = _get_provider().get_price(sym, exchange)
        if quote and quote.price:
            px = quote.price
            return jsonify({"symbol": sym, "price": px, "bid": round(px - px*0.0001, 6), "ask": round(px + px*0.0001, 6), "ts": quote.ts_ms, "feed": quote.feed})
    except Exception:
        pass
    base = {"BTCUSD": 68000, "ETHUSD": 3400, "LTCUSD": 70, "AAPL": 190, "TSLA": 240}.get(sym, 100)
    px = round(base * (1 + random.uniform(-0.003, 0.003)), 2)
    return jsonify({"symbol": sym, "price": px, "bid": px - 0.1, "ask": px + 0.1, "ts": int(time.time()*1000), "feed": "SIM"})

@app.route("/api/live_price")
def api_live_price():
    sym = (request.args.get("symbol") or "BTCUSD").upper()
    exchange = request.args.get("exchange", "").upper()
    try:
        quote = _get_provider().get_price(sym, exchange)
        if quote and quote.price:
            return jsonify({"symbol": sym, "price": quote.price, "ts": quote.ts_ms, "feed": quote.feed})
    except Exception:
        pass
    return jsonify({"symbol": sym, "price": None, "ts": int(time.time()*1000), "feed": "SIM"})

@app.route("/api/scanner/prices")
def api_scanner_prices():
    try:
        from db import get_db_connection
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT DISTINCT bp.local_ticker as symbol, b.name as broker
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1
              AND b.name NOT IN ('Forex', 'Futures')
            ORDER BY b.name, bp.local_ticker
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return jsonify({"prices": [], "error": str(e)}), 500

    provider = _get_provider()
    result = []
    for row in rows:
        symbol = row['symbol']
        broker_upper = row['broker'].upper()
        price = None
        feed = "SIM"
        try:
            is_crypto = broker_upper in ("GEMINI", "COINBASE")
            p = _get_pub_provider().get_price(symbol, "CRYPTO") if is_crypto else provider.get_price(symbol, broker_upper)
            if p and p.price:
                price, feed = p.price, p.feed
        except Exception:
            pass
        result.append({"symbol": symbol, "broker": row['broker'], "price": price, "feed": feed})

    return jsonify({"prices": result, "ts": int(time.time()*1000)})

#================================================================================
#                             api_scanner_snapshot
#===============================================================================




@app.route("/api/scanner/snapshot")
def api_scanner_snapshot():
    global _scanner_snapshot_cache, _scanner_snapshot_ts
    if _scanner_snapshot_cache and time.time() - _scanner_snapshot_ts < 600:
        return jsonify(_scanner_snapshot_cache)

    from db import get_db_connection
    from engine.tuning.candle_fetcher import fetch_candles
    # KISS V3 removed RSI/MACD - dummy compat
    calc_rsi_real = lambda x: 50
    calc_macd_series = lambda x: 0

    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT bp.local_ticker as symbol, b.name as broker,
                   sp.rsi_len, sp.candle_time, sp.pl_pct,
                   sp.macd_fast, sp.macd_slow, sp.macd_signal
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1 AND b.name NOT IN ('Forex', 'Futures')
            ORDER BY sp.pl_pct DESC
        """)
        all_rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return jsonify({"symbols": [], "error": str(e)}), 500

    # Best strategy per symbol (already sorted by pl_pct DESC)
    seen, rows = set(), []
    for r in all_rows:
        if r['symbol'] not in seen:
            seen.add(r['symbol'])
            rows.append(r)

    provider = _get_provider()
    result = []
    for row in rows:
        symbol = row['symbol']
        broker = row['broker']
        rsi_len = int(row['rsi_len'] or 20)
        candle_time = row['candle_time'] or '1hr'
        is_crypto = broker.upper() in ("GEMINI", "COINBASE")

        price = rsi = atr_pct = change = macd = None
        feed = "SIM"
        try:
            quote = _get_pub_provider().get_price(symbol, "CRYPTO") if is_crypto else provider.get_price(symbol, broker.upper())
            if quote and quote.price:
                price, feed = quote.price, quote.feed
        except Exception:
            pass

        try:
            candles = fetch_candles(symbol, timeframe=candle_time,
                                    limit=rsi_len + 50, broker=broker)
            if len(candles) > rsi_len + 1:
                # Ensure oldest-first order (Gemini API returns newest-first)
                if candles[0]['timestamp'] > candles[1]['timestamp']:
                    candles = list(reversed(candles))
                highs  = [c['high']  for c in candles]
                lows   = [c['low']   for c in candles]
                closes = [c['close'] for c in candles]
                n = len(closes)
                r_val = calc_rsi_real(highs, lows, closes, n - 1, rsi_len)
                if r_val is not None:
                    rsi = round(r_val, 2)

                # Calculate ATR percentage
                tr_list = []
                for i in range(1, len(closes)):
                    tr = max(
                        highs[i] - lows[i],
                        abs(highs[i] - closes[i - 1]),
                        abs(lows[i] - closes[i - 1])
                    )
                    tr_list.append(tr)
                if tr_list and closes[-1] > 0:
                    avg_tr = sum(tr_list[-14:]) / min(len(tr_list), 14)
                    atr_pct = round((avg_tr / closes[-1]) * 100, 2)

                # Calculate candle change percentage
                if len(closes) >= 2:
                    change = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2)

                # Calculate MACD series
                try:
                    macd_vals = calc_macd_series(closes, int(row['macd_fast'] or 12), int(row['macd_slow'] or 26), int(row['macd_signal'] or 9))
                    if macd_vals and len(macd_vals) > 0:
                        macd = round(macd_vals[-1], 2)
                except Exception:
                    pass

        except Exception as ex:
            print(f"[scanner_snapshot] Error processing {symbol}: {ex}")

        if price is None and 'closes' in locals() and closes:
            price = closes[-1]

        result.append({
            "symbol": symbol,
            "broker": broker,
            "price": price,
            "rsi": rsi,
            "atr_pct": atr_pct,
            "change": change,
            "macd": macd,
            "candle_time": candle_time,
            "pl_pct": row['pl_pct'],
            "feed": feed
        })

    _scanner_snapshot_cache = {"symbols": result, "ts": int(time.time() * 1000)}
    _scanner_snapshot_ts = time.time()
    return jsonify(_scanner_snapshot_cache)


    #============================================================================


def safe_float_list(val, default=None):
    """Safely converts incoming form inputs (strings, lists, or numbers) into a list of floats."""
    if default is None:
        default = [1.5]
    if not val:
        return default
    if isinstance(val, list):
        return [float(x) for x in val if str(x).strip()]
    if isinstance(val, (int, float)):
        return [float(val)]
    if isinstance(val, str):
        val = val.split('DEBUG')[0]
        val = val.replace('[', '').replace(']', '').replace('"', '').replace("'", "")
        res = []
        for x in val.split(','):
            x_clean = x.strip()
            if x_clean:
                try:
                    res.append(float(x_clean))
                except ValueError:
                    pass
        return res if res else default
    return default

def safe_int_list(val, default=None):
    """Safely converts incoming form inputs into a list of integers."""
    if default is None:
        default = [14]
    return [int(x) for x in safe_float_list(val, default)]



#------------------------------------------------------------------------------

def safe_int_list(val, default=[14]):
    """Safely converts incoming form inputs into a list of integers."""
    return [int(x) for x in safe_float_list(val, default)]
@app.route("/api/entry/start", methods=["POST"])
def api_entry_start():
    # used by some popups to kick off an entry
    data = request.get_json(force=True, silent=True) or {}
    order_id = f"SIM-{int(time.time())}-{random.randint(100,999)}"
    return jsonify({"ok": True, "order_id": order_id, "received": data})

@app.route("/api/trade-completed", methods=["POST"])
def api_trade_completed():
    # callback you set in WSGI env; just ack
    payload = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "ack": True, "received": payload})


# ---- Trade open / close — stores in active_trades table ----
@app.route("/api/trade/open", methods=["POST"])
def api_trade_open():
    try:
        data     = request.get_json(force=True, silent=True) or {}
        symbol   = (data.get("symbol") or "").upper()
        broker   = (data.get("exchange") or data.get("broker") or "UNKNOWN")
        side     = (data.get("side") or "BUY").upper()
        qty      = float(data.get("qty") or 1)

        if not symbol or side not in ("BUY", "SELL"):
            return jsonify({"ok": False, "error": "symbol and side required"}), 400

        direction = "LONG" if side == "BUY" else "SHORT"

        # Block crypto manual entries while Gemini is paused
        if broker.upper() in ('GEMINI', 'COINBASE', 'CRYPTO'):
            return jsonify({'ok': False, 'error': 'Crypto trading is currently paused'}), 400

        try:
            exchange = "CRYPTO" if broker.upper() in ("GEMINI", "COINBASE", "CRYPTO") else broker.upper()
            quote = _get_provider().get_price(symbol, exchange)
            entry_price = quote.price if quote and quote.price else float(data.get("price") or 100)
        except Exception:
            entry_price = float(data.get("price") or 100)

        from db import get_db_connection
        conn, cursor = get_db_connection()

        # Block duplicate: same symbol already has an open trade
        cursor.execute("SELECT id FROM active_trades WHERE symbol=%s AND status='OPEN' LIMIT 1", (symbol,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"ok": False, "error": f"{symbol} already has an open trade"}), 409

        bp_id = None
        try:
            cursor.execute("""
                SELECT bp.id FROM broker_products bp
                JOIN brokers b ON bp.broker_id = b.id
                WHERE bp.local_ticker = %s AND b.name = %s LIMIT 1
            """, (symbol, broker))
            row = cursor.fetchone()
            if row:
                bp_id = row['id']
        except Exception:
            pass

        # Fetch strategy params for this symbol/direction
        sp_params = {}
        try:
            cursor.execute("""
                SELECT stop_loss, trailing_start, init_profit, decay_start, decay_rate, rsi_exit
                FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                WHERE bp.local_ticker = %s AND sp.direction = %s AND sp.active = 1
                ORDER BY sp.pl_pct DESC LIMIT 1
            """, (symbol, direction))
            sp_row = cursor.fetchone()
            if sp_row:
                sp_params = sp_row
        except Exception:
            pass

        cursor.execute("""
            INSERT INTO active_trades
              (broker_product_id, broker_name, symbol, direction,
               entry_price, entry_time, last_price, status,
               stop_loss, trailing_start, init_profit, decay_start, decay_rate, rsi_exit)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s, 'OPEN',
                    %s, %s, %s, %s, %s, %s)
        """, (bp_id, broker, symbol, direction, entry_price, entry_price,
                float(sp_params.get('stop_loss') or 0.5),
                float(sp_params.get('trailing_start') or 0.5),
                float(sp_params.get('init_profit') or 1.0),
                float(sp_params.get('decay_start') or 2.0),
                float(sp_params.get('decay_rate') or 0.5),
                float(sp_params.get('rsi_exit') or 65.0)))

        trade_id = cursor.lastrowid

        # UPDATE strategy_params so executor can monitor this trade
        cursor.execute("""
            UPDATE strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            SET sp.active_order_id = %s,
                sp.entry_price = %s,
                sp.entry_time = NOW(),
                sp.peak_profit = -999.00
            WHERE bp.local_ticker = %s
              AND sp.direction = %s
              AND sp.active = 1
            LIMIT 1
        """, (trade_id, entry_price, symbol, direction))

        conn.commit()  # Commit both inserts
        conn.close()

        return jsonify({"ok": True, "trade_id": trade_id, "symbol": symbol,
                        "direction": direction, "entry_price": entry_price, "broker": broker})

    except Exception as e:  # ← REMOVE THE # HERE!
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/trade/close", methods=["POST"])
def api_trade_close():
    try:
        data       = request.get_json(force=True, silent=True) or {}
        symbol     = (data.get("symbol") or "").upper()
        pnl        = float(data.get("pnl") or data.get("pnl_pct") or 0)
        reason     = str(data.get("reason") or "")
        trade_id   = data.get("trade_id")
        exit_price = data.get("exit_price") or None

        from db import get_db_connection
        conn, cursor = get_db_connection()
        if trade_id:
            cursor.execute("""
                UPDATE active_trades
                SET status='CLOSED', exit_price=%s, exit_time=NOW(), exit_reason=%s
                WHERE id=%s
            """, (exit_price, reason, int(trade_id)))
        else:
            cursor.execute("""
                UPDATE active_trades
                SET status='CLOSED', exit_price=%s, exit_time=NOW(), exit_reason=%s
                WHERE symbol=%s AND status='OPEN'
                ORDER BY entry_time DESC LIMIT 1
            """, (exit_price, reason, symbol))
        conn.close()

        return jsonify({"ok": True, "symbol": symbol, "pnl": pnl, "reason": reason})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500





@app.route("/simple-explanation")
def simple_explanation():
    return render_or_404("Simple_Explanation.html")



@app.route("/architectural-analysis")
def architectural_analysis():
    return render_or_404("architectural-analysis.html")  # you have this file

@app.route("/beginner-guide")
def beginner_guide():
    return render_or_404("beginner-guide.html")



@app.route("/architectural-analysis-and-trading-philosophy")  # long name alias
def arch_and_philosophy():
    return render_or_404("Architectural Analysis and Trading Philosophy.html")

# --- SCANNER SIMULATOR (canonical) + aliases ---
@app.route("/scanner-simulator")
def scanner_simulator():
    # show the better diagnostics page instead of the placeholder
    return render_or_404("functional_scanner_diagnostics.html")


@app.route("/scanner/simulator")
def scanner_simulator_alias1():
    # handle older links
    return redirect("/scanner-simulator", code=302)

@app.route("/go/scanner-simulator")
def scanner_simulator_alias2():
    return redirect("/scanner-simulator", code=302)

# --- SETTINGS (your file is singular: setting.html) ---
@app.route("/settings")
def settings():
    return render_or_404("setting.html")





# ===================== AUTO TUNER PAGES =====================

@app.route("/api/ai_vision_check")
def api_ai_vision_check():
    try:
        import os
        from chart_renderer import render_chart
        from code_vision import check_reversal
        os.makedirs("/home/MeirNiv/charts", exist_ok=True)
        # Crypto symbols always
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "LINK/USD"]
        verdicts = []
        for symbol in symbols:
            chart_path = f"/home/MeirNiv/charts/chart_{symbol.replace('/','_')}_5m.png"
            render_chart(symbol, "5m", n_candles=60, outpath=chart_path)
            for direction in ["LONG", "SHORT"]:
                result = check_reversal(chart_path, symbol, direction)
                verdicts.append({
                    "symbol": symbol,
                    "broker": "Gemini",
                    "direction": direction,
                    "verdict": result.get("verdict", "ERROR"),
                    "reason": result.get("reason", "")
                })
        # Alpaca stocks handled by /api/ai_vision_check_stocks endpoint only
        return jsonify({"verdicts": verdicts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai_vision_check_stocks")
def api_ai_vision_check_stocks():
    try:
        import os
        from datetime import datetime
        import pytz
        from chart_renderer import render_chart
        from code_vision import check_reversal
        os.makedirs("/home/MeirNiv/charts", exist_ok=True)
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        market_open = now_et.weekday() < 5 and 570 <= now_et.hour * 60 + now_et.minute < 960
        if not market_open:
            return jsonify({"verdicts": [], "market_open": False})
        alpaca_symbols = ["TSLA", "NVDA", "MSFT", "AAPL", "QQQ", "SPY"]
        verdicts = []
        for symbol in alpaca_symbols:
            chart_path = f"/home/MeirNiv/charts/chart_{symbol}_5m.png"
            render_chart(symbol, "5m", n_candles=60, outpath=chart_path)
            for direction in ["LONG", "SHORT"]:
                result = check_reversal(chart_path, symbol, direction)
                verdicts.append({
                    "symbol": symbol,
                    "broker": "Alpaca",
                    "direction": direction,
                    "verdict": result.get("verdict", "ERROR"),
                    "reason": result.get("reason", "")
                })
        return jsonify({"verdicts": verdicts, "market_open": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/charts/<filename>")
def serve_chart(filename):
    import os
    from flask import send_file
    path = f"/home/MeirNiv/charts/{filename}"
    if os.path.exists(path) and filename.endswith('.png'):
        return send_file(path, mimetype='image/png')
    return "Not found", 404

#from engine.tuning.auto_tuner import run_analysis


#===================================================================
#  auto_tuner   add debug_log
#===================================================================

# DEBUG_TAG_START: Remove after testing
def debug_log(keyword, message):
    print(f"--- [DEBUG_PYTHON_{keyword}] {message} ---")
# DEBUG_TAG_END

from flask import render_template, request, jsonify

@app.route('/auto_tuner', methods=['GET', 'POST'])
def auto_tuner():
    from db import get_db_connection

    # --- HANDLE POST REQUEST (When user clicks Run Auto Tuner) ---
    if request.method == 'POST':
        req_data = request.json or {}

        symbol = req_data.get('symbol')
        broker_id = req_data.get('broker_id')
        direction = req_data.get('direction')
        timeframe = req_data.get('timeframe')
        bars = req_data.get('bars')

        print(f"--- [BACKEND TUNER] Processing -> Symbol: {symbol}, Broker: {broker_id}, Direction: {direction} ---")

        df = fetch_historical_data_for_symbol(broker_id, symbol, timeframe)   #   addition to get real data

        # ⚠️ CRITICAL: Ensure your actual backtest/tuner function
        # uses these variables instead of a hardcoded symbol!
        # Example:
        # results = run_grid_search(broker_id=broker_id, symbol=symbol, direction=direction, timeframe=timeframe, bars=bars)

        # For testing, make sure you return the symbol back in the JSON:
        # return jsonify({
        #     "status": "success",
        #     "symbol": symbol,
        #     "direction": direction,
        #     "timeframe": timeframe,
        #     "candle_count": bars,
        #     "total_pnl_val": ...,
        #     "win_rate_val": ...,
        #     "trades_val": ...,
        #     "avg_pnl_val": ...,
        #     "breakdown": {"DECAY": ..., "RSI": ..., "STOP": ..., "TRAIL": ...},
        #     "params": { ... }
        # })

    # --- HANDLE GET REQUEST (Loads the page and brokers) ---
    brokers = []
    try:
        conn, cursor = get_db_connection()
        cursor.execute("SELECT id, name FROM brokers ORDER BY name")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            if isinstance(row, dict):
                brokers.append({"id": row.get("id"), "name": row.get("name")})
            elif hasattr(row, "keys"):
                brokers.append({"id": row["id"], "name": row["name"]})
            else:
                brokers.append({"id": row[0], "name": row[1]})
    except Exception as e:
        print(f"--- [DEBUG_PYTHON_ERROR] Failed to load brokers: {e} ---")
        brokers = []

    return render_template('auto_tuner.html', brokers=brokers, data={})


#=======================================================================
#          auto_tuning_all
#=============================================================

@app.route('/auto_tuning_all', methods=['GET', 'POST'])
def auto_tuner_all():
    from db import get_db_connection
    try:
        # Add your logic here to trigger or display the full auto tuning run
        payload = request.args.to_dict() or (request.json if request.is_json else {})

        # If you want to render a template or return a response:
        return render_template('run _tuning_all.html')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


#=============================================================
#                         run_tuning_all
#=============================================================
@app.route("/run_tuning_all", methods=["POST"])
def run_tuning_all_action():
    def _run():
        try:
            from engine.tuning.run_tuning_all import run_all
            run_all()
        except Exception as e:
            print(f"[run_all_tuning] Error: {e}")

    # Fire the heavy script in a background thread so it doesn't block the server
    threading.Thread(target=_run, daemon=True).start()

    return jsonify({
        "status": "started",
        "message": "Full tuning run started in background. Check /tuning_runs for progress."
    })

#============================================================================





#=======================================================================
## GLOBAL_PYTHON_DEBUG: Search 'GLOBAL_PYTHON_DEBUG' to remove later
#=============================================================

def pdebug(label, data):
    print(f"--- [DEBUG_LOG | {label}] --- \n{data}\n-----------------------------")



#=======================================================
#document.addEventListener
# ===================== AUTO TUNER APIs =====================

@app.route("/get_brokers_and_symbols")
def get_brokers_and_symbols():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        if not conn:
            return jsonify({"brokers": [], "products": []})
        cursor.execute("SELECT id, name FROM brokers ORDER BY name")
        brokers = cursor.fetchall()
        cursor.execute("""
            SELECT bp.id, bp.broker_id, bp.local_ticker as symbol
            FROM broker_products bp
            ORDER BY bp.local_ticker
        """)
        products = cursor.fetchall()
        conn.close()
        return jsonify({"brokers": brokers, "products": products})
    except Exception as e:
        return jsonify({"brokers": [], "products": [], "error": str(e)})

#====================================================================
#     run_tuning       api/run_tuning'
#====================================================================

@app.route('/run_tuning', methods=['POST'])
@app.route('/api/run_tuning', methods=['POST'])
def run_tuning():
    import traceback
    try:
        data = request.get_json(force=True) or {}
        print(f"[TUNING REQUEST] Received payload: {data}")

        # Call your auto-tuner analysis engine, handling argument signature safety
        from engine.tuning.auto_tuner import run_analysis
        try:
            raw_result = run_analysis(data)
        except TypeError:
            raw_result = run_analysis()

        if not isinstance(raw_result, dict):
            raw_result = {}

        # Map engine results with support for multiple naming conventions
        trades_val = raw_result.get('total_trades', raw_result.get('trades_val', 0))
        win_rate_val = raw_result.get('win_rate', raw_result.get('win_rate_val', 0.0))
        total_pnl_val = raw_result.get('total_pnl', raw_result.get('total_pnl_val', 0.0))
        avg_pnl_val = raw_result.get('avg_pnl', raw_result.get('avg_pnl_val', 0.0))

        breakdown_raw = raw_result.get('breakdown', raw_result.get('exit_breakdown', {}))
        breakdown = {
            "STOP": breakdown_raw.get('STOP', breakdown_raw.get('stop', 0)),
            "TRAIL": breakdown_raw.get('TRAIL', breakdown_raw.get('trail', 0)),
            "DECAY": breakdown_raw.get('DECAY', breakdown_raw.get('decay', 0)),
            "RSI": breakdown_raw.get('RSI', breakdown_raw.get('rsi', 0))
        }

        # from engine.tuning.auto_tuner import run_analysis <- commented
        raw_result = run_analysis(data) # <- NameError

        params_raw = raw_result.get('params', raw_result.get('best_params', {}))
        def clean_opt(val, fallback):
            target = val if val is not None else fallback
            if target is None:
                return ""
            target_str = str(target).strip()
            if ',' in target_str:
                return target_str.split(',')[0].strip()
            return target_str

        params = {
            "rsi_len": clean_opt(params_raw.get('rsi_len'), data.get('rsi_len_options', '14')),
            "rsi_entry": clean_opt(params_raw.get('rsi_entry'), data.get('rsi_entry_options', '30')),
            "stop_loss": clean_opt(params_raw.get('stop_loss'), data.get('stop_loss_options', '1.5')),
            "trail_start": clean_opt(params_raw.get('trail_start'), data.get('trail_start_options', '0')),
            "trail_drop": clean_opt(params_raw.get('trail_drop'), data.get('trail_minus_options', '0')),
            "init_profit": clean_opt(params_raw.get('init_profit'), data.get('init_profit_options', '0')),
            "decay_start": clean_opt(params_raw.get('decay_start'), data.get('decay_start_options', '0'))
        }

        response_data = {
            "status": "success",
            "symbol": data.get('symbol', 'ETHUSD'),
            "direction": data.get('direction', 'LONG'),
            "timeframe": data.get('timeframe', '1hr'),
            "candle_count": data.get('bars', 2016),
            "trades_val": trades_val,
            "win_rate_val": win_rate_val,
            "total_pnl_val": total_pnl_val,
            "avg_pnl_val": avg_pnl_val,
            "params": params,
            "breakdown": breakdown
        }

        return jsonify(response_data), 200

    except Exception as e:
        err_str = traceback.format_exc()
        print(f"[TUNING CRASH TRACE]:\n{err_str}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": err_str
        }, 500)


#============================================================================
#  '/api/tuner_chart/
#==============================================================================================
@app.route('/api/tuner_chart/<symbol>/<direction>/<timeframe>')
def tuner_chart_data(symbol, direction, timeframe):
    try:
        from engine.tuning.auto_tuner import run_analysis
        data = {"symbol": symbol, "direction": direction.upper(), "timeframe": timeframe, "bars": 300}
        result = run_analysis(data)
        candles = result.get("chart_candles", [])
        markers = result.get("markers", [])
        chart_data = [{"time": i, "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"]} for i, c in enumerate(candles)]
        return jsonify({"candles": chart_data, "trades": markers, "stats": {"total_trades": result.get("total_trades",0), "win_rate": result.get("win_rate",0), "total_pnl": result.get("total_pnl",0), "avg_pnl": result.get("avg_pnl",0)}})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/tuner_chart')
def tuner_chart_page():
    return render_template("tuner_chart.html")

#===========================================================================


#============================================================
#    run_auto_tuner
#========================================================



@app.route("/run_auto_tuner", methods=["POST"])
def run_auto_tuner():
    import threading
    data = request.get_json(force=True, silent=True) or {}
    try:
        from db import get_db_connection
        # Resolve strategy_id from symbol_id + direction
        conn, cursor = get_db_connection()
        symbol_id = data.get("symbol_id")
        direction = data.get("direction", "LONG")
        timeframe = data.get("timeframe", "1hr")

        cursor.execute("SELECT local_ticker, broker_id FROM broker_products WHERE id=%s", (symbol_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Symbol not found"}), 400
        symbol = row['local_ticker']
        broker_id = row['broker_id']

        cursor.execute("SELECT name FROM brokers WHERE id=%s", (broker_id,))
        broker_row = cursor.fetchone()
        broker_name = broker_row['name'] if broker_row else "Gemini"

        cursor.execute("""
            SELECT id FROM strategy_params
            WHERE broker_product_id=%s AND direction=%s AND candle_time=%s
            LIMIT 1
        """, (symbol_id, direction, timeframe))
        sp_row = cursor.fetchone()
        if sp_row:
            strategy_id = sp_row['id']
        else:
            cursor.execute("""
                INSERT INTO strategy_params
                    (broker_product_id, direction, candle_time, rsi_len, rsi_entry,
                     stop_loss, trailing_start, trailing_drop, rsi_exit,
                     init_profit, decay_start, decay_rate, active)
                VALUES (%s,%s,%s,100,30,1.0,2.0,0.5,70,1.0,0.5,0.5,1)
            """, (symbol_id, direction, timeframe))
            strategy_id = cursor.lastrowid
        conn.close()

        cfg = {
            'timeframe'          : timeframe,
            'bars'               : int(data.get('bars', 2016)),
            'rsi_len_options'    : data.get('rsi_len_options',     [20, 50, 100, 168, 200]),
            'rsi_entry_options'  : data.get('rsi_entry_options',   [20, 30, 40]),
            'macd_fast'          : int(data.get('macd_fast', 12)),
            'macd_slow'          : int(data.get('macd_slow', 26)),
            'macd_sig'           : int(data.get('macd_sig',  9)),
            'stop_loss_options'  : data.get('stop_loss_options',   [0.3, 0.5, 0.7, 1.0]),
            'trail_start_options': data.get('trail_start_options', [1.0, 2.0, 3.0]),
            'trail_minus_options': data.get('trail_minus_options', [0.5, 1.0, 1.5, 2.0]),
            'rsi_exit_options'   : data.get('rsi_exit_options',    [65, 70, 75, 80]),
            'init_profit_options': data.get('init_profit_options', [0.5, 1.0, 1.5, 2.0]),
            'decay_start_options': data.get('decay_start_options', [0.5, 1.0, 2.0]),
            'decay_rate'         : float(data.get('decay_rate',  0.5)),
            'min_trades'         : int(data.get('min_trades', 5)),
            'score_metric'       : data.get('score_metric', 'total_pnl'),
        }

        from engine.tuning.auto_tuner import tune_strategy
        result = tune_strategy(strategy_id, symbol, direction, cfg=cfg, broker_name=broker_name)

        if not result:
            return jsonify({"error": "No valid combinations found — try fewer filters or more bars"})
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/disable_old_strategies", methods=["POST"])
def disable_old_strategies():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            UPDATE strategy_params
            SET active = 0
            WHERE (last_tuned < DATE_SUB(NOW(), INTERVAL 7 DAY) OR last_tuned IS NULL OR pl_pct < 0)
              AND active = 1
        """)
        affected = cursor.rowcount
        conn.close()
        return jsonify({"status": "success", "message": f"Disabled {affected} old/negative strategies"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
#   /tuning_runs page route
# ============================================================

@app.route('/tuning_runs')
def tuning_runs_page():
    from db import get_db_connection
    runs = []
    try:
        conn, cursor = get_db_connection()
        # Fetch the latest tuning runs from your database table
        cursor.execute("SELECT * FROM tuning_runs ORDER BY id DESC LIMIT 50")
        runs = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"[tuning_runs_page] Error: {e}")
        runs = []

    return render_template('tuning_runs.html', runs=runs)






#====================================================================================
#/api/tuning_runs
#======================================================================


@app.route("/api/tuning_runs")
def api_tuning_runs():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT id, started_at, finished_at, status, summary
            FROM tuning_runs ORDER BY id DESC LIMIT 50
        """)
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            if r.get('started_at'):
                r['started_at'] = str(r['started_at'])
            if r.get('finished_at'):
                r['finished_at'] = str(r['finished_at'])
        return jsonify(rows)
    except Exception as e:
        return jsonify([])


@app.route("/api/tuning_runs/cleanup", methods=["POST"])
def api_tuning_runs_cleanup():
    """Mark any run stuck in 'running' status for >2 hours as 'failed'."""
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            UPDATE tuning_runs
            SET status='failed', finished_at=NOW(),
                summary=CONCAT(IFNULL(summary,''), ' [auto-cancelled: stuck]')
            WHERE status='running'
              AND started_at < DATE_SUB(NOW(), INTERVAL 2 HOUR)
        """)
        affected = cursor.rowcount
        conn.close()
        return jsonify({"ok": True, "cancelled": affected})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/tuning_runs/<int:run_id>")
def api_tuning_run_detail(run_id):
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("SELECT * FROM tuning_runs WHERE id=%s", (run_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row.get('started_at'):
            row['started_at'] = str(row['started_at'])
        if row.get('finished_at'):
            row['finished_at'] = str(row['finished_at'])
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/performance")
def api_performance():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT bp.local_ticker as symbol, b.name as broker,
                   sp.direction, sp.candle_time,
                   COALESCE(sp.pl_pct, 0) as pl_pct,
                   sp.rsi_len, sp.rsi_entry, sp.stop_loss,
                   sp.trailing_start, sp.init_profit,
                   sp.last_tuned
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1
            ORDER BY sp.pl_pct DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            if r.get('last_tuned'):
                r['last_tuned'] = str(r['last_tuned'])
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e), "rows": []}), 500


# Also create tuning DB tables on /api/db/init
_TUNING_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS tuning_runs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        started_at DATETIME, finished_at DATETIME,
        status VARCHAR(16) DEFAULT 'running',
        summary TEXT, log_text LONGTEXT
    )""",
    """CREATE TABLE IF NOT EXISTS tuning_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        strategy_id INT, rsi_len INT, rsi_entry FLOAT,
        stop_loss FLOAT, trailing_start FLOAT, trailing_drop FLOAT,
        winrate FLOAT, avg_pnl FLOAT, pl_pct FLOAT,
        trades_tested INT, tuned_at DATETIME
    )""",
]

_orig_db_init = app.view_functions.get('api_db_init')

@app.route("/api/db/init/tuning")
def api_db_init_tuning():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        for sql in _TUNING_TABLES_SQL:
            cursor.execute(sql)
        conn.close()
        return jsonify({"ok": True, "tables": ["tuning_runs", "tuning_history"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500




#=========================================================================
#      /api/symbol_trades/<symbol>      api/save_trade_feedback
#==============================================================================

@app.route('/api/symbol_trades/<symbol>', methods=['GET'])
@app.route('/api/symbol_trades/<symbol>', methods=['GET'])
def get_symbol_trades(symbol):
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("SELECT id, symbol, direction, pnl_percent as pnl_pct FROM active_trades WHERE symbol LIKE %s ORDER BY id DESC LIMIT 100", (f"%{symbol}%",))
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            if 'pnl_pct' in r and r['pnl_pct'] is not None:
                r['pnl_pct'] = float(r['pnl_pct'])
        return jsonify({
            "status": "success",
            "trades": rows
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
@app.route('/api/save_trade_feedback', methods=['POST'])
def save_trade_feedback():
    data = request.json or {}
    trade_id = data.get('trade_id')
    feedback_text = data.get('feedback')
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            UPDATE backtest_orders SET feedback = %s WHERE id = %s
        """, (feedback_text, trade_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

#--------------------------------------------------------------------------





@app.route("/api/db/seed-brokers", methods=["POST"])
def seed_brokers():
    """Ensure Forex and Futures brokers exist in brokers table."""
    try:
        from db import get_db_connection
        conn, cursor = get_db_connection()
        for name in ("Forex", "Futures"):
            cursor.execute("SELECT id FROM brokers WHERE name = %s", (name,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO brokers (name) VALUES (%s)", (name,))
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/broker")
def broker_settings():
    from db import get_db_connection
    from flask import flash
    conn, cursor = get_db_connection()
    cursor.execute("SELECT id, name, api_key FROM brokers ORDER BY id")
    brokers = cursor.fetchall()
    conn.close()
    return render_template("brokers.html", brokers=brokers)

@app.route("/add_broker", methods=["POST"])
def add_broker():
    from db import get_db_connection
    from flask import flash
    action = request.form.get("action_type")
    conn, cursor = get_db_connection()
    if action == "register_broker":
        name = request.form.get("name", "").strip()
        if name:
            cursor.execute("INSERT IGNORE INTO brokers (name) VALUES (%s)", (name,))
    elif action == "update_keys":
        broker_id = request.form.get("broker_id")
        api_key = request.form.get("api_key", "").strip()
        api_secret = request.form.get("api_secret", "").strip()
        cursor.execute(
            "UPDATE brokers SET api_key=%s, api_secret=%s WHERE id=%s",
            (api_key, api_secret, broker_id)
        )
    conn.close()
    flash("Saved successfully")
    return redirect(url_for("broker_settings"))

@app.route("/delete_broker/<int:id>", methods=["POST"])
def delete_broker(id):
    from db import get_db_connection
    conn, cursor = get_db_connection()
    cursor.execute("DELETE FROM brokers WHERE id=%s", (id,))
    conn.close()
    return redirect(url_for("broker_settings"))



@app.route("/api/orders/summary")
def api_orders_summary():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT symbol, side, pnl_percent, exit_reason,
                   duration_seconds, created_at, broker
            FROM orders
            WHERE status = 'CLOSED'
            ORDER BY created_at DESC
            LIMIT 200
        """)
        trades = cursor.fetchall()
        conn.close()
        for t in trades:
            if t.get('created_at'):
                t['created_at'] = str(t['created_at'])
            if t.get('pnl_percent'):
                t['pnl_percent'] = float(t['pnl_percent'])
        return jsonify({"trades": trades, "count": len(trades)})
    except Exception as e:
        return jsonify({"trades": [], "error": str(e)}), 500

@app.route("/backtest-vs-live")
def backtest_vs_live():
    return render_or_404("backtest_vs_live.html")




@app.route("/api/active_symbols", methods=["GET"])
def api_active_symbols():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT bp.local_ticker as symbol, b.name as broker,
                   GROUP_CONCAT(DISTINCT sp.candle_time ORDER BY sp.candle_time) as candle_times,
                   GROUP_CONCAT(DISTINCT sp.direction ORDER BY sp.direction) as directions
            FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            JOIN strategy_params sp ON sp.broker_product_id = bp.id
            WHERE bp.is_active = 1 AND sp.active = 1
            GROUP BY bp.local_ticker, b.name
            ORDER BY b.name, bp.local_ticker
        """)
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"ok": True, "symbols": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/manual_tune/load", methods=["GET"])
def api_manual_tune_load():
    from db import get_db_connection
    try:
        symbol      = request.args.get('symbol', '').upper()
        direction   = request.args.get('direction', 'LONG').upper()
        candle_time = request.args.get('candle_time', '')
        conn, cursor = get_db_connection()
        params = [symbol, direction]
        sql = """
            SELECT sp.rsi_len, sp.rsi_entry, sp.rsi_exit,
                   sp.stop_loss, sp.trailing_start, sp.trailing_drop,
                   sp.init_profit, sp.macd_fast, sp.macd_slow, sp.macd_sig,
                   sp.decay_start, sp.decay_rate, sp.candle_time,
                   sp.pl_pct, sp.last_tuned
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            WHERE bp.local_ticker = %s AND sp.direction = %s"""
        if candle_time:
            sql += " AND sp.candle_time = %s"
            params.append(candle_time)
        sql += " ORDER BY sp.last_tuned DESC LIMIT 1"
        cursor.execute(sql, params)
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({"ok": False, "error": f"No params found for {symbol} {direction}"}), 404
        return jsonify({"ok": True, "data": {
            "rsi_window"           : row["rsi_len"],
            "oversold_level"       : float(row["rsi_entry"]),
            "overbought_level"     : float(row["rsi_entry"]),
            "rsi_exit"             : float(row["rsi_exit"]),
            "stop_loss"            : float(row["stop_loss"]),
            "early_start"          : float(row["trailing_start"]),
            "early_minus"          : float(row["trailing_drop"]),
            "rsi_profit"           : float(row["init_profit"]),
            "macd_fast"            : row["macd_fast"],
            "macd_slow"            : row["macd_slow"],
            "macd_signal"          : row["macd_sig"],
            "decay_start"          : float(row["decay_start"]),
            "decay_rate"           : float(row["decay_rate"]),
            "candle_time"          : row["candle_time"],
            "pl_pct"               : float(row["pl_pct"] or 0),
            "last_tuned"           : str(row["last_tuned"]) if row["last_tuned"] else None
        }})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/manual_tune/save", methods=["POST"])
def api_manual_tune_save():
    from db import get_db_connection
    try:
        data = request.get_json(force=True, silent=True) or {}
        symbol_raw = data.get('symbol','')
        trade_mode = data.get('trade_mode','BUY').upper()
        direction  = 'LONG' if trade_mode == 'BUY' else 'SHORT'
        symbol     = symbol_raw.split('_')[0].upper()

        def combine(a, b):
            try: return float(data.get(a,0)) + float(data.get(b,0))
            except: return 0.0

        rsi_len     = int(float(data.get('rsi_window', 100)))
        rsi_entry   = combine('oversold_level_int','oversold_level_dec') if direction=='LONG' else combine('overbought_level_int','overbought_level_dec')
        rsi_exit    = combine('rsi_exit_buy_int','rsi_exit_buy_dec') if direction=='LONG' else combine('rsi_exit_sell_int','rsi_exit_sell_dec')
        stop_loss   = combine('stop_loss_int','stop_loss_dec')
        trail_start = combine('early_start_int','early_start_dec')
        trail_drop  = combine('early_minus_int','early_minus_dec')
        init_profit = combine('rsi_profit_int','rsi_profit_dec')
        macd_fast   = int(float(data.get('macd_fast', 12)))
        macd_slow   = int(float(data.get('macd_slow', 26)))
        macd_sig    = int(float(data.get('macd_signal', 9)))

        conn, cursor = get_db_connection()
        cursor.execute("""
            SELECT bp.id FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            WHERE bp.local_ticker = %s LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": f"Symbol {symbol} not found"}), 404

        bp_id = row['id']
        cursor.execute("""
            SELECT id FROM strategy_params
            WHERE broker_product_id=%s AND direction=%s LIMIT 1
        """, (bp_id, direction))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE strategy_params SET
                    rsi_len=%s, rsi_entry=%s, rsi_exit=%s,
                    stop_loss=%s, trailing_start=%s, trailing_drop=%s,
                    init_profit=%s, macd_fast=%s, macd_slow=%s, macd_sig=%s,
                    active=1, last_tuned=NOW()
                WHERE id=%s
            """, (rsi_len, rsi_entry, rsi_exit, stop_loss, trail_start,
                  trail_drop, init_profit, macd_fast, macd_slow, macd_sig, existing['id']))
            msg = f"Updated {symbol} {direction}"
        else:
            cursor.execute("""
                INSERT INTO strategy_params
                    (broker_product_id, direction, rsi_len, rsi_entry, rsi_exit,
                     stop_loss, trailing_start, trailing_drop, init_profit,
                     macd_fast, macd_slow, macd_sig, active, last_tuned)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,NOW())
            """, (bp_id, direction, rsi_len, rsi_entry, rsi_exit, stop_loss,
                  trail_start, trail_drop, init_profit, macd_fast, macd_slow, macd_sig))
            msg = f"Created {symbol} {direction}"

        conn.close()
        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/crypto/status")
def api_crypto_status():
    from db import get_db_connection
    conn, cursor = get_db_connection()
    cursor.execute("SELECT COUNT(*) as active FROM strategy_params sp JOIN broker_products bp ON sp.broker_product_id=bp.id JOIN brokers b ON bp.broker_id=b.id WHERE b.name='Gemini' AND sp.active=1")
    row = cursor.fetchone()
    conn.close()
    return jsonify({"active": row["active"]})

@app.route("/api/crypto/active", methods=["POST"])
def api_crypto_active():
    data = request.get_json() or {}
    val = int(data.get("active", 0))
    from db import get_db_connection
    conn, cursor = get_db_connection()
    cursor.execute("UPDATE strategy_params sp JOIN broker_products bp ON sp.broker_product_id=bp.id JOIN brokers b ON bp.broker_id=b.id SET sp.active=%s WHERE b.name='Gemini'", (val,))
    cursor.execute("UPDATE brokers SET trading_enabled=%s WHERE name='Gemini'", (val,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "Crypto ENABLED" if val else "Crypto PAUSED"})

# --- KISS V3 DOC ROUTE - ONE STRATEGY ---
@app.route("/docs/strategy")
def docs_strategy():
    import pathlib, markdown
    md_file = pathlib.Path("doc/strategy/AiMn-KISS-Strategy-V3-full.md")
    if not md_file.exists():
        md_file = pathlib.Path("doc/strategy/AiMn-KISS-Strategy-V3.md")
    if md_file.exists():
        md_text = md_file.read_text(encoding="utf-8", errors="ignore")
        html_body = markdown.markdown(md_text, extensions=["fenced_code","tables","toc","nl2br"])
    else:
        html_body = "<p>Doc missing</p>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>KISS V3</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:900px;margin:0 auto;padding:24px;line-height:1.7;background:#fff;color:#111}}
.btn{{display:inline-block;background:#0a84ff;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;margin:5px;font-weight:600}}
.btn-dark{{background:#111}}
h1{{font-size:28px;border-bottom:2px solid #eee;padding-bottom:8px}}
h2{{color:#0a84ff;margin-top:30px;border-bottom:1px solid #eee;padding-bottom:6px}}
h3{{color:#333}}
pre{{background:#f6f8fa;padding:16px;border-radius:8px;overflow:auto}}
code{{background:#f0f0f0;padding:2px 6px;border-radius:4px}}
table{{border-collapse:collapse;width:100%;margin:16px 0}} th,td{{border:1px solid #ddd;padding:8px;text-align:left}} th{{background:#f5f5f5}}
.header{{position:sticky;top:0;background:rgba(255,255,255,.9);backdrop-filter:blur(10px);padding:12px 0;border-bottom:1px solid #eee;margin-bottom:20px;z-index:10}}
</style></head><body>
<div class="header"><a class="btn" href="/">← Dashboard</a> <a class="btn btn-dark" href="/doc/strategy/AiMn-KISS-Strategy-V3-full.md" download>⬇ Download MD</a> <a class="btn btn-dark" style="background:#111" href="/doc/strategy/AiMn_KISS_V3_Holy_Bible.pdf" download>📖 Holy Bible PDF</a></div>
<h1>📘 AiMn KISS V3 Strategy</h1>
{html_body}
</body></html>"""

@app.route("/doc/strategy/<path:filename>")
def serve_strategy_doc(filename):
    from flask import send_from_directory
    import pathlib
    folder = pathlib.Path("doc/strategy").resolve()
    return send_from_directory(str(folder), filename, as_attachment=False)
#=================================================================



@app.route('/tradingview_chart.html')
def tradingview_chart():
    trade_id = request.args.get('trade_id', 1)
    return render_template('trade_chart.html', trade_id=trade_id)


@app.teardown_appcontext
def shutdown_session(exception=None):
    try:
        db.remove()
    except Exception:
        try:
            db.rollback()
            db.remove()
        except Exception:
            pass