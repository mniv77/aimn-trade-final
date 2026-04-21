# app.py  (Flask — pages + rescue API)
from flask import Flask, render_template, redirect, abort, request, jsonify
import os, time, random

from sqlalchemy import text
from shared_models import Base
from app_sub.db import engine, db_session
from shared_models import Base, Trade  # Trade for /api/trade/open





# BEFORE (wrong in your error trail):
# from app_sub.db import engine, db_session

# AFTER (match your file path shown):



app = Flask(__name__, template_folder="templates", static_folder="static")

# Lazy singleton for quote provider (Alpaca → Binance/yfinance → SIM)
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

@aiml.route("/")
def aiml_home():
    return render_or_404("aiml/home.html")

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

# HOME / DASH
@app.route("/")
def home():
    return render_or_404("dashboard.html")

@app.route("/dashboard")
def dashboard():
    return render_or_404("dashboard.html")

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
                   sp.macd_fast, sp.macd_slow, sp.macd_signal
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
                   last_price, peak_profit, status, broker_name, candle_time
            FROM active_trades
            WHERE status = 'OPEN'
            ORDER BY entry_time DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        result = []
        for r in rows:
            # Convert entry_time to Unix timestamp (ms) to avoid timezone issues
            import datetime
            entry_ms = int(r['entry_time'].timestamp() * 1000) if isinstance(r['entry_time'], datetime.datetime) else None
            result.append({
                "id": r['id'], "symbol": r['symbol'],
                "direction": r['direction'],
                "side": "BUY" if r['direction'] == "LONG" else "SELL",
                "entry_price": r['entry_price'], "last_price": r['last_price'],
                "peak_profit": r['peak_profit'], "broker": r['broker_name'],
                "entry_time": entry_ms or str(r['entry_time']),
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

@app.route("/api/scanner/snapshot")
def api_scanner_snapshot():
    global _scanner_snapshot_cache, _scanner_snapshot_ts
    if _scanner_snapshot_cache and time.time() - _scanner_snapshot_ts < 600:
        return jsonify(_scanner_snapshot_cache)

    from db import get_db_connection
    from engine.tuning.candle_fetcher import fetch_candles
    from engine.tuning.auto_tuner import calc_rsi_real, calc_macd_series

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
                    rsi = round(max(0.0, min(100.0, r_val)), 1)
                if closes[-2]:
                    change = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
                atr_vals = [(candles[i]['high'] - candles[i]['low']) / candles[i]['close'] * 100
                            for i in range(-min(14, n), 0)]
                atr_pct = round(sum(atr_vals) / len(atr_vals), 2)
                # MACD
                try:
                    mf = int(row.get('macd_fast') or 12)
                    ms = int(row.get('macd_slow') or 26)
                    mg = int(row.get('macd_signal') or 9)
                    macd_series = calc_macd_series(closes, mf, ms, mg)
                    if macd_series:
                        macd = round(macd_series[-1], 4)
                except Exception:
                    pass
                # Use most recent candle close as price fallback
                if price is None and closes:
                    price = closes[-1]
                    feed = "CANDLE"
        except Exception as e:
            print(f"[snapshot] {symbol}: {e}")

        result.append({'symbol': symbol, 'broker': broker, 'price': price,
                       'rsi': rsi, 'atr_pct': atr_pct, 'change': change,
                       'macd': macd, 'feed': feed})

    _scanner_snapshot_cache = {'symbols': result, 'ts': int(time.time() * 1000)}
    _scanner_snapshot_ts = time.time()
    return jsonify(_scanner_snapshot_cache)

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

        cursor.execute("""
            INSERT INTO active_trades
              (broker_product_id, broker_name, symbol, direction,
               entry_price, entry_time, last_price, status)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s, 'OPEN')
        """, (bp_id, broker, symbol, direction, entry_price, entry_price))
        trade_id = cursor.lastrowid
        conn.close()

        return jsonify({"ok": True, "trade_id": trade_id, "symbol": symbol,
                        "direction": direction, "entry_price": entry_price, "broker": broker})
    except Exception as e:
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

@app.route("/auto_tuner")
def auto_tuner_page():
    return render_template("auto_tuner.html", brokers=[])

@app.route("/tuning_runs")
def tuning_runs_page():
    return render_or_404("tuning_runs.html")


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
            'trail_minus_options': data.get('trail_minus_options', [0.3, 0.5, 0.7]),
            'rsi_exit_options'   : data.get('rsi_exit_options',    [65, 70, 75, 80]),
            'init_profit_options': data.get('init_profit_options', [0.5, 1.0, 1.5, 2.0]),
            'decay_start'        : float(data.get('decay_start', 0.5)),
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


@app.route("/run_all_tuning", methods=["POST"])
def run_all_tuning():
    import threading
    def _run():
        try:
            from engine.tuning.run_tuning_all import run_all
            run_all()
        except Exception as e:
            print(f"[run_all_tuning] Error: {e}")
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "message": "Full tuning run started in background. Check /tuning_runs for progress."})


@app.route("/disable_old_strategies", methods=["POST"])
def disable_old_strategies():
    from db import get_db_connection
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            UPDATE strategy_params
            SET active = 0
            WHERE (last_tuned < '2025-04-08' OR last_tuned IS NULL OR pl_pct < 0)
              AND active = 1
        """)
        affected = cursor.rowcount
        conn.close()
        return jsonify({"status": "success", "message": f"Disabled {affected} old/negative strategies"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5080"))
    app.run(host="127.0.0.1", port=port, debug=True)
