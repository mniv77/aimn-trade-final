# trend_engine.py
"""
trend_engine.py
Swing-structure trend detection — no API, pure math.

CONCEPTS
  Swing High: candle whose high is the highest among FRACTAL_N candles
              on each side. Swing Low: mirror.
  Trend from structure:
      UP       = last swing high > previous  AND last swing low > previous
      DOWN     = last swing high < previous  AND last swing low < previous
      SIDEWAYS = mixed structure
  FLIP: the exact candle where price BREAKS the last confirmed swing
        level against the current trend:
      UP  -> DOWN when close breaks below the last swing low
      DOWN-> UP   when close breaks above the last swing high

MAJOR trend = 30m candles.  MINOR trend = 5m candles.
GOLDEN SIGNAL (early entry): minor trend flips INTO the major trend's
direction  ->  buy the pullback / sell the bounce.

Usage:
    from trend_engine import analyze_trend, combined_signal
    t = analyze_trend(candles)          # candles: list of dicts o/h/l/c/v (+optional timestamp)
    s = combined_signal("BTC/USD")      # fetches 30m + 5m itself, returns full picture
"""

FRACTAL_N = 3          # candles on each side to confirm a swing point
MAX_SWINGS_KEPT = 12   # how many recent swing points to keep/report


# ── Candle fetching (same source as code_vision) ─────────────────
def _fetch(symbol, timeframe, n):
    rows = []
    if "/" in symbol:
        try:
            from engine.tuning.candle_fetcher import fetch_candles
            candles = fetch_candles(symbol, timeframe=timeframe, limit=n, broker="Gemini")
            if candles:
                candles.sort(key=lambda x: x["timestamp"])
                rows = candles[-n:]
        except Exception:
            rows = []
    if not rows:
        try:
            from db import get_db_connection
            conn, cur = get_db_connection()
            try:
                cur.execute(
                    "SELECT timestamp, open, high, low, close, volume FROM candles "
                    "WHERE symbol=%s AND timeframe=%s ORDER BY timestamp DESC LIMIT %s",
                    (symbol, timeframe, n))
                db_rows = cur.fetchall()
            finally:
                conn.close()
            rows = list(reversed(db_rows)) if db_rows else []
        except Exception:
            rows = []
    out = []
    for r in rows:
        try:
            out.append({
                "t": r.get("timestamp"),
                "o": float(r["open"]), "h": float(r["high"]),
                "l": float(r["low"]),  "c": float(r["close"]),
                "v": float(r.get("volume") or 0),
            })
        except Exception:
            continue
    return out


# ── Swing point detection (fractals) ─────────────────────────────
def find_swings(candles, n=FRACTAL_N):
    """Return list of swing points: {'i', 'type': 'H'|'L', 'price', 't'}, oldest first.
    The last n candles cannot be confirmed swings yet (need n candles after)."""
    swings = []
    for i in range(n, len(candles) - n):
        h = candles[i]["h"]; l = candles[i]["l"]
        if all(h >= candles[j]["h"] for j in range(i - n, i + n + 1) if j != i):
            swings.append({"i": i, "type": "H", "price": h, "t": candles[i].get("t")})
        elif all(l <= candles[j]["l"] for j in range(i - n, i + n + 1) if j != i):
            swings.append({"i": i, "type": "L", "price": l, "t": candles[i].get("t")})
    # collapse consecutive same-type swings: keep the more extreme one
    cleaned = []
    for s in swings:
        if cleaned and cleaned[-1]["type"] == s["type"]:
            if s["type"] == "H":
                if s["price"] >= cleaned[-1]["price"]:
                    cleaned[-1] = s
            else:
                if s["price"] <= cleaned[-1]["price"]:
                    cleaned[-1] = s
        else:
            cleaned.append(s)
    return cleaned[-MAX_SWINGS_KEPT:]


