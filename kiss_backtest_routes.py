"""Routes for the independent KISS backtest.

The normal KISS path remains available. When the selected decision timeframe is
30m, this route uses the isolated 30m-trend / 5m-execution experiment.
"""
from flask import jsonify, render_template, request


def _db_rows(symbol: str, timeframe: str, limit: int = 5000):
    from db import get_db_connection
    tf_map = {"5m": "5m", "15m": "15m", "30m": "30m", "1hr": "1h", "1h": "1h", "6hr": "6h", "6h": "6h"}
    db_tf = tf_map.get(timeframe, timeframe)
    conn, cursor = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
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
    """Convert DB tuple rows to the dictionaries used by the KISS engines."""
    return [
        {
            "timestamp": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
        }
        for r in rows
    ]


def _run_selected(symbol, direction, timeframe):
    """Run the selected KISS experiment without touching broker/symbol selection."""
    if timeframe == "30m":
        from engine.kiss_execution_5m import run_kiss_30m_5m
        trend_rows = _row_dicts(_db_rows(symbol, "30m"))
        execution_rows = _row_dicts(_db_rows(symbol, "5m"))
        return run_kiss_30m_5m(trend_rows, execution_rows, symbol, direction)

    from engine.kiss_backtest import run_kiss_backtest
    rows = _row_dicts(_db_rows(symbol, timeframe))
    return run_kiss_backtest(rows, symbol, direction, timeframe)


def register_kiss_backtest_routes(app):
    @app.route("/kiss_backtest")
    def kiss_backtest_page():
        return render_template("kiss_backtest.html")

    @app.route("/api/kiss_backtest", methods=["GET"])
    def kiss_backtest_api():
        try:
            symbol = (request.args.get("symbol") or "").strip().upper()
            direction = (request.args.get("direction") or "LONG").strip().upper()
            timeframe = (request.args.get("timeframe") or "1hr").strip()
            broker_id = request.args.get("broker_id") or ""
            if not symbol:
                return jsonify({"status": "error", "message": "Symbol is required"}), 400

            result = _run_selected(symbol, direction, timeframe)
            result["broker_id"] = broker_id
            result["losers"] = [t for t in result["trades"] if t["pnl_pct"] <= 0]
            result["winners_hidden"] = True
            if timeframe == "30m":
                result["execution_experiment"] = "30m trend decision / 5m execution"
            return jsonify({"status": "success", **result})
        except Exception as exc:
            import traceback
            return jsonify({"status": "error", "message": str(exc), "trace": traceback.format_exc()}), 500

    @app.route("/api/kiss_backtest/chart", methods=["GET"])
    def kiss_backtest_chart():
        try:
            symbol = (request.args.get("symbol") or "").strip().upper()
            timeframe = (request.args.get("timeframe") or "1hr").strip()
            trade_id = (request.args.get("trade_id") or "").strip()
            direction = (request.args.get("direction") or "LONG").strip().upper()
            if not symbol or not trade_id:
                return jsonify({"status": "error", "message": "symbol and trade_id are required"}), 400

            if timeframe == "30m":
                from engine.kiss_execution_5m import run_kiss_30m_5m
                trend_rows = _row_dicts(_db_rows(symbol, "30m"))
                rows = _row_dicts(_db_rows(symbol, "5m"))
                result = run_kiss_30m_5m(trend_rows, rows, symbol, direction)
            else:
                from engine.kiss_backtest import run_kiss_backtest
                rows = _row_dicts(_db_rows(symbol, timeframe))
                result = run_kiss_backtest(rows, symbol, direction, timeframe)

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
                    "time": str(r["timestamp"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"] or 0),
                })
            return jsonify({
                "status": "success",
                "trade": trade,
                "candles": candles,
                "decision_timeframe": "30m" if timeframe == "30m" else timeframe,
                "execution_timeframe": "5m" if timeframe == "30m" else timeframe,
            })
        except Exception as exc:
            import traceback
            return jsonify({"status": "error", "message": str(exc), "trace": traceback.format_exc()}), 500
