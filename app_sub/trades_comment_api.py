from flask import request, jsonify, render_template
from sqlalchemy import text
import json, os, pathlib

CACHE_DIR = pathlib.Path("/home/MeirNiv/aimn-trade-final/tmp_cache")
CACHE_DIR.mkdir(exist_ok=True)

def register_trades_comment_routes(app, db):
    @app.route("/api/trades/comment_losers", methods=["POST", "GET"])
    def comment_losers():
        if request.method == "GET":
            try:
                result = db.execute(text("SELECT symbol, COUNT(*) as c FROM trade_comments GROUP BY symbol"))
                rows = result.fetchall()
                return jsonify({"symbols": [{"symbol": r[0], "losers": r[1]} for r in rows]})
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
            return jsonify({"count": len(losers)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/trade_chart_perfect/<symbol>")
    def trade_chart_perfect(symbol):
        try:
            # FAST - no yfinance on page load, use cache file in project
            cache_file = CACHE_DIR / f"last_tune_{symbol}.json"
            candles_file = CACHE_DIR / f"candles_{symbol}.json"
            trades = []
            candles = []
            summary = f"No cache for {symbol} - visit /tuner/run/{symbol} first (takes 60s)"
            if cache_file.exists():
                with open(cache_file,'r') as f:
                    data = json.load(f)
                    trades = data.get('trades',[])[:150]
                    summary = data.get('summary','')
            if candles_file.exists():
                with open(candles_file,'r') as f:
                    candles = json.load(f)
            else:
                # Demo candles if no cache
                candles = [{"time": 1700000000+i*3600, "open": 500+i, "high": 505+i, "low": 498+i, "close": 502+i} for i in range(200)]
            trades_json = json.dumps(trades, default=str)
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
            from tuner_perfect_v3 import perfect_tune, load_data
            best = perfect_tune(symbol)
            # Save trades cache PERSISTENT
            cache = {"summary": f"BEST trail={best['trail']} min_v={best['min_v']} WR={best['wr']*100:.1f}% total={best['total']:.1f}% count={best['count']}", "trades": best['trades'][:150]}
            with open(CACHE_DIR / f"last_tune_{symbol}.json",'w') as f:
                json.dump(cache, f, default=str)
            # Save candles too
            try:
                df = load_data(symbol, period="3mo")
                candles = []
                for idx, row in df.tail(200).iterrows():
                    candles.append({"time": int(idx.timestamp()), "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                with open(CACHE_DIR / f"candles_{symbol}.json",'w') as f:
                    json.dump(candles, f)
            except:
                pass
            return jsonify({"symbol": symbol, "best": {"trail": best['trail'], "min_v": best['min_v'], "wr": best['wr'], "total": best['total'], "count": best['count']}, "losers": best['losers'][:10], "chart_url": f"/trade_chart_perfect/{symbol}", "summary": cache["summary"]})
        except Exception as e:
            import traceback; return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500
