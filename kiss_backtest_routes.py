"""Routes for the independent KISS backtest.

The research baseline runs on 5m candles and accepts independent LONG/SHORT
RSI rescue thresholds plus a programmable trailing-minus percentage.
"""
from flask import jsonify, render_template, request


def _db_rows(symbol: str, timeframe: str, broker_id: str = "", limit: int = 5000):
    from db import get_db_connection
    tf_map = {"5m": "5m", "15m": "15m", "30m": "30m", "1hr": "1h", "1h": "1h", "6hr": "6h", "6h": "6h"}
    db_tf = tf_map.get(timeframe, timeframe)
    conn, cursor = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        if broker_id:
            cursor.execute(
                """SELECT timestamp, open, high, low, close, volume
                   FROM candles
                   WHERE symbol=%s AND broker_id=%s AND timeframe=%s
                   ORDER BY timestamp ASC
                   LIMIT %s""",
                (symbol, broker_id, db_tf, int(limit)),
            )
            return cursor.fetchall()
        cursor.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC
               LIMIT %s""",
            (symbol, db_tf, int(limit)),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def _row_dicts(rows):
    """Normalize MySQL dictionary-cursor rows to the engine's expected shape.

    db.get_db_connection() uses cursor(dictionary=True), so rows are mappings,
    not tuples. The previous tuple-only conversion tried r[0], which produced
    KeyError: 0 and surfaced in the browser as ERROR: 0.
    """
    normalized = []
    for r in rows:
        if isinstance(r, dict):
            normalized.append({
                "timestamp": r.get("timestamp"),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
            })
        else:
            normalized.append({
                "timestamp": r[0],
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5],
            })
    return normalized


def _run_selected(symbol, direction, broker_id, rsi_rescue_long, rsi_rescue_short, trailing_minus_pct, commission_pct, entry_mode):
    """Run the research baseline: 5m candles only."""
    from engine.kiss_backtest import run_kiss_backtest
    rows = _row_dicts(_db_rows(symbol, "5m", broker_id=broker_id))
    return run_kiss_backtest(
        rows,
        symbol,
        direction,
        "5m",
        rsi_rescue_long=rsi_rescue_long,
        rsi_rescue_short=rsi_rescue_short,
        trailing_minus_pct=trailing_minus_pct,
        commission_pct=commission_pct,
        entry_mode=entry_mode,
    )


def register_kiss_backtest_routes(app):
    @app.route("/kiss_backtest")
    def kiss_backtest_page():
        return render_template("kiss_backtest.html")

    @app.route("/api/kiss_backtest", methods=["GET"])
    def kiss_backtest_api():
        try:
            symbol = (request.args.get("symbol") or "").strip().upper()
            direction = (request.args.get("direction") or "LONG").strip().upper()
            timeframe = "5m"
            broker_id = request.args.get("broker_id") or ""
            rsi_rescue_long = float(request.args.get("rsi_rescue_long") or 20.0)
            rsi_rescue_short = float(request.args.get("rsi_rescue_short") or 80.0)
            trailing_minus_pct = float(request.args.get("trailing_minus_pct") or 0.5)
            commission_pct = float(request.args.get("commission_pct") or 0.0)
            entry_mode = (request.args.get("entry_mode") or "V15").strip().upper()
            if entry_mode not in {"V15", "V16"}:
                return jsonify({"status": "error", "message": "entry_mode must be V15 or V16"}), 400
            if not symbol:
                return jsonify({"status": "error", "message": "Symbol is required"}), 400

            result = _run_selected(
                symbol, direction, broker_id,
                rsi_rescue_long, rsi_rescue_short,
                trailing_minus_pct, commission_pct, entry_mode
            )
            result["broker_id"] = broker_id
            result["timeframe"] = "5m"
            result["parameters"] = {
                "rsi_rescue_long": rsi_rescue_long,
                "rsi_rescue_short": rsi_rescue_short,
                "trailing_minus_pct": trailing_minus_pct,
                "commission_pct_one_side": commission_pct,
                "entry_mode": entry_mode,
            }
            result["losers"] = [t for t in result["trades"] if t["net_pnl_pct"] <= 0]
            result["winners_hidden"] = True
            return jsonify({"status": "success", **result})
        except Exception as exc:
            import traceback
            return jsonify({"status": "error", "message": str(exc), "trace": traceback.format_exc()}), 500

    @app.route("/api/kiss_backtest/chart", methods=["GET"])
    def kiss_backtest_chart():
        try:
            symbol = (request.args.get("symbol") or "").strip().upper()
            timeframe = "5m"
            broker_id = request.args.get("broker_id") or ""
            trade_id = (request.args.get("trade_id") or "").strip()
            direction = (request.args.get("direction") or "LONG").strip().upper()
            rsi_rescue_long = float(request.args.get("rsi_rescue_long") or 20.0)
            rsi_rescue_short = float(request.args.get("rsi_rescue_short") or 80.0)
            trailing_minus_pct = float(request.args.get("trailing_minus_pct") or 0.5)
            commission_pct = float(request.args.get("commission_pct") or 0.0)
            entry_mode = (request.args.get("entry_mode") or "V15").strip().upper()
            if entry_mode not in {"V15", "V16"}:
                return jsonify({"status": "error", "message": "entry_mode must be V15 or V16"}), 400
            if not symbol or not trade_id:
                return jsonify({"status": "error", "message": "symbol and trade_id are required"}), 400

            from engine.kiss_backtest import run_kiss_backtest
            rows = _row_dicts(_db_rows(symbol, "5m", broker_id=broker_id))
            result = run_kiss_backtest(
                rows, symbol, direction, "5m",
                rsi_rescue_long=rsi_rescue_long,
                rsi_rescue_short=rsi_rescue_short,
                trailing_minus_pct=trailing_minus_pct,
                commission_pct=commission_pct,
                entry_mode=entry_mode,
            )

            trade = next((t for t in result["trades"] if t["trade_id"] == trade_id), None)
            if not trade:
                return jsonify({"status": "error", "message": "Trade ID not found"}), 404

            entry_i = next(i for i, r in enumerate(rows) if str(r["timestamp"]) == trade["entry_time"])
            exit_i = next(i for i, r in enumerate(rows) if str(r["timestamp"]) == trade["exit_time"])
            start = max(0, entry_i - 36)
            end = min(len(rows), exit_i + 37)
            candles = []
            for r in rows[start:end]:
                candles.append({
                    "time": str(r["timestamp"]), "open": float(r["open"]), "high": float(r["high"]),
                    "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"] or 0),
                })
            return jsonify({
                "status": "success", "trade": trade, "candles": candles,
                "decision_timeframe": "5m",
                "execution_timeframe": "5m",
            })
        except Exception as exc:
            import traceback
            return jsonify({"status": "error", "message": str(exc), "trace": traceback.format_exc()}), 500
