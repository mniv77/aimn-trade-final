# app_min.py
import os, time, json, sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify

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

@app.route("/symbol-api-manager", endpoint="symbol_api_manager")
def symbol_api_manager():
    return render_template("symbol_api_manager.html")

@app.route("/trade-tester", endpoint="trade_tester")
def trade_tester():
    # You confirmed the correct file is trade_tester.html (underscore)
    return render_template("trade_tester.html")

@app.route("/symbols", endpoint="symbols")
def symbols():
    return render_template("symbols.html")
 

@app.route("/simple-explanation", endpoint="simple_explanation")
def simple_explanation():
    # You said this is the right one with capital S + underscore
    return render_template("Simple_Explanation.html")

@app.route("/architectural-analysis", endpoint="architectural_analysis")
def architectural_analysis():
    return render_template("architectural-analysis.html")

@app.route("/architectural-analysis-and-trading-philosophy", endpoint="arch_and_philosophy")
def arch_and_philosophy():
    # This filename includes spaces—must match exactly
    return render_template("Architectural Analysis and Trading Philosophy.html")

@app.route("/scanner-simulator", endpoint="scanner_simulator")
def scanner_simulator():
    return render_template("scanner-simulator.html")

@app.route("/scanner/analysis", endpoint="scanner_analysis")
def scanner_analysis():
    return render_template("scanner-analysis.html")

# --- Orders (placeholder; no DB access yet) ---
@app.route("/orders", endpoint="orders")
def orders():
    return render_template("orders.html")


# --- System Overview / Beginner Guide ---
@app.route("/beginner-guide", endpoint="beginner_guide")
def beginner_guide():
    return render_template("beginner-guide.html")  # file exists

# --- Diagnostics (use the real diagnostics page you prefer) ---
@app.route("/diagnostics", endpoint="diagnostics")
def diagnostics():
    # You said this is the better diagnostics screen
    return render_template("functional_scanner_diagnostics.html")

# --- AI/ML Dashboard Home ---
@app.route("/aiml", endpoint="aiml_home")
def aiml_home():
    return render_template("aiml/home.html")
    
@app.route("/aiml/manual-tune")
def manual_tune():
    return render_template("aiml/manual_tune.html")


# --- Scanner ⇄ Popup Phase-1 Minimal Integration -----------------------------
 

DB_PATH = os.path.join(os.path.dirname(__file__), "popup.sqlite3")
SHARED_API_KEY = os.environ.get("SHARED_API_KEY", "")

def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

def _migrate_sqlite():
    # create table if not exists
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
            status TEXT,                -- OPEN/DONE/CANCELLED
            created_at INTEGER,         -- ms
            opened_at INTEGER,          -- ms
            closed_at INTEGER,          -- ms
            exit_price REAL,
            exit_value REAL,
            pnl_pct REAL,
            pnl_amount REAL,
            reason TEXT,
            snapshot_path TEXT
        )
        """)
        # Add any missing columns idempotently
        def add_col(name, sql_type):
            existing = [r["name"] for r in c.execute("PRAGMA table_info(trade_sessions)")]
            if name not in existing:
                c.execute(f"ALTER TABLE trade_sessions ADD COLUMN {name} {sql_type}")
        # Columns listed in your spec (safe to re-run)
        for nm, tp in [
            ("tenant","TEXT"),
            ("user_id","TEXT"),
            ("signal_id","INTEGER"),
            ("status","TEXT"),
            ("opened_at","INTEGER"),
            ("closed_at","INTEGER"),
            ("exit_price","REAL"),
            ("exit_value","REAL"),
            ("pnl_pct","REAL"),
            ("pnl_amount","REAL"),
            ("reason","TEXT"),
            ("snapshot_path","TEXT")
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
    idem_key = request.headers.get("Idempotency-Key")  # optional

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    # Validate required
    for k in ("symbol","exchange","side","qty","entry_price"):
        if k not in data:
            return jsonify(ok=False, error=f"Missing required field: {k}"), 400

    symbol       = str(data["symbol"]).upper()
    exchange     = str(data["exchange"])
    side         = str(data["side"]).upper()     # BUY/SELL
    qty          = float(data["qty"])
    entry_price  = float(data["entry_price"])
    signal_id    = int(data.get("signal_id") or 0) or None
    params       = data.get("params") or {}
    params_json  = json.dumps(params, separators=(",",":"))

    with _conn() as c:
        # Idempotency: if provided, reuse the first session that matches (signal_id + user_id + symbol + side)
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

        # Create a new session
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
    exit_reason  = str(body["exit_reason"]).upper()     # T/L/R/P
    exit_price   = float(body["exit_price"])
    pnl_pct      = float(body.get("pnl_percentage") or 0.0)
    exit_value   = body.get("exit_value")  # optional from popup
    ts_iso       = body.get("timestamp")
    snapshot     = body.get("snapshot_url")

    closed_at_ms = _now_ms()
    with _conn() as c:
        # compute amount if price & qty known (best-effort)
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

    # In Phase 1 we just acknowledge; Phase 2: also update exchange_states in MySQL
    return jsonify(status="success",
                   message="Trade recorded; (Phase 1) exchange resume handled by scanner internally"), 200
# ----------------------------------------------------------------------------- end

 
if __name__ == "__main__":
    app.run("127.0.0.1", int(os.environ.get("PORT", "5050")), debug=True)
