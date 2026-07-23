# code_vision.py
"""
code_vision.py
FREE local replacement for ai_vision_check.py (no API cost).

Implements the SAME rules as the AI Vision prompt, numerically:
  STEP 1: Overall trend on 30m candles (UP / DOWN / SIDEWAYS)
  STEP 2: Trend filter — DOWN blocks LONG, UP blocks SHORT, SIDEWAYS blocks both
  STEP 3: Right-edge pattern on 5m candles (last 15 candles only):
          V-pattern (sharp drop + volume spike + 3+ recovery candles)
          OR momentum breakout (3+ consecutive candles, growing size + volume)
          LOW VOLUME at right edge = NOT_CONFIRMED

Drop-in replacement: same function name + signature as ai_vision_check.check_reversal.
Image paths are accepted but ignored (candle data is fetched directly).

SAFETY: never returns "ERROR" on data problems — returns NOT_CONFIRMED
so a failure can never open an unprotected trade.
"""

# ── Tunable thresholds ────────────────────────────────────────────
TREND_CANDLES      = 80    # 30m candles for trend (same as chart)
TREND_MIN_PCT      = 1.0   # net % move across 30m chart to call UP/DOWN
EDGE_WINDOW        = 15    # right-edge window on 5m (last N candles)
MIN_RECOVERY       = 3     # 3+ recovery candles required (AI rule)
VOL_SPIKE_MULT     = 1.8   # volume spike = 1.8x chart average
LOW_VOL_MULT       = 0.6   # right-edge avg vol below 0.6x chart avg = undecided
ATR_LEN            = 14
DROP_ATR_MULT      = 2.5   # sharp drop/rally = 2.5x ATR
MOMENTUM_MOVE_PCT  = 0.8   # momentum breakout total move (matches engine rule)


# ── Candle fetching (same sources as chart_renderer) ─────────────
def _fetch(symbol, timeframe, n):
    """Return candles ascending by time: list of dicts with o/h/l/c/v."""
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
                "o": float(r["open"]), "h": float(r["high"]),
                "l": float(r["low"]),  "c": float(r["close"]),
                "v": float(r["volume"] or 0),
            })
        except Exception:
            continue
    return out


# ── Helpers ───────────────────────────────────────────────────────
def _avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0

def _atr_pct(candles, length=ATR_LEN):
    """Average true range as % of last close."""
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = _avg(trs[-length:])
    last = candles[-1]["c"]
    return (atr / last * 100.0) if last else 0.0

def _is_green(c):
    return c["c"] > c["o"]

def _is_red(c):
    return c["c"] < c["o"]