# ── Trend from swing structure ───────────────────────────────────
def _structure_trend(swings):
    """Classify trend from the last two swing highs + last two swing lows."""
    highs = [s for s in swings if s["type"] == "H"][-2:]
    lows  = [s for s in swings if s["type"] == "L"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "SIDEWAYS", "not enough swing points"
    hh = highs[1]["price"] > highs[0]["price"]
    hl = lows[1]["price"]  > lows[0]["price"]
    lh = highs[1]["price"] < highs[0]["price"]
    ll = lows[1]["price"]  < lows[0]["price"]
    if hh and hl:
        return "UP", f"HH {highs[1]['price']:.2f} + HL {lows[1]['price']:.2f}"
    if lh and ll:
        return "DOWN", f"LH {highs[1]['price']:.2f} + LL {lows[1]['price']:.2f}"
    return "SIDEWAYS", "mixed structure"


def analyze_trend(candles, n=FRACTAL_N):
    """Full trend picture for one timeframe.
    Returns dict: trend, reason, flip ('NONE'|'TO_UP'|'TO_DOWN'), flip_price,
                  last_swing_high, last_swing_low, swings, age (candles since last flip event)."""
    if len(candles) < n * 2 + 5:
        return {"trend": "SIDEWAYS", "reason": f"only {len(candles)} candles",
                "flip": "NONE", "flip_price": None,
                "last_swing_high": None, "last_swing_low": None, "swings": [], "age": None}
    swings = find_swings(candles, n)
    trend, reason = _structure_trend(swings)
    lsh = next((s["price"] for s in reversed(swings) if s["type"] == "H"), None)
    lsl = next((s["price"] for s in reversed(swings) if s["type"] == "L"), None)
    close = candles[-1]["c"]

    # TIEBREAKER: sharp stair-step moves confirm few swing points, leaving
    # structure "mixed" while the eye clearly sees a trend. Resolve with
    # (1) breakout/breakdown vs known swing levels, then (2) window slope.
    if trend == "SIDEWAYS":
        highs = [s["price"] for s in swings if s["type"] == "H"][-2:]
        lows  = [s["price"] for s in swings if s["type"] == "L"][-2:]
        closes = [c["c"] for c in candles]
        q = max(len(closes) // 4, 1)
        first_avg = sum(closes[:q]) / q
        last_avg  = sum(closes[-q:]) / q
        slope_pct = (last_avg - first_avg) / first_avg * 100.0 if first_avg else 0.0
        if lows and close < min(lows):
            trend = "DOWN"
            reason = f"breakdown: close {close:.2f} below swing lows {min(lows):.2f}"
        elif highs and close > max(highs):
            trend = "UP"
            reason = f"breakout: close {close:.2f} above swing highs {max(highs):.2f}"
        elif slope_pct <= -1.0:
            trend = "DOWN"
            reason = f"{reason}; slope {slope_pct:+.2f}%"
        elif slope_pct >= 1.0:
            trend = "UP"
            reason = f"{reason}; slope {slope_pct:+.2f}%"

    # FLIP detection: current close breaking the last confirmed swing level
    flip, flip_price = "NONE", None
    if trend == "UP" and lsl is not None and close < lsl:
        flip, flip_price, trend = "TO_DOWN", lsl, "DOWN"
        reason = f"FLIP: close {close:.2f} broke swing low {lsl:.2f}"
    elif trend == "DOWN" and lsh is not None and close > lsh:
        flip, flip_price, trend = "TO_UP", lsh, "UP"
        reason = f"FLIP: close {close:.2f} broke swing high {lsh:.2f}"

    # age: candles since the most recent swing point (freshness of structure)
    age = (len(candles) - 1 - swings[-1]["i"]) if swings else None

    # TURN detection (pullback ending): a FRESH swing point just confirmed,
    # and price already closed beyond that swing candle's opposite extreme.
    # turn_up  : newest swing is a LOW  + close > that candle's high
    # turn_down: newest swing is a HIGH + close < that candle's low
    turn = "NONE"
    if swings and age is not None and age <= n + 3:
        s_last = swings[-1]
        sc = candles[s_last["i"]]
        if s_last["type"] == "L" and close > sc["h"]:
            turn = "UP"
        elif s_last["type"] == "H" and close < sc["l"]:
            turn = "DOWN"

    return {"trend": trend, "reason": reason, "flip": flip, "flip_price": flip_price,
            "turn": turn, "last_swing_high": lsh, "last_swing_low": lsl,
            "swings": swings, "age": age}


# ── Combined major/minor signal (the golden rule) ────────────────
def combined_signal(symbol, major_tf="30m", minor_tf="5m",
                    major_n=100, minor_n=80):
    """Returns the full two-layer picture and an entry recommendation.
    ENTRY_LONG : major UP   and minor flipped TO_UP   (pullback ended)
    ENTRY_SHORT: major DOWN and minor flipped TO_DOWN (bounce ended)
    EXIT_LONG / EXIT_SHORT: major trend itself flipped
    else WAIT."""
    c_major = _fetch(symbol, major_tf, major_n)
    c_minor = _fetch(symbol, minor_tf, minor_n)
    major = analyze_trend(c_major)
    minor = analyze_trend(c_minor)

    signal = "WAIT"
    why = f"major={major['trend']}, minor={minor['trend']}"
    if major["flip"] == "TO_DOWN":
        signal, why = "EXIT_LONG", f"MAJOR flip to DOWN: {major['reason']}"
    elif major["flip"] == "TO_UP":
        signal, why = "EXIT_SHORT", f"MAJOR flip to UP: {major['reason']}"
    elif major["trend"] == "UP" and (minor["flip"] == "TO_UP" or minor["turn"] == "UP"):
        signal, why = "ENTRY_LONG", ("major UP + minor pullback ended "
                                     f"(turn={minor['turn']}, flip={minor['flip']})")
    elif major["trend"] == "DOWN" and (minor["flip"] == "TO_DOWN" or minor["turn"] == "DOWN"):
        signal, why = "ENTRY_SHORT", ("major DOWN + minor bounce ended "
                                      f"(turn={minor['turn']}, flip={minor['flip']})")

    return {"symbol": symbol, "signal": signal, "why": why,
            "major": {k: major[k] for k in ("trend", "reason", "flip", "turn",
                     "last_swing_high", "last_swing_low", "age")},
            "minor": {k: minor[k] for k in ("trend", "reason", "flip", "turn",
                     "last_swing_high", "last_swing_low", "age")}}


if __name__ == "__main__":
    import sys, json
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC/USD"
    print(json.dumps(combined_signal(symbol), indent=2, default=str))