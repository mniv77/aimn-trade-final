from flask import request, jsonify, render_template
from sqlalchemy import text
import json, os

def register_trades_comment_routes(app, db):
    @app.route("/api/trades/comment_losers", methods=["POST", "GET"])
    def comment_losers():
        if request.method == "GET":
            try:
                result = db.execute(text("SELECT symbol, COUNT(*) as c FROM trade_comments GROUP BY symbol"))
                rows = result.fetchall()
                return jsonify({"symbols": [{"symbol": r[0], "losers": r[1]} for r in rows], "total_losers": sum(r[1] for r in rows) if rows else 0})
            except Exception as e:
                return jsonify({"error": str(e)})
        try:
            data = request.get_json()
            symbol = data.get("symbol", "QQQ")
            trades = data.get("trades", [])
            losers = [t for t in trades if t.get("pnl",0)<0]
            db.execute(text("CREATE TABLE IF NOT EXISTS trade_comments (id INT AUTO_INCREMENT PRIMARY KEY, symbol VARCHAR(20), pnl FLOAT, ai_comment TEXT, gap FLOAT, rsi FLOAT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            for t in losers[:100]:
                db.execute(text("INSERT INTO trade_comments (symbol, pnl, ai_comment, gap, rsi) VALUES (:s, :p, :c, :g, :r)"), {"s":symbol,"p":float(t.get("pnl",0)),"c":str(t.get("ai_comment",""))[:500],"g":float(t.get("gap",0)),"r":float(t.get("rsi",0))})
            db.commit()
            return jsonify({"count": len(losers), "total": len(trades), "message": f"Saved {len(losers)}"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/trade_chart_perfect/<symbol>")
    def trade_chart_perfect(symbol):
        try:
            # FAST path - don't run tuner live, use last result file if exists
            import yfinance as yf, pandas as pd
            # Load 3mo candles fast
            df = yf.download(symbol, period="3mo", interval="1h", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            candles = []
            for idx, row in df.tail(200).iterrows():
                candles.append({"time": int(idx.timestamp()), "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
            # Try load cached trades from /tmp/last_tune_{symbol}.json
            trades = []
            summary = "Run tuner/run/QQQ first to cache"
            cache_path = f"/tmp/last_tune_{symbol}.json"
            if os.path.exists(cache_path):
                with open(cache_path,'r') as f:
                    data = json.load(f)
                    trades = data.get('trades',[])[:150]
                    summary = data.get('summary','')
            else:
                # Quick demo trades - run lightweight simulation
                summary = f"Live demo - run /tuner/run/{symbol} to cache full 198 trades"
                # Simulate 5 demo trades with AI comments
                for i in range(5):
                    trades.append({"entry_time": str(df.index[-10-i]), "entry_price": float(df['Close'].iloc[-10-i]), "exit_time": str(df.index[-5-i]), "exit_price": float(df['Close'].iloc[-5-i])*1.01, "pnl": 1.5, "gap": 0.2, "rsi": 65, "sma200": float(df['Close'].tail(200).mean()), "vol": 1000000, "avg_vol": 2000000, "price": float(df['Close'].iloc[-10-i]), "ai_comment": "WINNER"})
                    trades.append({"entry_time": str(df.index[-20-i]), "entry_price": float(df['Close'].iloc[-20-i]), "exit_time": str(df.index[-15-i]), "exit_price": float(df['Close'].iloc[-15-i])*0.98, "pnl": -1.7, "gap": 0.1, "rsi": 67, "sma200": float(df['Close'].tail(200).mean()), "vol": 100000, "avg_vol": 2000000, "price": float(df['Close'].iloc[-20-i]), "ai_comment": "LOSER-SMALL-LOSS part of 67% game"})
            trades_json = json.dumps(trades)
            candles_json = json.dumps(candles)
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
            # Cache to file for fast chart
            import json
            cache = {"summary": f"BEST trail={best['trail']} min_v={best['min_v']} WR={best['wr']*100:.1f}% total={best['total']:.1f}% count={best['count']}", "trades": best['trades'][:150], "best": best}
            # Convert timestamps to string for JSON
            with open(f"/tmp/last_tune_{symbol}.json",'w') as f:
                json.dump(cache, f, default=str)
            return jsonify({"symbol": symbol, "best": {"trail": best['trail'], "min_v": best['min_v'], "wr": best['wr'], "total": best['total'], "count": best['count']}, "losers": best['losers'][:10], "cached": f"/tmp/last_tune_{symbol}.json", "chart_url": f"/trade_chart_perfect/{symbol}"})
        except Exception as e:
            import traceback; return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500
