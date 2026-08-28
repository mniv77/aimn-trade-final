from flask import jsonify
def register_alerts_routes(app, db):
    @app.route("/api/alerts/latest")
    def alerts_latest():
        try:
            from sqlalchemy import text
            # Try db.session first, then db
            try:
                sess = db.session if hasattr(db, 'session') else db
                result = sess.execute(text("SELECT symbol, side, trail_pct, min_v_pct, price, created_at FROM alerts ORDER BY created_at DESC LIMIT 20"))
            except:
                # Fallback raw connection
                from app_sub.db import get_db_connection
                conn = get_db_connection()
                cur = conn[1] if isinstance(conn, tuple) else conn.cursor()
                cur.execute("SELECT symbol, side, trail_pct, min_v_pct, price, created_at FROM alerts ORDER BY created_at DESC LIMIT 20")
                rows = cur.fetchall()
                alerts = [{"symbol": str(r[0]), "side": str(r[1]), "trail_pct": float(r[2] or 0), "min_v_pct": float(r[3] or 0), "price": float(r[4] or 0), "time": str(r[5])} for r in rows]
                return jsonify({"alerts": alerts, "count": len(alerts), "mode": "kiss_v3", "status": "live"})

            rows = result.fetchall()
            alerts = [{"symbol": str(r[0]), "side": str(r[1]), "trail_pct": float(r[2] or 0), "min_v_pct": float(r[3] or 0), "price": float(r[4] or 0), "time": str(r[5])} for r in rows]
            return jsonify({"alerts": alerts, "count": len(alerts), "mode": "kiss_v3", "status": "live"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e), "alerts": [{"symbol":"QQQ","side":"BUY","trail_pct":0.03,"min_v_pct":0.002,"price":500,"time":"live"}], "mode": "kiss_v3", "status": "fallback"})

    @app.route("/api/alerts/generate/<symbol>")
    def generate_alert(symbol):
        try:
            from sqlalchemy import text
            sess = db.session if hasattr(db, 'session') else db
            r = sess.execute(text(f"SELECT trail_pct, min_v_pct FROM tuning_results WHERE symbol='{symbol}' AND mode='kiss_v3' ORDER BY created_at DESC LIMIT 1")).fetchone()
            if not r: return jsonify({"error": f"Tune {symbol} first"}), 404
            sess.execute(text(f"INSERT INTO alerts (symbol, side, trail_pct, min_v_pct, price) VALUES ('{symbol}', 'BUY', {r[0]}, {r[1]}, 0)"))
            sess.commit()
            return jsonify({"symbol": symbol, "side": "BUY", "trail_pct": float(r[0]), "min_v_pct": float(r[1]), "status": "generated"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500
