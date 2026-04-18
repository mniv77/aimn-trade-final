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
    return render_or_404("symbol_api_manager.html")

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

# Simple price
@app.route("/api/price")
def api_price():
    sym = (request.args.get("symbol") or "BTCUSD").upper()
    base = {"BTCUSD": 68000, "ETHUSD": 3400, "LTCUSD": 70, "AAPL": 190, "TSLA": 240}.get(sym, 100)
    px = round(base * (1 + random.uniform(-0.002, 0.002)), 2)
    return jsonify({"symbol": sym, "price": px, "ts": int(time.time()*1000)})

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
                   sp.trailing_start, sp.init_profit
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
        trades = db_session.query(Trade).filter(Trade.pnl == None).order_by(Trade.ts.desc()).limit(20).all()
        result = []
        for t in trades:
            result.append({
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "price": t.price,
                "broker": (t.meta or {}).get("exchange", ""),
                "ts": str(t.ts),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify([])

@app.route("/api/ticker")
def api_ticker():
    # some UIs call this instead of /api/price
    sym = (request.args.get("symbol") or "BTCUSD").upper()
    base = {"BTCUSD": 68000, "ETHUSD": 3400, "LTCUSD": 70, "AAPL": 190, "TSLA": 240}.get(sym, 100)
    px = round(base * (1 + random.uniform(-0.003, 0.003)), 2)
    return jsonify({"symbol": sym, "price": px, "bid": px - 0.1, "ask": px + 0.1, "ts": int(time.time()*1000)})

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


# ---- Trade open / close — stores in shared MySQL trades table ----
@app.route("/api/trade/open", methods=["POST"])
def api_trade_open():
    try:
        data = request.get_json(force=True, silent=True) or {}
        symbol   = (data.get("symbol") or "").upper()
        exchange = (data.get("exchange") or data.get("broker") or "UNKNOWN").upper()
        side     = (data.get("side") or "BUY").upper()
        qty      = float(data.get("qty") or 1)

        if not symbol or side not in ("BUY", "SELL"):
            return jsonify({"ok": False, "error": "symbol and side required"}), 400

        # Get a live price (fall back to 0 if unavailable)
        base_prices = {
            "BTCUSD": 68000, "BTC/USD": 68000,
            "ETHUSD": 3400,  "ETH/USD": 3400,
            "LTCUSD": 70,    "AAPL": 190, "TSLA": 240,
        }
        entry_price = base_prices.get(symbol, 100.0)

        trade = Trade(
            symbol=symbol,
            side=side,
            qty=qty,
            price=entry_price,
            meta={"exchange": exchange, "status": "open"},
        )
        db_session.add(trade)
        db_session.commit()

        return jsonify({
            "ok": True,
            "trade_id": trade.id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": entry_price,
            "exchange": exchange,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trade/close", methods=["POST"])
def api_trade_close():
    try:
        data     = request.get_json(force=True, silent=True) or {}
        symbol   = (data.get("symbol") or "").upper()
        pnl      = float(data.get("pnl") or data.get("pnl_pct") or 0)
        reason   = str(data.get("reason") or "")
        trade_id = data.get("trade_id")

        if trade_id:
            trade = db_session.get(Trade, int(trade_id))
        else:
            # Find latest open trade for this symbol
            trade = (
                db_session.query(Trade)
                .filter(Trade.symbol == symbol,
                        Trade.meta["status"].as_string() == "open")
                .order_by(Trade.id.desc())
                .first()
            )

        if trade:
            trade.pnl = pnl
            meta = dict(trade.meta or {})
            meta["status"] = "closed"
            meta["reason"] = reason
            trade.meta = meta
            db_session.commit()

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5080"))
    app.run(host="127.0.0.1", port=port, debug=True)
