# app.py  (Flask — pages + rescue API)
from flask import Flask, render_template, redirect, abort, request, jsonify
import os, time, random

from sqlalchemy import text
from shared_models import Base
  # you already use Base from app_sub.db in shared_models
from app_sub.db import engine, db_session
from shared_models import Base  # keep Base here ONLY for /api/db/init





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





if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5080"))
    app.run(host="127.0.0.1", port=port, debug=True)
