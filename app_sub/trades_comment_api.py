from flask import request, jsonify, render_template
from sqlalchemy import text
import json

def register_trades_comment_routes(app, db):
    @app.route("/api/trades/comment_losers", methods=["POST", "GET"])
    def comment_losers():
        if request.method == "GET":
            try:
                result = db.execute(text("SELECT symbol, COUNT(*) as c FROM trade_comments GROUP BY symbol"))
                rows = result.fetchall()
                return jsonify({"symbols": [{"symbol": r[0], "losers": r[1]} for r in rows], "total_losers": sum(r[1] for r in rows)})
            except Exception as e:
                return jsonify({"error": str(e), "info": "POST {symbol, trades:[{pnl, gap, rsi, ai_comment}]}"})
        try:
            data = request.get_json()
            symbol = data.get("symbol", "QQQ")
            trades = data.get("trades", [])
            losers = [t for t in trades if t.get("pnl",0)<0]
            db.execute(text("CREATE TABLE IF NOT EXISTS trade_comments (id INT AUTO_INCREMENT PRIMARY KEY, symbol VARCHAR(20), pnl FLOAT, ai_comment TEXT, gap FLOAT, rsi FLOAT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            for t in losers[:100]:
                db.execute(text("INSERT INTO trade_comments (symbol, pnl, ai_comment, gap, rsi) VALUES (:s, :p, :c, :g, :r)"), {"s":symbol,"p":float(t.get("pnl",0)),"c":str(t.get("ai_comment",""))[:500],"g":float(t.get("gap",0)),"r":float(t.get("rsi",0))})
            db.commit()
            return jsonify({"count": len(losers), "total": len(trades), "message": f"Saved {len(losers)} loser comments for {symbol}"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/trade_chart_perfect/<symbol>")
    def trade_chart_perfect(symbol):
        try:
            import sys
            sys.path.insert(0, './engine')
            sys.path.insert(0, '.')
            from tuner_perfect_v3 import perfect_tune, load_data
            import pandas as pd
            best = perfect_tune(symbol)
            trades = best['trades'][:150] if best else []
            # Load candles for chart
            df = load_data(symbol, period="3mo")
            candles = []
            for idx, row in df.tail(200).iterrows():
                candles.append({"time": int(idx.timestamp()), "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
            trades_json = json.dumps([{"entry_time": t["entry_time"], "entry_price": t["entry_price"], "exit_time": t["exit_time"], "exit_price": t["exit_price"], "pnl": t["pnl"], "gap": t["gap"], "rsi": t["rsi"], "sma200": t["sma200"], "vol": t["vol"], "avg_vol": t["avg_vol"], "price": t["price"], "ai_comment": t.get("ai_comment",""), "reason": t.get("reason","")} for t in trades])
            candles_json = json.dumps(candles)
            summary = f"BEST trail={best['trail']} min_v={best['min_v']} WR={best['wr']*100:.1f}% total={best['total']:.1f}% count={best['count']}" if best else "No trades"
            return render_template('trade_chart_view_perfect_v3.html', symbol=symbol, trades_json=trades_json, candles_json=candles_json, summary=summary)
        except Exception as e:
            import traceback
            return f"<h1>Error {e}</h1><pre>{traceback.format_exc()}</pre>"

    @app.route("/tuner/run/<symbol>")
    def tuner_run(symbol):
        try:
            import sys
            sys.path.insert(0, './engine')
            from tuner_perfect_v3 import perfect_tune
            best = perfect_tune(symbol)
            return jsonify({"symbol": symbol, "best": {"trail": best['trail'], "min_v": best['min_v'], "wr": best['wr'], "total": best['total'], "count": best['count']}, "losers": best['losers'][:10]})
        except Exception as e:
            import traceback; return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500
