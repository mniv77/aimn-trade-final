from flask import request, jsonify
from sqlalchemy import text
def register_trades_comment_routes(app, db):
    @app.route("/api/trades/comment_losers", methods=["POST", "GET"])
    def comment_losers():
        if request.method == "GET":
            try:
                result = db.execute(text("SELECT symbol, COUNT(*) as c FROM trade_comments GROUP BY symbol"))
                rows = result.fetchall()
                return jsonify({"symbols": [{"symbol": r[0], "losers": r[1]} for r in rows]})
            except Exception as e:
                return jsonify({"error": str(e), "info": "POST {symbol, trades:[{pnl, gap, rsi, ai_comment}]} to save"})
        try:
            data = request.get_json()
            symbol = data.get("symbol", "QQQ")
            trades = data.get("trades", [])
            losers = [t for t in trades if t.get("pnl",0)<0]
            db.execute(text("CREATE TABLE IF NOT EXISTS trade_comments (id INT AUTO_INCREMENT PRIMARY KEY, symbol VARCHAR(20), pnl FLOAT, ai_comment TEXT, gap FLOAT, rsi FLOAT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            for t in losers[:100]:
                db.execute(text("INSERT INTO trade_comments (symbol, pnl, ai_comment, gap, rsi) VALUES (:s, :p, :c, :g, :r)"), {"s":symbol,"p":float(t.get("pnl",0)),"c":str(t.get("ai_comment",""))[:500],"g":float(t.get("gap",0)),"r":float(t.get("rsi",0))})
            db.commit()
            return jsonify({"count": len(losers), "total": len(trades), "message": f"Saved {len(losers)} loser comments for {symbol} - AI will avoid GAP/RSI/THIN next tuning"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/trade_chart_perfect/<symbol>")
    def trade_chart_perfect(symbol):
        from flask import render_template
        import json
        # Load trades for symbol from tuner
        try:
            import sys
            sys.path.insert(0, './engine')
            from tuner_perfect_v3 import perfect_tune
            best = perfect_tune(symbol)
            trades = best['trades'] if best else []
            # Convert to JSON for template
            trades_json = json.dumps([{"entry_time": t["entry_time"], "entry_price": t["entry_price"], "exit_time": t["exit_time"], "exit_price": t["exit_price"], "pnl": t["pnl"], "gap": t["gap"], "rsi": t["rsi"], "sma200": t["sma200"], "vol": t["vol"], "avg_vol": t["avg_vol"], "price": t["price"], "ai_comment": t.get("ai_comment","")} for t in trades[:100]])
            # Dummy candles for now - real would load
            candles_json = json.dumps([])
            return render_template('trade_chart_view_perfect_v3.html', symbol=symbol, trades_json=trades_json, candles_json=candles_json)
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"Error {e} <pre>{traceback.format_exc()}</pre>"
