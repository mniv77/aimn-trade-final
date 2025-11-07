from flask import request, jsonify
from . import bp

# UI timeframe -> backend timeframe
_TF_MAP = {"1m":"1Min","1":"1Min","1min":"1Min","5m":"5Min","15m":"15Min"}

@bp.get("/api/bars")
def api_bars():
    """GET /popup/api/bars?symbol=BTC/USD&tf=1m&limit=300"""
    try:
        # lazy import to avoid heavy deps at WSGI load time
        from ..market_data import fetch_bars

        symbol = request.args.get("symbol", "BTC/USD")
        tf_in  = (request.args.get("tf", "1m") or "1m").lower()
        tf     = _TF_MAP.get(tf_in, "1Min")

        try:
            limit = int(request.args.get("limit", "300"))
            limit = max(10, min(limit, 600))
        except Exception:
            limit = 300

        df = fetch_bars(symbol, timeframe=tf, limit=limit)
        if df is None or getattr(df, "empty", True):
            return jsonify({"ok": True, "bars": []})

        rows = df.to_dict(orient="records")
        # make timestamps JSON-safe
        for r in rows:
            t = r.get("t")
            if t is not None and not isinstance(t, str):
                try:
                    r["t"] = t.isoformat()
                except Exception:
                    r["t"] = str(t)

        return jsonify({"ok": True, "bars": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
