from flask import jsonify
import os, sys
project_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_home not in sys.path:
    sys.path.insert(0, project_home)
from app_sub.db import db_session
from sqlalchemy import text

def register_alerts_routes(app, db):
    @app.route("/api/alerts/latest")
    def alerts_latest():
        try:
            result = db_session.execute(text("SELECT symbol, side, trail_pct, min_v_pct, price, created_at FROM alerts ORDER BY created_at DESC LIMIT 20"))
            rows = result.fetchall()
            alerts = [{"symbol": r[0], "side": r[1], "trail_pct": float(r[2]) if r[2] else 0, "min_v_pct": float(r[3]) if r[3] else 0, "price": float(r[4]) if r[4] else 0, "time": str(r[5])} for r in rows]
            return jsonify({"alerts": alerts, "count": len(alerts), "mode": "kiss_v3", "status": "live"})
        except Exception as e:
            return jsonify({"error": str(e), "alerts": []})

    @app.route("/api/alerts/generate/<symbol>")
    def generate_alert(symbol):
        try:
            result = db_session.execute(text(f"SELECT trail_pct, min_v_pct FROM tuning_results WHERE symbol='{symbol}' AND mode='kiss_v3' ORDER BY created_at DESC LIMIT 1"))
            row = result.fetchone()
            if not row:
                return jsonify({"error": f"Tune {symbol} first"}), 404
            db_session.execute(text(f"INSERT INTO alerts (symbol, side, trail_pct, min_v_pct, price) VALUES ('{symbol}', 'BUY', {row[0]}, {row[1]}, 0)"))
            db_session.commit()
            return jsonify({"symbol": symbol, "side": "BUY", "trail_pct": float(row[0]), "min_v_pct": float(row[1]), "status": "generated"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
