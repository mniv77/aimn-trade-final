# =====================
# /app/views.py  (FULL)
# =====================
from flask import Blueprint, render_template_string, request, redirect, url_for, jsonify, send_from_directory
from .db import db_session
from .models import StrategyParam, UiEvent, Trade
from .services.settings import SettingsService
from .security import upsert_alpaca_keys
from .market_data import fetch_bars
import os

ui_bp = Blueprint("ui", __name__)
api_bp = Blueprint("api", __name__)

from flask import Blueprint, render_template_string, request, redirect, url_for, jsonify

PARAM_FIELDS = [
    "mode","rsi_period","rsi_buy_whole","rsi_buy_decimal","rsi_sell_whole","rsi_sell_decimal",
    "macd_fast","macd_slow","macd_signal","vol_window",
    "weight_rsi","weight_macd","weight_vol","entry_threshold",
    "trailing_pct_primary_whole","trailing_pct_primary_decimal",
    "trailing_pct_secondary_whole","trailing_pct_secondary_decimal",
    "trailing_start_whole","trailing_start_decimal",
    "stop_loss_whole","stop_loss_decimal",
    "rsi_exit_whole","rsi_exit_decimal",
    "position_size_usd",
]

PARAM_SPEC = [
  ("mode","Mode","select",None,None,None),
  ("rsi_period","RSI Period","number",2,100,1),
  ("rsi_buy_whole","RSI Buy Whole","number",0,100,1),
  ("rsi_buy_decimal","RSI Buy Dec","number",0,99,1),
  ("rsi_sell_whole","RSI Sell Whole","number",0,100,1),
  ("rsi_sell_decimal","RSI Sell Dec","number",0,99,1),
  ("macd_fast","MACD Fast","number",2,50,1),
  ("macd_slow","MACD Slow","number",5,100,1),
  ("macd_signal","MACD Signal","number",2,50,1),
  ("vol_window","Volume Window","number",2,200,1),
  ("weight_rsi","Weight RSI","number",0.0,1.0,0.05),
  ("weight_macd","Weight MACD","number",0.0,1.0,0.05),
  ("weight_vol","Weight Vol","number",0.0,1.0,0.05),
  ("entry_threshold","Entry Threshold","number",0.0,2.0,0.01),
  ("trailing_pct_primary_whole","Trail#1 % Whole","number",0,50,1),
  ("trailing_pct_primary_decimal","Trail#1 % Dec","number",0,99,1),
  ("trailing_pct_secondary_whole","Trail#2 % Whole","number",0,50,1),
  ("trailing_pct_secondary_decimal","Trail#2 % Dec","number",0,99,1),
  ("trailing_start_whole","Trail Start % Whole","number",0,50,1),
  ("trailing_start_decimal","Trail Start % Dec","number",0,99,1),
  ("stop_loss_whole","Stop Loss % Whole","number",0,50,1),
  ("stop_loss_decimal","Stop Loss % Dec","number",0,99,1),
  ("rsi_exit_whole","RSI Exit Whole","number",0,100,1),
  ("rsi_exit_decimal","RSI Exit Dec","number",0,99,1),
  ("position_size_usd","Pos Size (USD)","number",1,100000,1),
]

SNAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "snapshots"))
os.makedirs(SNAP_DIR, exist_ok=True)

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <title>AIMn Dashboard</title>
  <style>
    body { font-family: sans-serif; }
    table{border-collapse:collapse}td,th{border:1px solid #888;padding:6px}
    input[type=number]{width:7em} select{width:7em}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}
    .card{border:1px solid #bbb;padding:12px;border-radius:8px}
    .nav a{margin-right:12px}
  </style>
  <script>
    let lastTradeId = 0;
    function selectAll(cls){ document.querySelectorAll('.'+cls).forEach(cb=>{ if(!cb.disabled) cb.checked=true; }); }
    function clearAll(cls){ document.querySelectorAll('.'+cls).forEach(cb=>cb.checked=false); }
    async function pollTrades(){
      try{
        const r = await fetch('/api/events/latest_trade');
        const j = await r.json();
        if (j && j.id && j.id > lastTradeId){
          lastTradeId = j.id;
          window.open('/trade/'+j.id, '_blank'); // why: pop chart window on new trade
        }
      }catch(e){}
      setTimeout(pollTrades, 5000);
    }
    window.addEventListener('load', pollTrades);
  </script>
</head>
<body>
  <div class="nav">
    <a href="/">Dashboard</a>
    <a href="/orders">Orders Log</a>
  </div>
  <h2>AIMn — TV-style Tuning</h2>
  <p>Status: {{ 'ENABLED' if rt.bot_enabled else 'DISABLED' }} | Mode: {{ rt.mode }} | Heartbeat: {{ rt.last_heartbeat }}</p>
  <form method="post" action="{{ url_for('api.toggle') }}"><button>Toggle Bot</button></form>

  <div class="grid">
    <div class="card">
      <h3>Profile Editor</h3>
      <form method="get" action="{{ url_for('ui.index') }}">
        Symbol <input name="symbol" value="{{symbol}}" size="10"/>
        TF <input name="tf" value="{{tf}}" size="6"/>
        <button>Load</button>
      </form>
      {% if sp %}
      <h4>{{sp.symbol}} — {{sp.timeframe}}</h4>
      <form method="post" action="{{ url_for('api.save_params') }}">
        <input type="hidden" name="id" value="{{sp.id}}"/>
        <table>
          {% for f,l,t,minv,maxv,step in spec %}
          <tr><td>{{l}}</td><td>
            {% if t=='select' %}
              <select name="{{f}}">
                <option value="BUY" {{'selected' if sp.mode=='BUY' else ''}}>BUY</option>
                <option value="SELL" {{'selected' if sp.mode=='SELL' else ''}}>SELL</option>
              </select>
            {% else %}
              <input type="number" name="{{f}}" value="{{getattr(sp,f)}}"
                {% if minv!=None %}min="{{minv}}"{% endif %}
                {% if maxv!=None %}max="{{maxv}}"{% endif %}
                {% if step!=None %}step="{{step}}"{% endif %}/>
            {% endif %}
          </td></tr>
          {% endfor %}
        </table>
        <button>Save</button>
      </form>
      {% else %}
      <p>No profile found. Create one:</p>
      <form method="post" action="{{ url_for('api.create_profile') }}">
        Symbol <input name="symbol" value="{{symbol}}" required size="10"/>
        TF <input name="timeframe" value="{{tf}}" required size="6"/>
        <button>Create</button>
      </form>
      {% endif %}
    </div>

    <div class="card">
      <h3>Bulk Apply Parameters</h3>
      <form method="post" action="{{ url_for('api.bulk_apply') }}">
        <p><b>1) Source Profile</b></p>
        <select name="source_id" required>
          <option value="">-- Select source (copy from) --</option>
          {% for row in all_profiles %}
            <option value="{{row.id}}" {% if sp and row.id==sp.id %}selected{% endif %}>
              {{row.symbol}} — {{row.timeframe}} (id={{row.id}})
            </option>
          {% endfor %}
        </select>

        <p style="margin-top:10px;"><b>2) Target Profiles</b></p>
        <div style="margin-bottom:6px;">
          <button type="button" onclick="selectAll('target-cb')">Select All</button>
          <button type="button" onclick="clearAll('target-cb')">Clear All</button>
        </div>
        <div style="max-height:220px;overflow:auto;border:1px solid #ddd;padding:8px;">
          {% for row in all_profiles %}
            <label style="display:block">
              <input type="checkbox" class="target-cb" name="target_ids" value="{{row.id}}"
                     {% if sp and row.id==sp.id %}disabled{% endif %}/>
              {{row.symbol}} — {{row.timeframe}} (id={{row.id}})
            </label>
          {% endfor %}
        </div>

        <p style="margin-top:10px;"><b>3) (Optional) Auto-create missing profiles</b></p>
        <p>Symbols CSV (e.g., <code>BTC/USD,ETH/USD,SOL/USD</code>) and TF:
          <input name="new_symbols_csv" size="40" />
          <input name="new_tf" size="6" placeholder="1m"/>
          <label><input type="checkbox" name="create_missing" /> Create & apply</label>
        </p>

        <p style="margin-top:10px;"><b>4) Apply</b></p>
        <button>Apply Source Parameters</button>
      </form>
      <p style="color:#666;margin-top:8px;">All tunables copied 1:1 (mode, RSI/MACD, weights, trailing/stop, size).</p>
    </div>
  </div>

  <hr/>
  <h3>Set Alpaca Keys (encrypted)</h3>
  <form method="post" action="{{ url_for('api.save_keys') }}">
    <input name="key_id" placeholder="Key ID" size="40" required />
    <input name="secret" placeholder="Secret" size="60" required />
    <label><input type="checkbox" name="paper" checked/> Paper</label>
    <button>Save</button>
  </form>
