from flask import jsonify, request
from datetime import datetime
import sys
sys.path.insert(0, "/home/MeirNiv/aimn-trade-final")
from db import get_db_connection

def register_alerts_routes(app, db):
    @app.route("/api/alerts/latest")
    def alerts_latest():
        conn = get_db_connection()
        if isinstance(conn, tuple): conn, cur = conn
        else: cur = conn.cursor()
        cur.execute("SELECT symbol, side, trail_pct, min_v_pct, price, created_at FROM alerts ORDER BY created_at DESC LIMIT 20")
        rows = cur.fetchall()
        alerts = [{"symbol": r[0], "side": r[1], "trail_pct": r[2], "min_v_pct": r[3], "price": r[4], "time": str(r[5])} for r in rows]
        return jsonify({"alerts": alerts, "count": len(alerts), "mode": "kiss_v3"})

    @app.route("/api/alerts/generate/<symbol>")
    def generate_alert(symbol):
        # Use best params from tuning_results
        conn = get_db_connection()
        if isinstance(conn, tuple): conn, cur = conn
        else: cur = conn.cursor()
        cur.execute("SELECT trail_pct, min_v_pct FROM tuning_results WHERE symbol=%s AND mode='kiss_v3'", (symbol,))
        row = cur.fetchone()
        if not row: return jsonify({"error": "Tune first"}), 404
        # Generate OPEN alert
        cur.execute("INSERT INTO alerts (symbol, side, trail_pct, min_v_pct, price) VALUES (%s,%s,%s,%s,%s)",
                    (symbol, "BUY", row[0], row[1], 0))
        conn.commit()
        return jsonify({"symbol": symbol, "side": "BUY", "trail_pct": row[0], "min_v_pct": row[1], "status": "generated"})
