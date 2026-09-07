"""Research-only 5m diagnostic for post-gap KISS transition recognition.

No orders. No DB writes. No KISS/V5 changes.

For each session gap (>2h), the previous completed 30m KISS state and the
previous 12-bar relative-price bucket are known before the open.  The script
then watches the first 24 completed 5m candles (120 minutes).

It asks a narrower question than the prior diagnostic:
    When a 30m SHORT -> FLAT/LONG transition eventually appears, how early
    does simple 5m reversal evidence appear?

Evidence is deliberately descriptive, not a proposed trading rule:
    1) first 5m close above/below the session open against the prior state
    2) first 2 consecutive 5m closes moving against the prior state
    3) first 0.20%, 0.40%, 0.60% adverse move from session open

For SHORT, "against" means upward. For LONG, downward.
The script reports timing for eventual transitions and false signals on events
where no opposite 30m state appears within 120m.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
REL_WINDOW = 12
SESSION_GAP_HOURS = 2.0
FIVE_MIN_BARS = 24
THRESHOLDS = (0.20, 0.40, 0.60)
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW:
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def relative_position(closes: Sequence[float], idx: int) -> Optional[float]:
    if idx < REL_WINDOW:
        return None
    w = closes[idx - REL_WINDOW:idx]
    lo, hi = min(w), max(w)
    if hi <= lo:
        return 50.0
    return 100.0 * (closes[idx] - lo) / (hi - lo)


def bucket(p: Optional[float]) -> str:
    if p is None:
        return "UNKNOWN"
    if p <= 20:
        return "LOW"
    if p >= 80:
        return "HIGH"
    return "MIDDLE"


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cur.fetchall() or []
        out = []
        for r in rows:
            if isinstance(r, dict):
                d = dict(r)
            else:
                d = {"timestamp": r[0], "open": r[1], "high": r[2],
                     "low": r[3], "close": r[4], "volume": r[5]}
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


def nearest_5m(rows: Sequence[Dict[str, Any]], start: datetime, count: int) -> List[Dict[str, Any]]:
    """Return completed 5m bars at/after the session open, without lookahead."""
    out = [r for r in rows if r["timestamp"] >= start]
    return out[:count]


def first_30m_transition(closes: Sequence[float], i: int) -> Tuple[Optional[int], Optional[str]]:
    prev = market_state(closes, i - 1)
    for b in range(1, 5):
        j = i + b
        if j >= len(closes):
            break
        state = market_state(closes, j)
        if state != prev:
            return b * 30, state
    return None, None


def evidence(rows5: Sequence[Dict[str, Any]], direction: str) -> Dict[str, Any]:
    if not rows5:
        return {"cross_open": None, "two_step": None, "thresholds": {x: None for x in THRESHOLDS}}

    open_px = rows5[0]["open"]
    prev_close = open_px
    cross_open = None
    two_step = None
    thresholds = {x: None for x in THRESHOLDS}
    streak = 0

    for n, r in enumerate(rows5, start=1):
        close = r["close"]
        if direction == "SHORT":
            adverse = (close / open_px - 1.0) * 100.0
            moved_against = close > prev_close
            crossed = close > open_px
        else:
            adverse = (1.0 - close / open_px) * 100.0
            moved_against = close < prev_close
            crossed = close < open_px

        if crossed and cross_open is None:
            cross_open = n * 5

        if moved_against:
            streak += 1
        else:
            streak = 0
        if streak >= 2 and two_step is None:
            two_step = n * 5

        for x in THRESHOLDS:
            if adverse >= x and thresholds[x] is None:
                thresholds[x] = n * 5
        prev_close = close

    return {"cross_open": cross_open, "two_step": two_step, "thresholds": thresholds}


def build_events(rows30: Sequence[Dict[str, Any]], rows5: Sequence[Dict[str, Any]], symbol: str) -> List[Dict[str, Any]]:
    if len(rows30) < TREND_WINDOW + REL_WINDOW + 5:
        return []
    closes30 = [r["close"] for r in rows30]
    out = []
    for i in range(TREND_WINDOW + REL_WINDOW, len(rows30) - 4):
        t0, t1 = rows30[i - 1]["timestamp"], rows30[i]["timestamp"]
        if (t1 - t0).total_seconds() / 3600 <= SESSION_GAP_HOURS:
            continue
        state = market_state(closes30, i - 1)
        pos = relative_position(closes30, i - 1)
        b = bucket(pos)
        if state not in ("LONG", "SHORT") or b == "UNKNOWN":
            continue
        bars5 = nearest_5m(rows5, t1, FIVE_MIN_BARS)
        if len(bars5) < FIVE_MIN_BARS:
            continue
        transition_min, transition_state = first_30m_transition(closes30, i)
        ev = evidence(bars5, state)
        out.append({
            "symbol": symbol,
            "open_time": t1,
            "state": state,
            "bucket": b,
            "gap_pct": (rows30[i]["open"] / rows30[i - 1]["close"] - 1) * 100,
            "transition_min": transition_min,
            "transition_state": transition_state,
            "evidence": ev,
        })
    return out


def split(events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by = defaultdict(list)
    for e in events:
        by[e["symbol"]].append(e)
    a, b = [], []
    for symbol, rows in by.items():
        rows.sort(key=lambda x: x["open_time"])
        cut = int(len(rows) * 0.70)
        a.extend(rows[:cut]); b.extend(rows[cut:])
    return a, b


def fmt_timing(xs: List[Optional[int]]) -> str:
    vals = [x for x in xs if x is not None]
    return "n/a" if not vals else f"{mean(vals):.1f}m median={median(vals):.0f}m"


def report_group(events: List[Dict[str, Any]], state: str, b: str) -> None:
    xs = [e for e in events if e["state"] == state and e["bucket"] == b]
    if not xs:
        return
    opposite = "LONG" if state == "SHORT" else "SHORT"
    changed = [e for e in xs if e["transition_min"] is not None]
    opp = [e for e in xs if e["transition_state"] == opposite]
    print(f"\n{state} + {b}  N={len(xs)} | change120={100*len(changed)/len(xs):.1f}% | toOPP={100*len(opp)/len(xs):.1f}%")
    for name, getter in (
        ("cross session open", lambda e: e["evidence"]["cross_open"]),
        ("2 consecutive 5m", lambda e: e["evidence"]["two_step"]),
    ):
        all_sig = [e for e in xs if getter(e) is not None]
        real = [e for e in opp if getter(e) is not None and getter(e) <= e["transition_min"]]
        false = [e for e in xs if e["transition_min"] is None and getter(e) is not None]
        print(f"  {name:22} seen={100*len(all_sig)/len(xs):5.1f}% | real-before-transition={100*len(real)/len(opp):5.1f}% | false(no120)={100*len(false)/len([e for e in xs if e['transition_min'] is None]) if any(e['transition_min'] is None for e in xs) else 0:5.1f}% | timing={fmt_timing([getter(e) for e in real])}")
    for threshold in THRESHOLDS:
        getter = lambda e, x=threshold: e["evidence"]["thresholds"][x]
        real = [e for e in opp if getter(e) is not None and getter(e) <= e["transition_min"]]
        false = [e for e in xs if e["transition_min"] is None and getter(e) is not None]
        no_change = sum(e["transition_min"] is None for e in xs)
        print(f"  adverse >= {threshold:.2f}%       real-before-transition={100*len(real)/len(opp):5.1f}% | false(no120)={100*len(false)/no_change if no_change else 0:5.1f}% | timing={fmt_timing([getter(e) for e in real])}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit", type=int, default=10000)
    args = ap.parse_args()

    print("KISS POST-GAP 5M TRANSITION-EVIDENCE DIAGNOSTIC")
    print("Research only — no strategy/engine changes, no DB writes")
    print(f"Symbols: {', '.join(args.symbols)}")
    print("5m observation window: 120m / 24 completed bars")
    print("Evidence is descriptive; thresholds are not trading rules.")

    events = []
    for symbol in args.symbols:
        try:
            r30 = load(symbol, "30m", args.limit)
            r5 = load(symbol, "5m", args.limit)
            e = build_events(r30, r5, symbol)
            events.extend(e)
            print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} session_events={len(e)}")
        except Exception as exc:
            print(f"{symbol}: ERROR: {exc}")

    print(f"\nALL EVENTS: N={len(events)}")
    d, h = split(events)
    for title, data in (("FULL SAMPLE", events), ("DISCOVERY 70%", d), ("HOLDOUT 30%", h)):
        print(f"\n{'='*80}\n{title}\n{'='*80}")
        for state, b in (("SHORT","LOW"),("SHORT","MIDDLE"),("SHORT","HIGH"),("LONG","LOW"),("LONG","MIDDLE"),("LONG","HIGH")):
            report_group(data, state, b)

    print("\nKEY TEST")
    print("========")
    print("For actual SHORT->LONG transitions, did 5m evidence appear before the")
    print("official 30m transition, and how often did the same evidence appear")
    print("without a transition within 120m?")
    print("If the holdout shows useful early recognition with acceptable false")
    print("signals, the next experiment can test richer transition features.")
    print("No trading rule is derived from this diagnostic.")


if __name__ == "__main__":
    main()
