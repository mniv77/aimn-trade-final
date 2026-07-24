# data_factory.py
"""
data_factory.py
Builds and grows the ML dataset from Gemini ground-truth candles.

Every 30m bar x direction x symbol becomes one labeled example:
  FEATURES  computed with NO LOOK-AHEAD (window ends at that bar), using the
            SAME trend_engine the live system uses
  LABELS    what price actually did next: +2h/+6h/+24h forward returns,
            max favorable / adverse excursion over next 6h
Idempotent: PRIMARY KEY (symbol, ts, direction) + INSERT IGNORE, so running
it daily (scheduled task) only appends new bars. History + live accumulation
in one script.

Usage:
    python3 data_factory.py            # all 4 crypto symbols
    python3 data_factory.py BTC/USD    # one symbol
"""

import sys
from trend_engine import analyze_trend

SYMBOLS   = ["BTC/USD", "ETH/USD", "SOL/USD", "LINK/USD"]
TREND_W   = 80     # 30m bars for trend/range features (matches code_vision)
CTX_W     = 100    # 1hr bars for context trend
EDGE_W    = 15     # right-edge pattern window (matches code_vision)
H_2H, H_6H, H_24H = 4, 12, 48   # label horizons in 30m bars
WARMUP    = TREND_W + 5

DDL = """
CREATE TABLE IF NOT EXISTS ml_dataset (
    symbol        VARCHAR(20)  NOT NULL,
    ts            DATETIME     NOT NULL,
    direction     VARCHAR(5)   NOT NULL,
    close         DOUBLE,
    trend30       VARCHAR(10),
    trend30_flip  VARCHAR(10),
    trend30_age   INT,
    trend1h       VARCHAR(10),
    pos_in_range  DOUBLE,
    vol_edge_ratio DOUBLE,
    vol_spike     DOUBLE,
    atr_pct       DOUBLE,
    v_move_pct    DOUBLE,
    v_recovery    INT,
    momentum3     DOUBLE,
    rsi14         DOUBLE,
    ret_1bar      DOUBLE,
    ret_4bar      DOUBLE,
    rules_verdict VARCHAR(15),
    fwd_ret_2h    DOUBLE,
    fwd_ret_6h    DOUBLE,
    fwd_ret_24h   DOUBLE,
    mfe_6h        DOUBLE,
    mae_6h        DOUBLE,
    PRIMARY KEY (symbol, ts, direction)
)
"""


def _fetch(symbol, timeframe, n):
    from engine.tuning.candle_fetcher import fetch_candles
    c = fetch_candles(symbol, timeframe=timeframe, limit=n, broker="Gemini")
    c.sort(key=lambda x: x["timestamp"])
    return [{"t": x["timestamp"], "o": float(x["open"]), "h": float(x["high"]),
             "l": float(x["low"]), "c": float(x["close"]),
             "v": float(x.get("volume") or 0)} for x in c]


def _rsi14(closes):
    if len(closes) < 15:
        return 50.0
    gains, losses = [], []
    for i in range(-14, 0):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag, al = sum(gains) / 14, sum(losses) / 14
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - 100 / (1 + rs)


def _atr_pct(c, length=14):
    if len(c) < 2:
        return 0.0
    trs = []
    for i in range(1, len(c)):
        h, l, pc = c[i]["h"], c[i]["l"], c[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[-length:]) / min(len(trs), length)
    return atr / c[-1]["c"] * 100 if c[-1]["c"] else 0.0


