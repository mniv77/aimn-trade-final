import pathlib, re
app_path = pathlib.Path("/home/MeirNiv/aimn-trade-final/app.py") if pathlib.Path("/home/MeirNiv/aimn-trade-final/app.py").exists() else pathlib.Path("app.py")
txt = app_path.read_text()
# remove any old v32 blocks
txt = re.sub(r"@app\.route\('/api/v32_candles'.*?read\(\)\)\n", "", txt, flags=re.DOTALL)
txt = re.sub(r"@app\.route\('/v32_chart'.*?read\(\)\)\n", "", txt, flags=re.DOTALL)
txt = re.sub(r"# === V32.*?# === END V32 ===\n?", "", txt, flags=re.DOTALL)

# add clean block at end
add = """

# === V32 SYNCED - SINGLE CORRECT ===
@app.route('/api/v32_candles', endpoint='api_v32_candles_final')
def api_v32_candles_final():
    from engine.tuning.candle_fetcher import fetch_gemini_candles
    try:
        from engine.tuning.simulate_trades_v5_ai_trailing import simulate_trades_v5_ai_trailing
    except ImportError:
        from engine.tuning.simulator import simulate_trades_v5_ai_trailing
    from flask import request, jsonify
    sym = request.args.get('symbol','linkusd')
    tf = request.args.get('tf','30m')
    limit = int(request.args.get('limit','2016'))
    params = {"rsi_entry":35,"rsi_len":50,"stop_loss":2,"trail_drop":0.3,"trail_start":1,"profit_floor":0.5,"decay_start":2,"decay_rate":0.5,"direction":"LONG"}
    candles = fetch_gemini_candles(sym, tf, limit)
    if not candles:
        return jsonify({"candles":[],"trades":[],"total_pnl":0,"error":"no candles from gemini"})
    chart = [{"time": int(c["timestamp"].timestamp()), "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"]} for c in candles]
    res = simulate_trades_v5_ai_trailing(candles, **params)
    trades = res.get("trades",[]) if isinstance(res, dict) else res
    total = res.get("total_pnl",0) if isinstance(res, dict) else sum([t.get("pnl_pct",0) for t in trades])
    return jsonify({"candles": chart, "trades": trades, "total_pnl": total})

@app.route('/v32_chart', endpoint='v32_chart_final')
def v32_chart_final():
    return open('templates/v32_synced.html').read()
# === END V32 ===
"""
txt = txt.rstrip() + "\n" + add
app_path.write_text(txt)
print(f"Patched {app_path} OK")