# ── STEP 1: Trend on 30m ─────────────────────────────────────────
def _detect_trend(c30):
    """Swing-structure trend (fast: flips the moment a swing level breaks).
    Falls back to the old slow quartile-average method if trend_engine
    is unavailable. Returns (trend, reason_text)."""
    try:
        from trend_engine import analyze_trend
        t = analyze_trend(c30)
        return t["trend"], t["reason"]
    except Exception:
        pass
    # fallback: original quartile-average method
    closes = [c["c"] for c in c30]
    q = max(len(closes) // 4, 1)
    first_avg = _avg(closes[:q])
    last_avg  = _avg(closes[-q:])
    if not first_avg:
        return "SIDEWAYS", "no data"
    change_pct = (last_avg - first_avg) / first_avg * 100.0
    if change_pct >= TREND_MIN_PCT:
        return "UP", f"quartile {change_pct:+.2f}%"
    if change_pct <= -TREND_MIN_PCT:
        return "DOWN", f"quartile {change_pct:+.2f}%"
    return "SIDEWAYS", f"quartile {change_pct:+.2f}%"


# ── STEP 3: Right-edge patterns on 5m ────────────────────────────
def _edge_volume_ok(c5):
    chart_avg = _avg(c["v"] for c in c5)
    edge_avg  = _avg(c["v"] for c in c5[-5:])
    if chart_avg <= 0:
        return True, 1.0   # no volume data — don't block on volume alone
    return edge_avg >= LOW_VOL_MULT * chart_avg, (edge_avg / chart_avg)

def _v_pattern(c5, direction, atr_pct):
    """Sharp move + volume spike at extreme + 3+ recovery candles at right edge."""
    edge = c5[-EDGE_WINDOW:]
    chart_avg_vol = _avg(c["v"] for c in c5) or 1.0
    if direction == "LONG":
        i_ext = min(range(len(edge)), key=lambda i: edge[i]["l"])
        extreme = edge[i_ext]["l"]
        before = edge[:i_ext] or [edge[i_ext]]
        pre_ref = max(c["h"] for c in before)
        move_pct = (pre_ref - extreme) / extreme * 100.0 if extreme else 0.0
        recovery = edge[i_ext + 1:]
        good = sum(1 for c in recovery if _is_green(c))
    else:  # SHORT
        i_ext = max(range(len(edge)), key=lambda i: edge[i]["h"])
        extreme = edge[i_ext]["h"]
        before = edge[:i_ext] or [edge[i_ext]]
        pre_ref = min(c["l"] for c in before)
        move_pct = (extreme - pre_ref) / pre_ref * 100.0 if pre_ref else 0.0
        recovery = edge[i_ext + 1:]
        good = sum(1 for c in recovery if _is_red(c))
    # volume spike at the extreme (extreme candle or neighbor)
    lo, hi = max(0, i_ext - 1), min(len(edge), i_ext + 2)
    spike = max(c["v"] for c in edge[lo:hi]) / chart_avg_vol
    sharp = move_pct >= DROP_ATR_MULT * max(atr_pct, 0.05)
    if sharp and spike >= VOL_SPIKE_MULT and good >= MIN_RECOVERY:
        return True, (f"V-pattern: {move_pct:.2f}% move, volume spike "
                      f"{spike:.1f}x, {good} recovery candles at right edge")
    return False, (f"no V-pattern (move {move_pct:.2f}%, spike {spike:.1f}x, "
                   f"{good} recovery candles)")

def _momentum(c5, direction):
    """3 consecutive candles in direction, growing bodies, volume >= chart avg, move >= 0.8%."""
    if len(c5) < 4:
        return False, "not enough candles"
    last3 = c5[-3:]
    ok_dir = all(_is_green(c) for c in last3) if direction == "LONG" \
        else all(_is_red(c) for c in last3)
    bodies = [abs(c["c"] - c["o"]) for c in last3]
    growing = bodies[0] <= bodies[1] <= bodies[2] or bodies[2] >= 1.5 * _avg(bodies[:2])
    start = last3[0]["o"]
    move = (last3[-1]["c"] - start) / start * 100.0 if start else 0.0
    if direction == "SHORT":
        move = -move
    chart_avg_vol = _avg(c["v"] for c in c5) or 1.0
    vol_ok = _avg(c["v"] for c in last3) >= chart_avg_vol
    if ok_dir and growing and move >= MOMENTUM_MOVE_PCT and vol_ok:
        return True, f"momentum breakout: 3 candles, {move:.2f}% move, rising volume"
    return False, "no momentum breakout"


# ── Main entry point (drop-in for ai_vision_check.check_reversal) ─
def check_reversal(image_path, symbol, direction, image_path_5m=None):
    try:
        c30 = _fetch(symbol, "30m", TREND_CANDLES)
        c5  = _fetch(symbol, "5m", 60)
        if len(c30) < 20:
            return {"verdict": "NOT_CONFIRMED",
                    "reason": f"CODE-VISION DATA: only {len(c30)} 30m candles"}
        if len(c5) < EDGE_WINDOW:
            c5 = c30  # fall back to 30m for edge pattern (single-chart mode)

        # STEP 1 + 2: trend filter (no exceptions)
        trend, why = _detect_trend(c30)
        if trend == "SIDEWAYS":
            return {"verdict": "NOT_CONFIRMED",
                    "reason": f"TREND=SIDEWAYS ({why}). Sideways = no trade."}
        if trend == "DOWN" and direction == "LONG":
            return {"verdict": "NOT_CONFIRMED",
                    "reason": f"TREND=DOWN ({why}). Trend does not support LONG."}
        if trend == "UP" and direction == "SHORT":
            return {"verdict": "NOT_CONFIRMED",
                    "reason": f"TREND=UP ({why}). Trend does not support SHORT."}

        # Low volume at right edge = market undecided
        vol_ok, vol_ratio = _edge_volume_ok(c5)
        if not vol_ok:
            return {"verdict": "NOT_CONFIRMED",
                    "reason": (f"TREND={trend} ({why}). LOW VOLUME at right "
                               f"edge ({vol_ratio:.2f}x avg) = undecided.")}

        # STEP 3: right-edge pattern (V-pattern OR momentum breakout)
        atr = _atr_pct(c5)
        v_ok, v_msg = _v_pattern(c5, direction, atr)
        if v_ok:
            return {"verdict": "CONFIRMED",
                    "reason": f"TREND={trend} ({why}). Pattern: {v_msg}"}
        m_ok, m_msg = _momentum(c5, direction)
        if m_ok:
            return {"verdict": "CONFIRMED",
                    "reason": f"TREND={trend} ({why}). Pattern: {m_msg}"}
        return {"verdict": "NOT_CONFIRMED",
                "reason": f"TREND={trend} ({why}). Pattern: {v_msg}; {m_msg}"}

    except Exception as e:
        # SAFETY: never return ERROR — a failure must never open a trade
        return {"verdict": "NOT_CONFIRMED", "reason": f"CODE-VISION EXCEPTION: {e}"}


if __name__ == "__main__":
    import sys, json
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC/USD"
    direction = sys.argv[2] if len(sys.argv) > 2 else "LONG"
    print(json.dumps(check_reversal(None, symbol, direction), indent=2))