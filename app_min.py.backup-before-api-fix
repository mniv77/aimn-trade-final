# app_min.py - Complete with Trading APIs
import os, time, json, sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import random

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
STATIC    = ROOT / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES),
    static_folder=str(STATIC)
)

# --- Health (never touches DB) ---
@app.get("/api/health")
def api_health():
    return jsonify(ok=True)

# --- NEW: Live Price API for popup ---
@app.get("/api/live_price")
def api_live_price():
    """Return mock live price for popup to display"""
    symbol = request.args.get('symbol', 'UNKNOWN')
    exchange = request.args.get('exchange', 'UNKNOWN')
    
    # Mock price generation (replace with real broker API later)
    base_prices = {
        'AAPL': 175.50, 'TSLA': 245.30, 'NVDA': 391.25, 'MSFT': 378.15,
        'BTC/USD': 43250.00, 'ETH/USD': 2280.50, 'SPY': 458.75, 'QQQ': 395.20
    }
    
    base_price = base_prices.get(symbol, 100.0)
    # Add small random variation (+/- 0.5%)
    variation = base_price * (random.random() - 0.5) * 0.01
    current_price = round(base_price + variation, 2)
    
    return jsonify({
        'ok': True,
        'symbol': symbol,
        'exchange': exchange,
        'price': current_price,
        'last': current_price,
        'timestamp': int(time.time() * 1000)
    })

# --- NEW: Trade Open API for popup ---
@app.post("/api/trade/open")
def api_trade_open():
    """Handle trade entry - stores in database and returns entry price"""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400
    
    symbol = data.get('symbol', 'UNKNOWN')
    exchange = data.get('exchange', 'UNKNOWN')
    side = data.get('side', 'BUY')
    qty = data.get('qty', 1)
    
    # Get current price
    base_prices = {
        'AAPL': 175.50, 'TSLA': 245.30, 'NVDA': 391.25, 'MSFT': 378.15,
        'BTC/USD': 43250.00, 'ETH/USD': 2280.50, 'SPY': 458.75, 'QQQ': 395.20
    }
    entry_price = base_prices.get(symbol, 100.0)
    
    # Store trade in database
    try:
        with _conn() as c:
            c.execute("""
                INSERT INTO trade_sessions
                (symbol, exchange, side, qty, entry_price, status, created_at, opened_at)
                VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?)
            """, (symbol, exchange, side, qty, entry_price, _now_ms(), _now_ms()))
    except Exception as e:
        print(f"Database error: {e}")
    
    return jsonify({
        'ok': True,
        'symbol': symbol,
        'exchange': exchange,
        'side': side,
        'qty': qty,
        'entry_price': entry_price,
        'timestamp': int(time.time() * 1000)
    })

# --- UI ROUTES (map to your existing templates; Linux is case-sensitive) ---
@app.route("/", endpoint="index")
def index():
    return render_template("index.html")

@app.route("/tuning", endpoint="tuning")
def tuning():
    return render_template("tuning.html")

@app.route("/scanner", endpoint="scanner")
def scanner():
    return render_template("aimn_flowing_scanner_auto.html")

@app.route("/symbol-api-manager", endpoint="symbol-api-manager")
def symbol_api_manager():
    return render_template("symbol_api_manager.html")

@app.route("/trade-tester", endpoint="trade_tester")
def trade_tester():
    return render_template("trade_tester.html")

# ✅ CRITICAL: Trade Popup Route
@app.route("/trade-popup-fixed", endpoint="trade_popup_fixed")
def trade_popup_fixed():
    """Display the trading popup window with real-time chart and controls"""
    return render_template("trade-popup-fixed.html")

@app.route("/symbols", endpoint="symbols")
def symbols():
    return render_template("symbols.html")

@app.route("/simple-explanation", endpoint="simple_explanation")
def simple_explanation():
    return render_template("Simple_Explanation.html")

@app.route("/architectural-analysis", endpoint="architectural_analysis")
def architectural_analysis():
    return render_template("Architectural Analysis and Trading Philosophy.html")

@app.route("/architectural-analysis", endpoint="arch_and_philosophy")
def arch_and_philosophy():
    return render_template("Architectural Analysis and Trading Philosophy.html")

@app.route("/scanner-simulator", endpoint="scanner_simulator")
def scanner_simulator():
    return render_template("scanner-simulator.html")

@app.route("/scanner_analysis", endpoint="scanner_analysis")
def scanner_analysis():
    return render_template("aimn_diagnostic_scanner.html")

@app.route("/orders", endpoint="orders")
def orders():
    return render_template("orders.html")

@app.route("/beginner-guide", endpoint="beginner_guide")
def beginner_guide():
    return render_template("trading_philosophy.html")

@app.route("/diagnostics", endpoint="diagnostics")
def diagnostics():
    return render_template("functional_scanner_diagnostics.html")

@app.route("/aiml", endpoint="aiml_home")
def aiml_home():
    return render_template("aiml/home.html")

@app.route("/aiml/manual-tune", endpoint="manual_tune")
def manual_tune():
    ctx = {
        "pnl_pct": 0.0,
        "n_trades": 0,
        "win_rate": 0.0,
        "avg_trade_pct": 0.0,
        "max_drawdown": 0.0,
    }
    return render_template("aiml/manual_tune.html", **ctx)

# --- Scanner ⇄ Popup Phase-1 Minimal Integration -----------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "popup.sqlite3")
SHARED_API_KEY = os.environ.get("SHARED_API_KEY", "dev-key-12345")

def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