def _features(win30, ctx1h, direction):
    """All features from a 30m window (ending at decision bar) + 1hr context."""
    close = win30[-1]["c"]
    t30 = analyze_trend(win30[-TREND_W:])
    t1h = analyze_trend(ctx1h[-CTX_W:]) if len(ctx1h) >= 30 else {"trend": "SIDEWAYS"}

    rng_hi = max(c["h"] for c in win30[-TREND_W:])
    rng_lo = min(c["l"] for c in win30[-TREND_W:])
    pos = (close - rng_lo) / (rng_hi - rng_lo) if rng_hi > rng_lo else 0.5

    vols = [c["v"] for c in win30[-TREND_W:]]
    avg_v = (sum(vols) / len(vols)) or 1e-9
    vol_edge = sum(vols[-5:]) / 5 / avg_v

    edge = win30[-EDGE_W:]
    if direction == "LONG":
        i_ext = min(range(len(edge)), key=lambda i: edge[i]["l"])
        extreme = edge[i_ext]["l"]
        pre = max((c["h"] for c in edge[:i_ext]), default=extreme)
        v_move = (pre - extreme) / extreme * 100 if extreme else 0.0
        rec = sum(1 for c in edge[i_ext + 1:] if c["c"] > c["o"])
    else:
        i_ext = max(range(len(edge)), key=lambda i: edge[i]["h"])
        extreme = edge[i_ext]["h"]
        pre = min((c["l"] for c in edge[:i_ext]), default=extreme)
        v_move = (extreme - pre) / pre * 100 if pre else 0.0
        rec = sum(1 for c in edge[i_ext + 1:] if c["c"] < c["o"])
    lo, hi = max(0, i_ext - 1), min(len(edge), i_ext + 2)
    spike = max(c["v"] for c in edge[lo:hi]) / avg_v

    last3 = win30[-3:]
    sgn = 1 if direction == "LONG" else -1
    mom3 = sgn * (last3[-1]["c"] - last3[0]["o"]) / last3[0]["o"] * 100 if last3[0]["o"] else 0.0

    closes = [c["c"] for c in win30]
    ret1 = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 and closes[-2] else 0.0
    ret4 = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) > 4 and closes[-5] else 0.0

    # what would the current rule gate say (trend filter + range guard only;
    # volume/pattern gates encoded separately as features)
    verdict = "PASS"
    tr = t30["trend"]
    if tr == "SIDEWAYS":
        verdict = "BLOCK_TREND"
    elif tr == "DOWN" and direction == "LONG":
        verdict = "BLOCK_TREND"
    elif tr == "UP" and direction == "SHORT":
        verdict = "BLOCK_TREND"
    elif direction == "LONG" and pos >= 0.80:
        verdict = "BLOCK_RANGE"
    elif direction == "SHORT" and pos <= 0.20:
        verdict = "BLOCK_RANGE"

    return {
        "close": close,
        "trend30": t30["trend"], "trend30_flip": t30.get("flip", "NONE"),
        "trend30_age": t30.get("age") or 0, "trend1h": t1h["trend"],
        "pos_in_range": round(pos, 4), "vol_edge_ratio": round(vol_edge, 3),
        "vol_spike": round(spike, 3), "atr_pct": round(_atr_pct(win30), 4),
        "v_move_pct": round(v_move, 4), "v_recovery": rec,
        "momentum3": round(mom3, 4), "rsi14": round(_rsi14(closes), 2),
        "ret_1bar": round(ret1, 4), "ret_4bar": round(ret4, 4),
        "rules_verdict": verdict,
    }


def _labels(c30, i, direction):
    """Direction-signed forward outcomes from bar i's close (no fees)."""
    entry = c30[i]["c"]
    sgn = 1 if direction == "LONG" else -1

    def fwd(h):
        j = i + h
        if j >= len(c30):
            return None
        return sgn * (c30[j]["c"] - entry) / entry * 100

    horizon = c30[i + 1:i + 1 + H_6H]
    if direction == "LONG":
        mfe = max((c["h"] - entry) / entry * 100 for c in horizon)
        mae = min((c["l"] - entry) / entry * 100 for c in horizon)
    else:
        mfe = max((entry - c["l"]) / entry * 100 for c in horizon)
        mae = min((entry - c["h"]) / entry * 100 for c in horizon)
    return {"fwd_ret_2h": fwd(H_2H), "fwd_ret_6h": fwd(H_6H),
            "fwd_ret_24h": fwd(H_24H),
            "mfe_6h": round(mfe, 4), "mae_6h": round(mae, 4)}


def harvest(symbol):
    from db import get_db_connection
    c30 = _fetch(symbol, "30m", 3000)
    c1h = _fetch(symbol, "1hr", 3000)
    if len(c30) < WARMUP + H_24H + 2:
        print(f"{symbol}: not enough 30m candles ({len(c30)})")
        return 0

    conn, cur = get_db_connection()
    cur.execute(DDL)
    rows = 0
    j1h = 0
    cols = None
    for i in range(WARMUP, len(c30) - H_24H - 1):
        now = c30[i]["t"]
        while j1h < len(c1h) and c1h[j1h]["t"] <= now:
            j1h += 1
        win30 = c30[:i + 1]
        ctx1h = c1h[:j1h]
        for direction in ("LONG", "SHORT"):
            f = _features(win30, ctx1h, direction)
            lab = _labels(c30, i, direction)
            if lab["fwd_ret_24h"] is None:
                continue
            rec = {"symbol": symbol, "ts": now, "direction": direction, **f, **lab}
            if cols is None:
                cols = list(rec.keys())
                sql = ("INSERT IGNORE INTO ml_dataset (" + ",".join(cols) +
                       ") VALUES (" + ",".join(["%s"] * len(cols)) + ")")
            cur.execute(sql, [rec[c] for c in cols])
            rows += cur.rowcount
    conn.commit()
    conn.close()
    print(f"{symbol}: inserted {rows} new rows")
    return rows


if __name__ == "__main__":
    targets = [sys.argv[1]] if len(sys.argv) > 1 else SYMBOLS
    total = sum(harvest(s) for s in targets)
    print(f"TOTAL new rows: {total}")