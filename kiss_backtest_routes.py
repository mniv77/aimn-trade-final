
"""Routes for the independent KISS backtest.

The research baseline runs on 5m candles and accepts independent LONG/SHORT
RSI rescue thresholds plus a programmable trailing-minus percentage.

Step 64K adds a read-only, validated candle endpoint for AIMn Visual Laboratory.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import tempfile
from flask import jsonify, render_template, request


def _db_rows(symbol: str, timeframe: str, broker_id: str = "", limit: int = 5000):
    from db import get_db_connection
    tf_map = {"5m": "5m", "15m": "15m", "30m": "30m", "1hr": "1h", "1h": "1h", "6hr": "6h", "6h": "6h"}
    db_tf = tf_map.get(timeframe, timeframe)
    conn, cursor = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        # candles does not contain broker_id in this database schema.
        # broker_id remains a UI/request parameter for compatibility, but
        # candle selection is by symbol + timeframe.
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
    """Normalize MySQL dictionary-cursor rows to the engine's expected shape."""
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


def _validated_lab_candles(rows):
    """Fail closed on unaligned, malformed or duplicate 5m candles."""
    candles = []
    previous_time = None
    for r in rows:
        raw_time = r["timestamp"]
        if isinstance(raw_time, datetime):
            dt = raw_time
        else:
            dt = datetime.fromisoformat(str(raw_time))
        if dt.second != 0 or dt.microsecond != 0 or dt.minute % 5 != 0:
            raise ValueError("Non-standard 5m timestamps detected; data not safe for Visual Laboratory")
        if previous_time is not None and dt <= previous_time:
            raise ValueError("Duplicate or out-of-order candle timestamps")
        previous_time = dt
        o, h, l, c = (float(r[k]) for k in ("open", "high", "low", "close"))
        v = float(r["volume"] or 0)
        if not (l <= min(o, c) <= max(o, c) <= h) or v < 0:
            raise ValueError("Invalid candle OHLCV values")
        candles.append({"time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": o, "high": h, "low": l, "close": c, "volume": v})
    return candles



