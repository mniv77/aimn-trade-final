"""Routes for the independent KISS V3 backtest.

Nothing in the existing tuner/backtest strategy is imported here.
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


def register_kiss_backtest_routes(app):
    @app.route("/kiss_backtest")
    def kiss_backtest_page():
        return render_template("kiss_backtest.html")

    @app.route("/api/kiss_backtest", methods=["GET"])
    def kiss_backtest_api():
        try:
            from engine.kiss_backtest import run_kiss_backtest
            symbol = (request.args.get("symbol") or "").strip().upper()
            direction = (request.args.get("direction") or "LONG").strip().upper()
            timeframe = (request.args.get("timeframe") or "1hr").strip()
            broker_id = request.args.get("broker_id") or ""
            if not symbol:
                return jsonify({"status": "error", "message": "Symbol is required"}), 400
            rows = _db_rows(symbol, timeframe)
            result = run_kiss_backtest(rows, symbol, direction, timeframe)
            result["broker_id"] = broker_id
            result["losers"] = [t for t in result["trades"] if t["pnl_pct"] <= 0]
            result["winners_hidden"] = True
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
            from engine.kiss_backtest import run_kiss_backtest
            rows = _db_rows(symbol, timeframe)
            result = run_kiss_backtest(rows, symbol, direction, timeframe)
            trade = next((t for t in result["trades"] if t["trade_id"] == trade_id), None)
            if not trade:
                return jsonify({"status": "error", "message": "Trade ID not found"}), 404

            entry_i = next(i for i, r in enumerate(rows) if str(r["timestamp"]) == trade["entry_time"])
            exit_i = next(i for i, r in enumerate(rows) if str(r["timestamp"]) == trade["exit_time"])
            start = max(0, entry_i - 25)
            end = min(len(rows), exit_i + 26)
            candles = []
            for r in rows[start:end]:
                candles.append({
                    "time": str(r["timestamp"]),
                    "open": float(r["open"]), "high": float(r["high"]),
                    "low": float(r["low"]), "close": float(r["close"]),
                    "volume": float(r["volume"] or 0),
                })
            return jsonify({"status": "success", "trade": trade, "candles": candles})
        except Exception as exc:
            import traceback
            return jsonify({"status": "error", "message": str(exc), "trace": traceback.format_exc()}), 500