def _migrate_sqlite():
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS trade_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant TEXT,
            user_id TEXT,
            signal_id INTEGER,
            symbol TEXT,
            exchange TEXT,
            side TEXT,
            qty REAL,
            entry_price REAL,
            params_json TEXT,
            status TEXT,
            created_at INTEGER,
            opened_at INTEGER,
            closed_at INTEGER,
            exit_price REAL,
            exit_value REAL,
            pnl_pct REAL,
            pnl_amount REAL,
            reason TEXT,
            snapshot_path TEXT
        )
        """)
        
        def add_col(name, sql_type):
            existing = [r["name"] for r in c.execute("PRAGMA table_info(trade_sessions)")]
            if name not in existing:
                c.execute(f"ALTER TABLE trade_sessions ADD COLUMN {name} {sql_type}")
        
        for nm, tp in [
            ("tenant","TEXT"), ("user_id","TEXT"), ("signal_id","INTEGER"),
            ("status","TEXT"), ("opened_at","INTEGER"), ("closed_at","INTEGER"),
            ("exit_price","REAL"), ("exit_value","REAL"), ("pnl_pct","REAL"),
            ("pnl_amount","REAL"), ("reason","TEXT"), ("snapshot_path","TEXT")
        ]:
            add_col(nm, tp)
        
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_signal ON trade_sessions(signal_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON trade_sessions(user_id)")

_migrate_sqlite()

def _require_bearer():
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ",1)[1].strip()
    return token and token == SHARED_API_KEY

def _now_ms():
    return int(time.time()*1000)

@app.route("/healthz", endpoint="healthz")
def healthz():
    return {"ok": True}

# --- 3.1 Scanner → Popup: Create trade session -------------------------------
@app.post("/api/trade_sessions")
def api_trade_sessions_create():
    if not _require_bearer():
        return jsonify(ok=False, error="Unauthorized"), 401

    user_id = request.headers.get("X-User-Id") or "default_user"
    tenant = request.headers.get("X-Tenant") or "public"
    idem_key = request.headers.get("Idempotency-Key")

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    for k in ("symbol","exchange","side","qty","entry_price"):
        if k not in data:
            return jsonify(ok=False, error=f"Missing required field: {k}"), 400

    symbol       = str(data["symbol"]).upper()
    exchange     = str(data["exchange"])
    side         = str(data["side"]).upper()
    qty          = float(data["qty"])
    entry_price  = float(data["entry_price"])
    signal_id    = int(data.get("signal_id") or 0) or None
    params       = data.get("params") or {}
    params_json  = json.dumps(params, separators=(",",":"))

    with _conn() as c:
        if idem_key and signal_id:
            row = c.execute("""
              SELECT id FROM trade_sessions
              WHERE signal_id = ? AND user_id = ? AND symbol = ? AND side = ? AND status IS NOT 'CANCELLED'
              ORDER BY id ASC LIMIT 1
            """, (signal_id, user_id, symbol, side)).fetchone()
            if row:
                sid = row["id"]
                popup_url = f"/trade-popup-fixed?symbol={symbol}&exchange={exchange}&side={side}&qty={qty}&sid={sid}&entry={entry_price}"
                return jsonify(ok=True, sid=sid, user_id=user_id, popup_url=popup_url), 200

        c.execute("""
          INSERT INTO trade_sessions
          (tenant,user_id,signal_id,symbol,exchange,side,qty,entry_price,params_json,status,created_at,opened_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (tenant, user_id, signal_id, symbol, exchange, side, qty, entry_price, params_json, "OPEN", _now_ms(), _now_ms()))
        sid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    popup_url = f"/trade-popup-fixed?symbol={symbol}&exchange={exchange}&side={side}&qty={qty}&sid={sid}&entry={entry_price}"
    return jsonify(ok=True, sid=sid, user_id=user_id, popup_url=popup_url), 200

# --- 3.2 Popup → Scanner: Trade completion callback --------------------------
@app.post("/api/trade-completed")
def api_trade_completed():
    if not _require_bearer():
        return jsonify(status="error", error="Unauthorized"), 401

    try:
        body = request.get_json(force=True) or {}
    except Exception:
        return jsonify(status="error", error="Invalid JSON"), 400

    required = ("session_id","symbol","side","exit_reason","exit_price")
    for k in required:
        if k not in body:
            return jsonify(status="error", error=f"Missing field: {k}"), 400

    sid          = int(body["session_id"])
    exit_reason  = str(body["exit_reason"]).upper()
    exit_price   = float(body["exit_price"])
    pnl_pct      = float(body.get("pnl_percentage") or 0.0)
    exit_value   = body.get("exit_value")
    ts_iso       = body.get("timestamp")
    snapshot     = body.get("snapshot_url")

    closed_at_ms = _now_ms()
    with _conn() as c:
        row = c.execute("SELECT qty, entry_price FROM trade_sessions WHERE id = ?", (sid,)).fetchone()
        pnl_amount = None
        if row:
            qty = float(row["qty"])
            entry = float(row["entry_price"])
            pnl_amount = (exit_price - entry) * qty if body.get("side","BUY").upper()=="BUY" else (entry - exit_price) * qty

        c.execute("""
           UPDATE trade_sessions
              SET status='DONE',
                  closed_at=?,
                  exit_price=?,
                  exit_value=?,
                  pnl_pct=?,
                  pnl_amount=?,
                  reason=?,
                  snapshot_path=COALESCE(?, snapshot_path)
            WHERE id=?
        """, (closed_at_ms, exit_price, exit_value, pnl_pct, pnl_amount, exit_reason, snapshot, sid))

    return jsonify(status="success",
                   message="Trade recorded; (Phase 1) exchange resume handled by scanner internally"), 200

if __name__ == "__main__":
    app.run("0.0.0.0", int(os.environ.get("PORT", "5000")), debug=True)