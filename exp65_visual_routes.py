"""
AIMn EXP65 Visual Research
Read-only historical trade inspection.
No broker, database, or order execution.
"""

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import jsonify, render_template, request

from kiss.visual_research.exp65_out_of_sample_engine import (
    run_kiss_backtest,
)

DATA_FILE = (
    Path(__file__).resolve().parent
    / "kiss/visual_research/missed_short_audit/nvda_jul_oct_2026.json"
)

NY = ZoneInfo("America/New_York")


@lru_cache(maxsize=1)
def load_research():
    raw = json.loads(DATA_FILE.read_text())
    rows = []

    for candle in raw:
        row = dict(candle)
        row["timestamp"] = datetime.fromisoformat(
            row["timestamp"]
        ).astimezone(NY).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(row)

    result = run_kiss_backtest(
        rows, "NVDA", "SHORT", "5m",
        rsi_rescue_long=20,
        rsi_rescue_short=80,
        trailing_minus_pct=0.50,
        commission_pct=0.10,
        entry_mode="V18",
    )

    if len(result["trades"]) != 12:
        raise ValueError(
            "EXP65 reproduction mismatch: expected 12 trades"
        )

    timestamps = {
        row["timestamp"]: i
        for i, row in enumerate(rows)
    }

    return rows, result, timestamps


def register_exp65_visual_routes(app):

    @app.get("/exp65/visual")
    def exp65_visual_page():
        return render_template("exp65_visual.html")

    @app.get("/api/exp65/visual/trades")
    def exp65_visual_trades():
        try:
            rows, result, _ = load_research()
            trades = result["trades"]

            wins = sum(
                float(t["net_pnl_pct"]) > 0
                for t in trades
            )

            return jsonify({
                "status": "success",
                "symbol": "NVDA",
                "direction": "SHORT",
                "timeframe": "5m",
                "engine": "EXP65 V18",
                "candle_count": len(rows),
                "trade_count": len(trades),
                "winners": wins,
                "losers": len(trades) - wins,
                "total_net_pct": round(
                    sum(float(t["net_pnl_pct"]) for t in trades),
                    3
                ),
                "trades": trades,
                "research_only": True,
            })
        except Exception as exc:
            app.logger.exception("EXP65 trades error")
            return jsonify({
                "status": "error",
                "message": str(exc),
            }), 500

    @app.get("/api/exp65/visual/chart")
    def exp65_visual_chart():
        try:
            trade_id = request.args.get("trade_id", "")

            rows, result, timestamps = load_research()

            trade = next(
                (
                    t for t in result["trades"]
                    if t["trade_id"] == trade_id
                ),
                None
            )

            if trade is None:
                return jsonify({
                    "status": "error",
                    "message": "Trade not found",
                }), 404

            entry_i = timestamps[trade["entry_time"]]
            exit_i = timestamps[trade["exit_time"]]

            start = max(0, entry_i - 36)
            end = min(len(rows), exit_i + 37)

            candles = []

            for row in rows[start:end]:
                candles.append({
                    "time": row["timestamp"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0),
                })

            return jsonify({
                "status": "success",
                "trade": trade,
                "candles": candles,
                "research_only": True,
            })

        except Exception as exc:
            app.logger.exception("EXP65 chart error")
            return jsonify({
                "status": "error",
                "message": str(exc),
            }), 500


    @app.get("/api/exp65/visual/diagnostics")
    def exp65_visual_diagnostics():
        try:
            rows, result, indices = load_research()
            diagnostics = []

            for trade in result["trades"]:
                start = indices[trade["entry_time"]]
                end = indices[trade["exit_time"]]
                entry = float(trade["entry_price"])

                best = entry
                streak = 0
                warning_i = None

                for i in range(start + 1, end):
                    close = float(rows[i]["close"])
                    previous = float(rows[i - 1]["close"])
                    streak = streak + 1 if close > previous else 0
                    best = min(best, close)

                    giveback = (
                        (entry / best - 1) * 100
                        - (entry / close - 1) * 100
                    )

                    if streak >= 2 and giveback >= 0.10:
                        warning_i = i
                        break

                item = {
                    "trade_id": trade["trade_id"],
                    "warning_time": None,
                    "review_time": None,
                    "status": "NO_WARNING",
                    "review_net_pct": None,
                }

                if warning_i is not None:
                    item["warning_time"] = rows[warning_i]["timestamp"]

                    review_i = warning_i + 3

                    if review_i >= end:
                        item["status"] = "EXITED_EARLY"
                    else:
                        benchmark = min(
                            float(rows[j]["close"])
                            for j in range(start, warning_i + 1)
                        )

                        next_closes = [
                            float(rows[j]["close"])
                            for j in range(warning_i + 1, review_i + 1)
                        ]

                        recovered = min(next_closes) < benchmark
                        close = float(rows[review_i]["close"])

                        item["review_time"] = rows[review_i]["timestamp"]
                        item["status"] = (
                            "RECOVERED" if recovered
                            else "NOT_RECOVERED"
                        )
                        item["review_net_pct"] = round(
                            (entry / close - 1) * 100 - 0.20, 3
                        )

                diagnostics.append(item)

            return jsonify({
                "status": "success",
                "research_only": True,
                "diagnostics": diagnostics,
            })

        except Exception as exc:
            app.logger.exception("EXP65 diagnostics error")
            return jsonify({
                "status": "error",
                "message": str(exc),
            }), 500
