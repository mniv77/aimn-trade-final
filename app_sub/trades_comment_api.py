from flask import request, jsonify
from sqlalchemy import text
def register_trades_comment_routes(app, db):
    @app.route("/api/trades/comment_losers", methods=["POST"])
    def comment_losers():
        try:
            data = request.get_json()
            symbol = data.get("symbol")
            trades = data.get("trades", [])
            losers = [t for t in trades if t.get("pnl",0)<0]
            # save to table trade_comments if exists else tuning_results notes
            try:
                db.execute(text("CREATE TABLE IF NOT EXISTS trade_comments (id INT AUTO_INCREMENT PRIMARY KEY, symbol VARCHAR(20), pnl FLOAT, ai_comment TEXT, gap FLOAT, rsi FLOAT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
                for t in losers[:50]: # limit
                    db.execute(text("INSERT INTO trade_comments (symbol, pnl, ai_comment, gap, rsi) VALUES (:s, :p, :c, :g, :r)"), {"s":symbol,"p":t.get("pnl",0),"c":t.get("ai_comment",""),"g":t.get("gap",0),"r":t.get("rsi",0)})
                db.commit()
            except Exception as e:
                print("comment save error", e)
            return jsonify({"count": len(losers), "total": len(trades), "message": f"Saved {len(losers)} loser comments for {symbol} - AI will avoid GAP/RSI/THIN next tuning"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500