# Step 64AM: Completed research results are snapshots, never recalculated on read.
# Storage is local to this Flask application's instance directory.
def _research_snapshot_key(symbol, direction, broker_id, params):
    identity = {
        "symbol": symbol, "direction": direction, "broker_id": str(broker_id),
        "timeframe": "5m", "parameters": params,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _research_snapshot_path(app, key):
    return Path(app.instance_path) / "kiss_saved_results" / (key + ".json")


def _research_params(args):
    return {
        "rsi_rescue_long": float(args.get("rsi_rescue_long") or 20.0),
        "rsi_rescue_short": float(args.get("rsi_rescue_short") or 80.0),
        "trailing_minus_pct": float(args.get("trailing_minus_pct") or 0.5),
        "commission_pct_one_side": float(args.get("commission_pct") or 0.0),
        "entry_mode": (args.get("entry_mode") or "V15").strip().upper(),
    }


def _save_research_snapshot(app, symbol, direction, broker_id, params, result):
    key = _research_snapshot_key(symbol, direction, broker_id, params)
    target = _research_snapshot_path(app, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "success", "source": "saved_kiss_backtest",
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol, "direction": direction, "broker_id": str(broker_id),
        "timeframe": "5m", "parameters": params,
        "trades": result.get("trades", []),
        "total_pnl_pct": result.get("total_pnl_pct"),
        "win_rate_pct": result.get("win_rate_pct"),
        "candle_count": result.get("candle_count"),
    }
    # Replace atomically so readers never observe partially written JSON.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".kiss_", suffix=".tmp", delete=False) as fh:
            temp_name = fh.name
            json.dump(payload, fh, ensure_ascii=False, default=str, allow_nan=False)
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def register_kiss_backtest_routes(app):
    @app.route("/kiss_backtest")
    def kiss_backtest_page():
        return render_template("kiss_backtest.html")

    @app.route("/api/aimn_visual_lab/candles", methods=["GET"])
    def aimn_visual_lab_candles_api():
        """Read-only candles for charts; no backtest or trade execution."""
        symbol = (request.args.get("symbol") or "").strip().upper()
        timeframe = (request.args.get("timeframe") or "5m").strip()
        broker_id = request.args.get("broker_id") or ""
        # Until the crypto snapshot issue is resolved, allow only verified stock symbols.
        stock_symbols = {"NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL", "SPY", "QQQ"}
        if symbol not in stock_symbols or timeframe != "5m":
            return jsonify({"status": "error", "message": "Only validated stock-symbol 5m datasets are supported"}), 400
        try:
            rows = _row_dicts(_db_rows(symbol, "5m", broker_id=broker_id))
            if not rows:
                return jsonify({"status": "error", "message": "No candles found", "symbol": symbol}), 404
            candles = _validated_lab_candles(rows)
            return jsonify({"status": "success", "symbol": symbol, "timeframe": "5m",
                            "broker_id": broker_id, "source": "mysql", "count": len(candles),
                            "candles": candles, "trades": [], "research_overlays": False})
        except ValueError as exc:
            return jsonify({"status": "error", "symbol": symbol, "message": str(exc)}), 422
        except Exception:
            app.logger.exception("Visual Laboratory candle retrieval failed")
            return jsonify({"status": "error", "message": "Unable to retrieve candles"}), 500

    @app.route("/api/aimn_visual_lab/saved_trades", methods=["GET"])
    def aimn_visual_lab_saved_trades_api():
        """Read an existing completed KISS snapshot. NEVER run the engine."""
        symbol = (request.args.get("symbol") or "").strip().upper()
        direction = (request.args.get("direction") or "").strip().upper()
        broker_id = request.args.get("broker_id") or ""
        timeframe = (request.args.get("timeframe") or "5m").strip()
        if symbol not in {"NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL", "SPY", "QQQ"} or direction not in {"LONG", "SHORT"} or timeframe != "5m":
            return jsonify({"status": "error", "message": "Valid stock symbol, LONG/SHORT direction and 5m timeframe required"}), 400
        try:
            params = _research_params(request.args)
            if params["entry_mode"] not in {"V15", "V16", "V17"}:
                return jsonify({"status": "error", "message": "Invalid entry mode"}), 400
            key = _research_snapshot_key(symbol, direction, broker_id, params)
            path = _research_snapshot_path(app, key)
            if not path.is_file():
                return jsonify({"status": "not_saved", "symbol": symbol, "direction": direction,
                                "timeframe": "5m", "trades": [],
                                "message": "No previously saved KISS results match these settings. No backtest was run."})
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            return jsonify(payload)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Invalid research parameters"}), 400
        except Exception:
            app.logger.exception("Saved KISS research retrieval failed")
            return jsonify({"status": "error", "message": "Unable to retrieve saved KISS results"}), 500

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
            if entry_mode not in {"V15", "V16", "V17"}:
                return jsonify({"status": "error", "message": "entry_mode must be V15, V16 or V17"}), 400
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
            # Save only after an explicitly requested KISS run completes.
            # A failed save must not erase the backtest response.
            try:
                _save_research_snapshot(app, symbol, direction, broker_id,
                                        result["parameters"], result)
                result["saved_for_visual_lab"] = True
            except Exception:
                app.logger.exception("Could not save completed KISS research results")
                result["saved_for_visual_lab"] = False
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
            if entry_mode not in {"V15", "V16", "V17"}:
                return jsonify({"status": "error", "message": "entry_mode must be V15, V16 or V17"}), 400
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

    @app.route("/api/aimn_visual_lab/exp74_75", methods=["GET"])
    def aimn_exp74_75_comparison():
        """Research-only historical NVDA comparison; no orders or persistence."""
        try:
            from engine.kiss_backtest import run_kiss_backtest as baseline
            from kiss.exp74_kiss_hybrid_engine import run_kiss_backtest as hybrid
            from kiss.exp75_kiss_profit_lock_engine import run_kiss_backtest as profit_lock
            if request.args.get("symbol", "NVDA") != "NVDA":
                return jsonify({"status":"error","message":"EXP74/75 currently validated for NVDA only"}), 400
            source = Path(__file__).resolve().parent / "kiss/visual_research/aimn_nvda_candles.json"
            rows = json.loads(source.read_text(encoding="utf-8"))
            kwargs = dict(symbol="NVDA", direction="SHORT", timeframe="5m",
                          entry_mode="V15", trailing_minus_pct=0.50,
                          commission_pct=0.10, rsi_rescue_long=20, rsi_rescue_short=80)
            experiments = {}
            for label, engine in (("EXP74",hybrid),("EXP75",profit_lock)):
                result = engine(rows, **kwargs)
                experiments[label] = {
                    "trades": result["trades"],
                    "net_pct_sum": result["total_net_pnl_pct"],
                    "winners": result["winner_count"],
                    "count": len(result["trades"])
                }
            return jsonify({"status":"success","symbol":"NVDA","direction":"SHORT",
                            "timeframe":"5m","source":"frozen_research_candles",
                            "experiments":experiments})
        except Exception:
            app.logger.exception("EXP74/75 Visual Laboratory comparison failed")
            return jsonify({"status":"error","message":"Research comparison unavailable"}), 500
