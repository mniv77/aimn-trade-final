"""KISS V5.6.2 — Trend Health / Thesis Failure.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.6.1 asked how early the official 30m MA transition could be recognized.
That question proved too indirect. V5.6.2 asks the trading question instead:

    WHEN DID THE OLD TREND STOP BEING SAFE TO TRADE?

For an existing LONG:
    healthy trend -> weakening -> thesis failure -> confirmed failure

For an existing SHORT the logic is mirrored.

The detector deliberately does NOT try to predict the official MA transition.
It reconstructs only what was knowable at each completed 5m candle and records:
  * trend health deterioration;
  * first thesis-failure point;
  * stronger structural confirmation;
  * price behavior after each recognition point.

This is a research measurement, not a trading rule.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
SWING_LOOKBACK = 3
LOOKBACK_MINUTES = 240
POST_MINUTES = 120
HEALTH_BARS = 12
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def f(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("+00:00", "")).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            "SELECT timestamp,open,high,low,close,volume "
            "FROM candles WHERE symbol=%s AND timeframe=%s "
            "ORDER BY timestamp ASC LIMIT %s",
            (symbol, timeframe, int(limit)),
        )
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall() or []:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5]
            }
            d["timestamp"] = dt(d["timestamp"])
            for k in ("open", "high", "low", "close", "volume"):
                d[k] = f(d[k])
            out.append(d)
        return out
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def state(closes: Sequence[float], i: int) -> str:
    if i < TREND_WINDOW or i >= len(closes):
        return "FLAT"
    ma = sum(closes[i - TREND_WINDOW:i]) / TREND_WINDOW
    if closes[i] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[i] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def transitions(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows]
    states = [state(closes, i) for i in range(len(rows))]
    out: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(rows)):
        if states[i - 1] in ("LONG", "SHORT") and states[i] in ("LONG", "SHORT") and states[i] != states[i - 1]:
            out.append({
                "i": i,
                "from": states[i - 1],
                "to": states[i],
                "time": rows[i]["timestamp"] + timedelta(minutes=30),
                "price": rows[i]["close"],
            })
    return out


def close_index(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    for i, r in enumerate(rows):
        if r["timestamp"] + timedelta(minutes=5) == target:
            return i
    return None


def signed_return(base: float, price: float, prior: str) -> float:
    raw = (price / base - 1.0) * 100.0
    return raw if prior == "LONG" else -raw


def confirmed_swings(rows: Sequence[Dict[str, Any]], idx: int) -> Tuple[List[int], List[int]]:
    highs: List[int] = []
    lows: List[int] = []
    if idx < SWING_LOOKBACK * 2 + 1:
        return highs, lows
    for i in range(SWING_LOOKBACK, idx - SWING_LOOKBACK + 1):
        if i + SWING_LOOKBACK > idx:
            continue
        h = rows[i]["high"]
        l = rows[i]["low"]
        lh = max(x["high"] for x in rows[i-SWING_LOOKBACK:i])
        rh = max(x["high"] for x in rows[i+1:i+SWING_LOOKBACK+1])
        ll = min(x["low"] for x in rows[i-SWING_LOOKBACK:i])
        rl = min(x["low"] for x in rows[i+1:i+SWING_LOOKBACK+1])
        if h >= lh and h >= rh:
            highs.append(i)
        if l <= ll and l <= rl:
            lows.append(i)
    return highs, lows


def health_snapshot(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    start = max(1, idx - HEALTH_BARS + 1)
    closes = [rows[j]["close"] for j in range(start, idx + 1)]
    if len(closes) < 4:
        return {"healthy": True, "progress": 0, "adverse": 0, "net": 0.0, "consecutive_adverse": 0}

    moves = []
    for a, b in zip(closes[:-1], closes[1:]):
        raw = (b / a - 1.0) * 100.0
        moves.append(raw if prior == "LONG" else -raw)

    progress = sum(1 for x in moves if x > 0.0)
    adverse = sum(1 for x in moves if x < 0.0)
    net = sum(moves)
    consecutive = 0
    for x in reversed(moves):
        if x < 0.0:
            consecutive += 1
        else:
            break

    # A trend is considered locally healthy when continuation still dominates.
    healthy = progress > adverse and net > 0.0 and consecutive < 2
    return {
        "healthy": healthy,
        "progress": progress,
        "adverse": adverse,
        "net": net,
        "consecutive_adverse": consecutive,
    }


def immediate_structure_failure(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    cutoff = idx - 1
    recent_highs = [j for j in highs if j < cutoff and j >= max(0, idx - HEALTH_BARS - SWING_LOOKBACK)]
    recent_lows = [j for j in lows if j < cutoff and j >= max(0, idx - HEALTH_BARS - SWING_LOOKBACK)]
    if prior == "LONG" and recent_lows:
        j = recent_lows[-1]
        if rows[idx]["close"] < rows[j]["low"]:
            return True, f"break_higher_low_{rows[j]['timestamp'].strftime('%H:%M')}"
    if prior == "SHORT" and recent_highs:
        j = recent_highs[-1]
        if rows[idx]["close"] > rows[j]["high"]:
            return True, f"break_lower_high_{rows[j]['timestamp'].strftime('%H:%M')}"
    return False, ""


def thesis_failure_signal(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    if idx < HEALTH_BARS:
        return False, ""
    h = health_snapshot(rows, idx, prior)
    structure, structure_reason = immediate_structure_failure(rows, idx, prior)

    # First thesis failure: the old trend has stopped behaving healthily AND
    # there is either persistent adverse pressure or a causal structure break.
    persistent = h["adverse"] >= 3 and h["net"] <= 0.0
    two_against = h["consecutive_adverse"] >= 2
    if structure:
        return True, structure_reason
    if persistent and two_against:
        return True, "persistent_adverse_pressure"
    return False, ""


def confirmed_failure(rows: Sequence[Dict[str, Any]], idx: int, prior: str, failure_idx: int) -> Tuple[bool, str]:
    if idx <= failure_idx:
        return False, ""
    structure, reason = immediate_structure_failure(rows, idx, prior)
    if structure:
        return True, reason

    # Confirmation requires adverse persistence after the thesis-failure point.
    vals = []
    for j in range(failure_idx, idx + 1):
        vals.append(signed_return(rows[failure_idx]["close"], rows[j]["close"], prior))
    if len(vals) >= 4 and vals[-1] < 0.0 and min(vals) < -0.20:
        return True, "failure_follow_through"
    return False, ""


def post_returns(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Optional[float]]:
    base = rows[idx]["close"]
    out: Dict[str, Optional[float]] = {}
    for mins in (15, 30, 60, 120):
        j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=mins))
        out[f"ret_{mins}m"] = None if j is None else signed_return(base, rows[j]["close"], prior)
    return out


def analyze(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    stage = "HEALTHY"
    weakening_idx: Optional[int] = None
    failure_idx: Optional[int] = None
    confirm_idx: Optional[int] = None
    events: List[Dict[str, Any]] = []

    for idx in range(start, end + 1):
        obs = rows[idx]["timestamp"] + timedelta(minutes=5)
        h = health_snapshot(rows, idx, prior)

        if stage == "HEALTHY":
            # Weakening is deliberately broader than thesis failure.
            if h["adverse"] >= h["progress"] and (h["net"] <= 0.0 or h["consecutive_adverse"] >= 2):
                stage = "WEAKENING"
                weakening_idx = idx
                events.append({
                    "stage": "WEAKENING", "idx": idx, "time": obs,
                    "minutes_to_t0": (t0 - obs).total_seconds() / 60.0,
                    "reason": f"progress={h['progress']} adverse={h['adverse']} net={h['net']:.3f} consecutive={h['consecutive_adverse']}"
                })
                continue

        if stage == "WEAKENING" and weakening_idx is not None:
            ok, reason = thesis_failure_signal(rows, idx, prior)
            if ok:
                stage = "THESIS_FAILURE"
                failure_idx = idx
                events.append({
                    "stage": "THESIS_FAILURE", "idx": idx, "time": obs,
                    "minutes_to_t0": (t0 - obs).total_seconds() / 60.0,
                    "reason": reason
                })
                continue

        if stage == "THESIS_FAILURE" and failure_idx is not None:
            ok, reason = confirmed_failure(rows, idx, prior, failure_idx)
            if ok:
                stage = "CONFIRMED_FAILURE"
                confirm_idx = idx
                events.append({
                    "stage": "CONFIRMED_FAILURE", "idx": idx, "time": obs,
                    "minutes_to_t0": (t0 - obs).total_seconds() / 60.0,
                    "reason": reason
                })
                break

    result = {
        "usable": True, "stage": stage, "events": events,
        "weakening_idx": weakening_idx, "failure_idx": failure_idx, "confirm_idx": confirm_idx
    }
    for e in events:
        e["post"] = post_returns(rows, e["idx"], prior)
        e["boundary_hit"] = e["idx"] == start
    return result


def fmt(v: Optional[float]) -> str:
    return "--" if v is None else f"{v:+.3f}%"


def print_case(n: int, symbol: str, event: Dict[str, Any], result: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    print("TREND HEALTH / THESIS FAILURE (V5.6.2):")
    if not result["events"]:
        print("  NO_THESIS_FAILURE_RECOGNITION")
    for e in result["events"]:
        boundary = " [WINDOW_BOUNDARY]" if e["boundary_hit"] else ""
        print(f"  {e['stage']:<22} {e['time']} ({e['minutes_to_t0']:+.0f}m){boundary} {e['reason']}")
        p = e["post"]
        print("    POST: " + " ".join(f"{k}={fmt(v)}" for k, v in p.items()))
    print(f"FINAL THESIS STATE: {result['stage']}")


def median(vals: List[float]) -> float:
    vals = sorted(vals)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.2 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.2 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rr = [x for x in records if x["direction"] == direction]
        print(f"{direction}: N={len(rr)}")
        for stage in ("WEAKENING", "THESIS_FAILURE", "CONFIRMED_FAILURE"):
            vals = [x[stage] for x in rr if x[stage] is not None]
            boundary = sum(1 for x in rr if x.get(stage + "_boundary"))
            if not vals:
                print(f"  {stage:<22} N=0")
                continue
            print(f"  {stage:<22} N={len(vals):2d} mean={sum(vals)/len(vals):.1f}m median={median(vals):.1f}m earliest={max(vals):.1f}m boundary={boundary}")
        complete = sum(1 for x in rr if x["CONFIRMED_FAILURE"] is not None)
        failure = sum(1 for x in rr if x["THESIS_FAILURE"] is not None)
        print(f"  THESIS FAILURE        {failure}/{len(rr)}")
        print(f"  CONFIRMED FAILURE     {complete}/{len(rr)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit30", type=int, default=5000)
    ap.add_argument("--limit5", type=int, default=50000)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    case_no = 0

    for symbol in args.symbols:
        rows30 = load(symbol, "30m", args.limit30)
        rows5 = load(symbol, "5m", args.limit5)
        evs = transitions(rows30)
        total += len(evs)
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} transitions={len(evs)}")
        for event in evs:
            result = analyze(rows5, event)
            if not result["usable"]:
                skipped += 1
                continue
            case_no += 1
            print_case(case_no, symbol, event, result)
            row: Dict[str, Any] = {
                "symbol": symbol,
                "direction": f"{event['from']}->{event['to']}",
                "WEAKENING": None,
                "THESIS_FAILURE": None,
                "CONFIRMED_FAILURE": None,
                "WEAKENING_boundary": False,
                "THESIS_FAILURE_boundary": False,
                "CONFIRMED_FAILURE_boundary": False,
            }
            for e in result["events"]:
                row[e["stage"]] = e["minutes_to_t0"]
                row[e["stage"] + "_boundary"] = e["boundary_hit"]
            records.append(row)

    summarize(records, total, skipped)
    print("V5.6.2 KEY QUESTION: when did the old trend stop being safe to trade?")
    print("V5.6.2 KEY TEST: did price continue against the old trend after thesis failure?")
    print("V5.6.2 is a causal research timeline, not a trading rule.")


if __name__ == "__main__":
    main()
