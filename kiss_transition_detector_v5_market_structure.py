"""KISS Transition Detector V5 — Market Structure Transition, research only.

Research-only. No orders, no DB writes.

Purpose:
    V4 tried to approach the official 30m MA-state transition with increasingly
    strict confirmation. That reduced false alarms but remained too early.

V5 changes the target. It does NOT try to predict the 30m MA state transition.
It studies the actual price-structure transition first.

Target sequence (LONG -> SHORT):
    higher high -> higher low -> higher high -> failed higher high
    -> lower high -> break prior higher low -> lower low

Mirror target (SHORT -> LONG):
    lower low -> lower high -> lower low -> failed lower low
    -> higher low -> break prior lower high -> higher high

Timestamps:
    T0 = first meaningful weakness against the old structure
    T1 = failed continuation / failed extreme
    T2 = first opposite swing
    T3 = break of prior supporting structure
    T4 = confirmation of the new structure
    T5 = official 30m LONG<->SHORT MA-state transition

The key research question is whether T4 occurs materially before T5,
and whether T4 is a cleaner definition of the real transition than the
lagging 30m MA-state change.

This file is intentionally standalone so existing V4 and unrelated local
changes are not touched.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
MIN_5M_HISTORY = 24
SWING_LOOKBACK = 3
SEARCH_BACK = 24
FORWARD_MINUTES = 180
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("+00:00", "")).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cur.fetchall() or []
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5],
            }
            d["timestamp"] = ts(d["timestamp"])
            for k in ("open", "high", "low", "close", "volume"):
                d[k] = num(d[k])
            out.append(d)
        return out
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def opposite(s: str) -> str:
    return "SHORT" if s == "LONG" else "LONG"


def direct_transitions(rows30: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    out: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(rows30)):
        a, b = states[i - 1], states[i]
        if a in ("LONG", "SHORT") and b == opposite(a):
            out.append({
                "index": i,
                "known_time": rows30[i]["timestamp"] + timedelta(minutes=30),
                "from": a,
                "to": b,
                "price": rows30[i]["close"],
            })
    return out


def _local_high(h: Sequence[float], i: int) -> bool:
    if i < SWING_LOOKBACK or i + SWING_LOOKBACK >= len(h):
        return False
    return h[i] >= max(h[i - SWING_LOOKBACK:i]) and h[i] >= max(h[i + 1:i + SWING_LOOKBACK + 1])


def _local_low(l: Sequence[float], i: int) -> bool:
    if i < SWING_LOOKBACK or i + SWING_LOOKBACK >= len(l):
        return False
    return l[i] <= min(l[i - SWING_LOOKBACK:i]) and l[i] <= min(l[i + 1:i + SWING_LOOKBACK + 1])


def _candidate_swings(bars: Sequence[Dict[str, Any]]) -> Tuple[List[int], List[int]]:
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    highs = [i for i in range(len(bars)) if _local_high(h, i)]
    lows = [i for i in range(len(bars)) if _local_low(l, i)]
    return highs, lows


def structure_transition(bars: Sequence[Dict[str, Any]], prior: str) -> Dict[str, Any]:
    """Find the strongest causal market-structure transition visible so far.

    Swing points are only accepted after SWING_LOOKBACK completed bars on the
    right, so the detector does not peek into future data when a stage fires.
    The stages are built from distinct later observations.
    """
    if len(bars) < MIN_5M_HISTORY:
        return {"stage": 0}

    c = [b["close"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    highs, lows = _candidate_swings(bars)

    # Work only with confirmed swings. The most recent possible swing is
    # deliberately excluded if it lacks right-side confirmation.
    if prior == "LONG":
        # T0: a confirmed lower close after an established bullish push.
        if len(highs) < 2 or len(lows) < 1:
            return {"stage": 0}
        hh1 = highs[-2]
        hh2 = highs[-1]
        if h[hh2] <= h[hh1]:
            return {"stage": 0}
        prior_lows = [x for x in lows if x < hh2]
        if not prior_lows:
            return {"stage": 0}
        hl = prior_lows[-1]
        if c[-1] >= h[hh2]:
            return {"stage": 0}
        t0 = len(bars) - 1

        # T1: price fails to make a new high after T0. A confirmed lower high
        # is the first structural sign that continuation has failed.
        post_highs = [x for x in highs if x > hh2 and x > t0 - SEARCH_BACK]
        if post_highs:
            return {"stage": 0}
        # A later confirmed high below HH2 is required.
        later_highs = [x for x in highs if x > t0 - SEARCH_BACK and h[x] < h[hh2]]
        if not later_highs:
            return {"stage": 1, "t0": t0, "hh": hh2, "hl": hl}
        lh = later_highs[-1]

        # T2: close breaks below the prior higher-low structure.
        break_idx = next((j for j in range(lh + 1, len(c)) if c[j] < l[hl]), None)
        if break_idx is None:
            return {"stage": 2, "t0": t0, "hh": hh2, "hl": hl, "lh": lh}

        # T3: a later confirmed lower low below the broken HL.
        later_lows = [x for x in lows if x > break_idx and l[x] < l[hl]]
        if not later_lows:
            return {"stage": 3, "t0": t0, "hh": hh2, "hl": hl, "lh": lh, "break": break_idx}
        ll = later_lows[-1]

        # T4: after the lower low, a confirmed lower high. This is the new
        # bearish structure confirmation. It must be later than LL.
        new_highs = [x for x in highs if x > ll and h[x] < h[lh]]
        if not new_highs:
            return {"stage": 4, "t0": t0, "hh": hh2, "hl": hl, "lh": lh, "break": break_idx, "ll": ll}
        nh = new_highs[-1]
        return {
            "stage": 5, "t0": t0, "hh": hh2, "hl": hl, "lh": lh,
            "break": break_idx, "ll": ll, "new_high": nh,
        }

    # Mirror: SHORT -> LONG.
    if len(lows) < 2 or len(highs) < 1:
        return {"stage": 0}
    ll1 = lows[-2]
    ll2 = lows[-1]
    if l[ll2] >= l[ll1]:
        return {"stage": 0}
    prior_highs = [x for x in highs if x < ll2]
    if not prior_highs:
        return {"stage": 0}
    lh = prior_highs[-1]
    if c[-1] <= l[ll2]:
        return {"stage": 0}
    t0 = len(bars) - 1

    later_lows = [x for x in lows if x > t0 - SEARCH_BACK and l[x] > l[ll2]]
    if not later_lows:
        return {"stage": 1, "t0": t0, "ll": ll2, "lh": lh}
    hl = later_lows[-1]

    break_idx = next((j for j in range(hl + 1, len(c)) if c[j] > h[lh]), None)
    if break_idx is None:
        return {"stage": 2, "t0": t0, "ll": ll2, "lh": lh, "hl": hl}

    later_highs = [x for x in highs if x > break_idx and h[x] > h[lh]]
    if not later_highs:
        return {"stage": 3, "t0": t0, "ll": ll2, "lh": lh, "hl": hl, "break": break_idx}
    hh = later_highs[-1]

    new_lows = [x for x in lows if x > hh and l[x] > l[hl]]
    if not new_lows:
        return {"stage": 4, "t0": t0, "ll": ll2, "lh": lh, "hl": hl, "break": break_idx, "hh": hh}
    nl = new_lows[-1]
    return {
        "stage": 5, "t0": t0, "ll": ll2, "lh": lh, "hl": hl,
        "break": break_idx, "hh": hh, "new_low": nl,
    }


def stage_time(rows5: Sequence[Dict[str, Any]], event_time: datetime, prior: str, target_stage: int) -> Optional[datetime]:
    start = event_time - timedelta(minutes=LOOKBACK_MINUTES)
    best: Optional[datetime] = None
    for bar in rows5:
        obs = bar["timestamp"] + timedelta(minutes=5)
        if obs < start or obs > event_time:
            continue
        hist = [r for r in rows5 if r["timestamp"] + timedelta(minutes=5) <= obs]
        recent = hist[-(SEARCH_BACK + 10):]
        result = structure_transition(recent, prior)
        if result.get("stage", 0) >= target_stage:
            best = obs
            break
    return best


def evaluate_symbol(symbol: str, rows30: Sequence[Dict[str, Any]], rows5: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events = direct_transitions(rows30)
    cases: List[Dict[str, Any]] = []
    for e in events:
        stages = {f"T{i}": stage_time(rows5, e["known_time"], e["from"], i) for i in range(1, 6)}
        cases.append({
            "kind": "REAL",
            "symbol": symbol,
            "from": e["from"],
            "to": e["to"],
            "event_time": e["known_time"],
            "stages": stages,
        })
    return cases


def split_cases(cases: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by = defaultdict(list)
    for c in cases:
        by[c["symbol"]].append(c)
    discovery, holdout = [], []
    for rows in by.values():
        rows.sort(key=lambda x: x["event_time"])
        cut = int(len(rows) * 0.70)
        discovery.extend(rows[:cut])
        holdout.extend(rows[cut:])
    return discovery, holdout


def pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def summarize(cases: Sequence[Dict[str, Any]], label: str) -> None:
    print(f"\n{label}")
    print("=" * len(label))
    print(f"CASES {len(cases)}")
    for stage in range(1, 6):
        rows = [c for c in cases if c["stages"].get(f"T{stage}") is not None]
        leads = [
            (c["event_time"] - c["stages"][f"T{stage}"]).total_seconds() / 60.0
            for c in rows
            if c["stages"][f"T{stage}"] <= c["event_time"]
        ]
        print(
            f"T{stage}: reached={len(rows)}/{len(cases)} ({pct(len(rows), len(cases)):.1f}%) "
            f"lead_mean={mean(leads):.1f}m median={median(leads):.1f}m "
            f"within15={pct(sum(x <= 15 for x in leads), len(leads)):.1f}% "
            f"within30={pct(sum(x <= 30 for x in leads), len(leads)):.1f}%"
            if leads else
            f"T{stage}: reached=0/{len(cases)}"
        )


def stage_pairs(cases: Sequence[Dict[str, Any]]) -> None:
    print("\nSTAGE-TO-STAGE TIMING")
    print("=====================")
    for a, b in [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]:
        vals = []
        for c in cases:
            ta = c["stages"].get(f"T{a}")
            tb = c["stages"].get(f"T{b}")
            if ta is not None and tb is not None and tb >= ta:
                vals.append((tb - ta).total_seconds() / 60.0)
        if vals:
            print(f"T{a}->T{b}: N={len(vals)} mean={mean(vals):.1f}m median={median(vals):.1f}m")


def run(symbols: Sequence[str], limit30: int, limit5: int) -> None:
    all_cases: List[Dict[str, Any]] = []
    print("KISS V5 MARKET STRUCTURE TRANSITION — RESEARCH ONLY")
    print("No orders. No DB writes. No engine changes.")
    print("Target: actual price structure, not prediction of the 30m MA transition.")
    for symbol in symbols:
        rows30 = load(symbol, "30m", limit30)
        rows5 = load(symbol, "5m", limit5)
        cases = evaluate_symbol(symbol, rows30, rows5)
        all_cases.extend(cases)
        print(f"{symbol}: cases={len(cases)}")

    discovery, holdout = split_cases(all_cases)
    print(f"\nTOTAL {len(all_cases)} discovery={len(discovery)} holdout={len(holdout)}")
    summarize(all_cases, "FULL")
    summarize(discovery, "DISCOVERY 70%")
    summarize(holdout, "HOLDOUT 30%")
    stage_pairs(discovery)
    stage_pairs(holdout)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="KISS V5 market structure transition research")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    p.add_argument("--limit30", type=int, default=5000)
    p.add_argument("--limit5", type=int, default=30000)
    args = p.parse_args()
    run(args.symbols, args.limit30, args.limit5)