</body>
</html>
"""

@ui_bp.route("/")
def index():
    svc = SettingsService()
    rt = svc.get_runtime()
    symbol = (request.args.get("symbol") or "BTC/USD").upper()
    tf = (request.args.get("tf") or "1m")
    sp = db_session.query(StrategyParam).filter_by(symbol=symbol, timeframe=tf).one_or_none()
    all_profiles = db_session.query(StrategyParam).order_by(StrategyParam.symbol, StrategyParam.timeframe).all()
    return render_template_string(INDEX_HTML, rt=rt, sp=sp, spec=PARAM_SPEC,
                                  symbol=symbol, tf=tf, getattr=getattr, all_profiles=all_profiles)

@ui_bp.route("/orders")
def orders():
    rows = db_session.query(Trade).order_by(Trade.ts.desc()).limit(500).all()
    html = ["<h2>Orders Log</h2><p><a href='/'>Back</a></p><table border=1 cellpadding=6>",
            "<tr><th>ID</th><th>TS</th><th>Symbol</th><th>Side</th><th>Price</th><th>PnL%</th><th>Reason</th><th>Snapshot</th></tr>"]
    for t in rows:
        snap_html = f"/snapshots/trade_{t.id}.html"
        exists = os.path.exists(os.path.join(SNAP_DIR, f"trade_{t.id}.html"))
        link = f"<a href='{snap_html}' target='_blank'>View</a>" if exists else f"<a href='/api/trade/{t.id}/snapshot' target='_blank'>Generate</a>"
        html.append(f"<tr><td>{t.id}</td><td>{t.ts}</td><td>{t.symbol}</td><td>{t.side}</td><td>{t.price:.6f}</td><td>{(t.pnl_pct or 0):.2f}</td><td>{t.reason or ''}</td><td>{link}</td></tr>")
    html.append("</table>")
    return "\n".join(html)

@api_bp.route("/toggle", methods=["POST"])
def toggle():
    svc = SettingsService()
    r = svc.get_runtime()
    svc.set_runtime(enabled=not r.bot_enabled)
    return redirect(url_for("ui.index"))

@api_bp.route("/create_profile", methods=["POST"])
def create_profile():
    symbol = request.form["symbol"].upper()
    tf = request.form["timeframe"]
    if not db_session.query(StrategyParam).filter_by(symbol=symbol, timeframe=tf).one_or_none():
        db_session.add(StrategyParam(symbol=symbol, timeframe=tf))
        db_session.commit()
    return redirect(url_for("ui.index", symbol=symbol, tf=tf))

@api_bp.route("/save_params", methods=["POST"])
def save_params():
    pid = int(request.form["id"])
    sp = db_session.get(StrategyParam, pid)
    for f,_,t,_,_,_ in PARAM_SPEC:
        if f in request.form and request.form[f] != "":
            v = request.form[f]
            setattr(sp, f, float(v) if t=="number" and ("." in v) else (int(v) if t=="number" else v))
    db_session.commit()
    SettingsService().refresh_cache()
    return redirect(url_for("ui.index", symbol=sp.symbol, tf=sp.timeframe))

@api_bp.route("/save_keys", methods=["POST"])
def save_keys():
    upsert_alpaca_keys(request.form["key_id"], request.form["secret"], paper=("paper" in request.form))
    return redirect(url_for("ui.index"))

@api_bp.route("/bulk_apply", methods=["POST"])
def bulk_apply():
    source_id = int(request.form["source_id"])
    target_ids = [int(x) for x in request.form.getlist("target_ids") if x.isdigit()]
    create_missing = "create_missing" in request.form
    new_symbols_csv = (request.form.get("new_symbols_csv") or "").strip()
    new_tf = (request.form.get("new_tf") or "").strip() or "1m"

    src = db_session.get(StrategyParam, source_id)
    if not src: return redirect(url_for("ui.index"))

    if create_missing and new_symbols_csv:
        for sym in [s.strip().upper() for s in new_symbols_csv.split(",") if s.strip()]:
            existing = db_session.query(StrategyParam).filter_by(symbol=sym, timeframe=new_tf).one_or_none()
            if not existing:
                clone = StrategyParam(symbol=sym, timeframe=new_tf)
                for f in PARAM_FIELDS:
                    setattr(clone, f, getattr(src, f))
                db_session.add(clone); db_session.commit()
                target_ids.append(clone.id)

    for tid in set(target_ids):
        if tid == source_id: continue
        dst = db_session.get(StrategyParam, tid)
        if not dst: continue
        for f in PARAM_FIELDS:
            setattr(dst, f, getattr(src, f))
    db_session.commit()
    SettingsService().refresh_cache()
    return redirect(url_for("ui.index"))

@api_bp.route("/events/latest_trade")
def latest_trade():
    ev = db_session.query(UiEvent).order_by(UiEvent.id.desc()).first()
    if not ev: return jsonify({})
    return jsonify({"id": ev.ref_id, "kind": ev.kind})

def _tf_to_secs(tf: str) -> int:
    tf = (tf or "1m").lower()
    if tf.endswith("m"): return int(tf[:-1]) * 60
    if tf.endswith("h"): return int(tf[:-1]) * 3600
    return 60

@api_bp.route("/bar_count")
def bar_count():
    trade_id = int(request.args["trade_id"])
    wait_after_side = request.args.get("side") or "sell"
    t = db_session.get(Trade, trade_id)
    if not t: return jsonify({"count": 0})
    tf = (t.meta or {}).get("timeframe", "1m")
    df = fetch_bars(t.symbol, timeframe="1Min", limit=400)
    if df.empty: return jsonify({"count": 0})
    # count bars strictly AFTER the reference trade time for the given side
    ref_ts = t.ts
    # If the trade is a "buy" and you're waiting after exit, caller should pass the exit id instead.
    count = int((df["t"] > ref_ts).sum())
    return jsonify({"count": count, "tf": tf})

@api_bp.route("/trade/<int:trade_id>/snapshot")
def make_snapshot(trade_id: int):
    # why: persist the latest frame to disk for later viewing
    import plotly.graph_objs as go
    import plotly.io as pio

    t = db_session.get(Trade, trade_id)
    if not t: return "Trade not found", 404
    tf = (t.meta or {}).get("timeframe", "1m")
    df = fetch_bars(t.symbol, timeframe="1Min", limit=400)
    if df.empty: return "No bars", 500

    fig = go.Figure(data=[go.Candlestick(x=df["t"], open=df["open"], high=df["high"], low=df["low"], close=df["close"])])
    fig.add_hline(y=t.price, line_dash="dot", annotation_text=f"{'ENTRY' if t.side=='buy' else 'EXIT'} @ {t.price:.2f}")

    # Try to render trailing and peak from meta when available
    m = t.meta or {}
    if m.get("trailing_active"):
        if m.get("trail_primary") is not None:
            fig.add_hline(y=m["trail_primary"], line_dash="dash", annotation_text="Trail #1")
        if m.get("trail_secondary") is not None:
            fig.add_hline(y=m["trail_secondary"], line_dash="dash", annotation_text="Trail #2")
    if m.get("entry_price"):
        fig.add_hline(y=m["entry_price"], line_dash="dot", annotation_text=f"Entry @ {m['entry_price']:.2f}")
    if m.get("peak_price"):
        fig.add_hline(y=m["peak_price"], line_dash="dash", annotation_text=f"Peak @ {m['peak_price']:.2f}")

    title = f"{t.symbol} Trade {t.side.upper()} | P&L {t.pnl_pct or 0:.2f}% | Reason {t.reason or ''} | TF {tf}"
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, template="plotly_white")

    html_path = os.path.join(SNAP_DIR, f"trade_{t.id}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(fig.to_html(include_plotlyjs="cdn", full_html=True))

    # Optional PNG (requires kaleido). Enable if installed:
    # try:
    #     png_path = os.path.join(SNAP_DIR, f"trade_{t.id}.png")
    #     pio.write_image(fig, png_path, format="png", width=1280, height=720, scale=2)
    # except Exception:
    #     pass

    return redirect(f"/snapshots/trade_{t.id}.html")

@ui_bp.route("/trade/<int:trade_id>")
def trade_view(trade_id: int):
    import plotly.graph_objs as go
    t = db_session.get(Trade, trade_id)
    if not t: return "Trade not found", 404
    tf = (t.meta or {}).get("timeframe", "1m")
    df = fetch_bars(t.symbol, timeframe="1Min", limit=300)
    if df.empty: return "No bars", 500

    fig = go.Figure(data=[go.Candlestick(x=df["t"], open=df["open"], high=df["high"], low=df["low"], close=df["close"])])
    fig.add_hline(y=t.price, line_dash="dot", annotation_text=f"{'ENTRY' if t.side=='buy' else 'EXIT'} @ {t.price:.2f}")

    m = t.meta or {}
    if m.get("trailing_active"):
        if m.get("trail_primary") is not None:
            fig.add_hline(y=m["trail_primary"], line_dash="dash", annotation_text="Trail #1")
        if m.get("trail_secondary") is not None:
            fig.add_hline(y=m["trail_secondary"], line_dash="dash", annotation_text="Trail #2")
    if m.get("entry_price"):
        fig.add_hline(y=m["entry_price"], line_dash="dot", annotation_text=f"Entry @ {m['entry_price']:.2f}")
    if m.get("peak_price"):
        fig.add_hline(y=m["peak_price"], line_dash="dash", annotation_text=f"Peak @ {m['peak_price']:.2f}")

    title = f"{t.symbol} {t.side.upper()} | P&L {t.pnl_pct or 0:.2f}% | Reason {t.reason or ''} | TF {tf}"
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, template="plotly_white")
    html_fig = fig.to_html(include_plotlyjs="cdn", full_html=False)

    # JS: reload to simulate moving chart, wait N bars then snapshot & close
    WAIT_BARS = int(request.args.get("wait_bars", "4"))
    POLL_MS   = int(request.args.get("poll_ms", "5000"))
    html = f"""
    <!doctype html><html><head><title>Trade {trade_id}</title></head>
    <body>
      <div id="fig">{html_fig}</div>
      <div style="margin-top:8px;color:#666">
        Auto-saving after {WAIT_BARS} bars… <button onclick="saveNow()">Save Now</button>
        <button onclick="window.stopReload=true">Keep Open</button>
      </div>
      <script>
        let lastReload = Date.now();
        async function checkBars(){{
          try {{
            const r = await fetch('/api/bar_count?trade_id={trade_id}');
            const j = await r.json();
            if (j.count >= {WAIT_BARS} && !window.stopReload) {{
              await fetch('/api/trade/{trade_id}/snapshot');
              setTimeout(()=>window.close(), 800);
              return;
            }}
          }} catch(e){{}}
          if (!window.stopReload) setTimeout(checkBars, {POLL_MS});
        }}
        function saveNow(){{
          fetch('/api/trade/{trade_id}/snapshot').then(()=>window.close());
        }}
        setTimeout(checkBars, {POLL_MS});
        // Optional moving effect: periodic soft reload
        setInterval(()=>{{ if(!window.stopReload) location.reload(); }}, {POLL_MS*3});
      </script>
    </body></html>
    """
    return html

@ui_bp.route("/snapshots/<path:fname>")
def serve_snapshot(fname: str):
    # why: serve saved frames even without static server config
    return send_from_directory(SNAP_DIR, fname, as_attachment=False)
    
@api_bp.route("/health")
def health():
    """DB + runtime health."""
    from .services.settings import SettingsService
    from .db import db_session
    from sqlalchemy import text

    try:
        db_session.execute(text("SELECT 1"))
        svc = SettingsService()
        rt = svc.get_runtime()
        return jsonify({
            "status": "ok",
            "enabled": bool(rt.bot_enabled),
            "mode": rt.mode,
            "last_heartbeat": str(rt.last_heartbeat)
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503
        
        # Append to the END of app/views.py (do not remove your existing code)

# 1) Ensure these are already imported at the top of views.py; add any missing ones:
from flask import Blueprint, render_template_string, request, redirect, url_for, jsonify
from .db import db_session
from .models import StrategyParam
from .services.settings import SettingsService

# 2) Ensure blueprints exist somewhere above; if not, add these lines once:
# ui_bp = Blueprint("ui", __name__)
# api_bp = Blueprint("api", __name__)

# 3) ADD the Bulk Apply page + endpoint:
BULK_HTML = """
<!doctype html>
<html>
<head>
  <title>AIMn — Bulk Apply</title>
  <style>
    body{font-family:sans-serif} .card{border:1px solid #bbb;padding:12px;border-radius:8px;max-width:900px}
    label{display:block;margin:4px 0} .top a{margin-right:12px}
  </style>
  <script>
    function selAll(){ document.querySelectorAll('input.target').forEach(cb=>{ if(!cb.disabled) cb.checked=true; }); }
    function clrAll(){ document.querySelectorAll('input.target').forEach(cb=>cb.checked=false); }
  </script>
</head>
<body>
  <div class="top"><a href="/">Dashboard</a> <b>Bulk Apply</b></div>
  <h2>Bulk Apply Parameters</h2>
  <div class="card">
    <form method="post" action="{{ url_for('api.bulk_apply') }}">
      <p><b>1) Source profile</b></p>
      <select name="source_id" required>
        <option value="">-- select --</option>
        {% for p in all_profiles %}
          <option value="{{p.id}}">{{p.symbol}} — {{p.timeframe}} (id={{p.id}})</option>
        {% endfor %}
      </select>

      <p style="margin-top:10px;"><b>2) Target profiles</b></p>
      <button type="button" onclick="selAll()">Select All</button>
      <button type="button" onclick="clrAll()">Clear All</button>
      <div style="max-height:260px;overflow:auto;border:1px solid #ddd;padding:8px;margin-top:6px;">
        {% for p in all_profiles %}
          <label>
            <input type="checkbox" class="target" name="target_ids" value="{{p.id}}">
            {{p.symbol}} — {{p.timeframe}} (id={{p.id}})
          </label>
        {% endfor %}
      </div>

      <p style="margin-top:10px;"><b>3) (Optional) Auto-create from symbols CSV</b></p>
      <div>
        Symbols: <input name="new_symbols_csv" size="40" placeholder="BTC/USD,ETH/USD,SOL/USD">
        TF: <input name="new_tf" size="6" value="1m">
        <label><input type="checkbox" name="create_missing"> Create & include</label>
      </div>

      <p style="margin-top:10px;"><b>4) Apply</b></p>
      <button>Apply Source Parameters</button>
    </form>
  </div>
