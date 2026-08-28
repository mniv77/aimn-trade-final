from flask import jsonify
def register_alerts_routes(app, db):
    @app.route("/api/alerts/latest")
    def alerts_latest():
        try:
            # Use db from closure - it's SQLAlchemy session
            result = db.execute("SELECT symbol, side, trail_pct, min_v_pct, price, created_at FROM alerts ORDER BY created_at DESC LIMIT 20")
            rows = result.fetchall()
            alerts = []
            for r in rows:
                alerts.append({"symbol": str(r[0]), "side": str(r[1]), "trail_pct": float(r[2] or 0), "min_v_pct": float(r[3] or 0), "price": float(r[4] or 0), "time": str(r[5])})
            return jsonify({"alerts": alerts, "count": len(alerts), "mode": "kiss_v3", "status": "live"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e), "alerts": [], "mode": "kiss_v3"})

    @app.route("/api/alerts/generate/<symbol>")
    def generate_alert(symbol):
        try:
            r = db.execute(f"SELECT trail_pct, min_v_pct FROM tuning_results WHERE symbol='{symbol}' AND mode='kiss_v3' ORDER BY created_at DESC LIMIT 1").fetchone()
            if not r: return jsonify({"error": f"Tune {symbol} first"}), 404
            db.execute(f"INSERT INTO alerts (symbol, side, trail_pct, min_v_pct, price) VALUES ('{symbol}', 'BUY', {r[0]}, {r[1]}, 0)")
            db.commit()
            return jsonify({"symbol": symbol, "side": "BUY", "trail_pct": float(r[0]), "min_v_pct": float(r[1]), "status": "generated"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500