</body>
</html>
"""

@ui_bp.route("/bulk")
def bulk():
    all_profiles = db_session.query(StrategyParam).order_by(StrategyParam.symbol, StrategyParam.timeframe).all()
    return render_template_string(BULK_HTML, all_profiles=all_profiles)

@api_bp.route("/bulk_apply", methods=["POST"])
def bulk_apply():
    src_id = int(request.form["source_id"])
    target_ids = [int(x) for x in request.form.getlist("target_ids") if x.isdigit()]
    create_missing = "create_missing" in request.form
    new_symbols_csv = (request.form.get("new_symbols_csv") or "").strip()
    new_tf = (request.form.get("new_tf") or "").strip() or "1m"

    src = db_session.get(StrategyParam, src_id)
    if not src:
        return redirect(url_for("ui.index"))

    excluded = {"id", "symbol", "timeframe", "updated_at"}
    copy_fields = [c.name for c in StrategyParam.__table__.columns if c.name not in excluded]

    if create_missing and new_symbols_csv:
        symbols = [s.strip().upper() for s in new_symbols_csv.split(",") if s.strip()]
        for sym in symbols:
            existing = db_session.query(StrategyParam).filter_by(symbol=sym, timeframe=new_tf).one_or_none()
            if not existing:
                clone = StrategyParam(symbol=sym, timeframe=new_tf)
                for f in copy_fields:
                    setattr(clone, f, getattr(src, f))
                db_session.add(clone); db_session.commit()
                target_ids.append(clone.id)

    for tid in set(target_ids):
        if tid == src_id:
            continue
        dst = db_session.get(StrategyParam, tid)
        if not dst:
            continue
        for f in copy_fields:
            setattr(dst, f, getattr(src, f))
    db_session.commit()
    SettingsService().refresh_cache()
    return redirect(url_for("bulk"))

# --- append to END of app/views.py ---

# Requires at top (ensure these imports exist in your file):
# from flask import Blueprint, render_template_string, request, redirect, url_for, jsonify
# from .db import db_session
# from .models import StrategyParam   # already used
from .models import Trade            # add this import if missing
from flask import send_from_directory
import os

# Snapshots directory (saved frames live here)
SNAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "snapshots"))
os.makedirs(SNAP_DIR, exist_ok=True)

@ui_bp.route("/orders")
def orders():
    rows = db_session.query(Trade).order_by(Trade.ts.desc()).limit(500).all()
    # simple HTML for quick visibility
    html = [
        "<!doctype html><html><head><title>AIMn — Orders Log</title>",
        "<style>body{font-family:sans-serif}table{border-collapse:collapse}td,th{border:1px solid #888;padding:6px}</style>",
        "</head><body>",
        "<div><a href='/'>Dashboard</a></div>",
        "<h2>Orders Log</h2>",
        "<table><tr><th>ID</th><th>Time</th><th>Symbol</th><th>Side</th><th>Price</th><th>PnL%</th><th>Reason</th><th>Snapshot</th></tr>"
    ]
    for t in rows:
        snap_name = f"trade_{t.id}.html"
        snap_path = os.path.join(SNAP_DIR, snap_name)
        if os.path.exists(snap_path):
            snap_link = f"<a target='_blank' href='/snapshots/{snap_name}'>View</a>"
        else:
            snap_link = "<span style='color:#888'>None</span>"
        html.append(
            f"<tr><td>{t.id}</td><td>{t.ts}</td><td>{t.symbol}</td>"
            f"<td>{t.side}</td><td>{t.price:.6f}</td><td>{(t.pnl_pct or 0):.2f}</td>"
            f"<td>{t.reason or ''}</td><td>{snap_link}</td></tr>"
        )
    html.append("</table></body></html>")
    return "\n".join(html)

@ui_bp.route("/snapshots/<path:fname>")
def serve_snapshot(fname: str):
    # serve saved chart frames (HTML files) from snapshots folder
    return send_from_directory(SNAP_DIR, fname, as_attachment=False)
