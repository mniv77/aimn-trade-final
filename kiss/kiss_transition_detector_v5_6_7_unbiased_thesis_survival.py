"""KISS V5.6.7 — Unbiased Thesis Survival Test.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.6 showed an important idea: damage must survive recovery testing.
But its candidate was often selected at the start of the observation window,
which contaminates recognition timing, and its TRUE_FAILURE label used future
information before evaluating the same future outcome.

V5.6.7 fixes that measurement problem.

For EVERY completed 5m candle in a broad causal window we ask:

  1. Is this candle an observable EXIT CANDIDATE using information available
     at this candle only?
  2. Looking forward, did the old thesis recover or continue failing?
  3. Independently, was EXITING here better than HOLDING here?

The future is used ONLY for evaluation.  It is never used to choose the
candidate candle.

Each candidate is classified by the realized 60m result:
  GOOD_EXIT    = holding would have lost > EXIT_BUFFER more than exiting
  FALSE_EXIT   = holding would have gained > EXIT_BUFFER
  NEUTRAL      = neither clearly better
  UNKNOWN      = insufficient future candles

This is a truth/evaluation test, not a trading rule.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
SWING_LOOKBACK = 3
LOOKBACK_MINUTES = 480
POST_MINUTES = 120
EVAL_MINUTES = 60
EXIT_BUFFER = 0.10
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
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
            "SELECT timestamp,open,high,low,close,volume FROM candles "
            "WHERE symbol=%s AND timeframe=%s ORDER BY timestamp ASC LIMIT %s",
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
                d[k] = num(d[k])
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
    for i in range(SWING_LOOKBACK, idx - SWING_LOOKBACK + 1):
        if i + SWING_LOOKBACK > idx:
            continue
        h = rows[i]["high"]
        l = rows[i]["low"]
        left_h = max(rows[j]["high"] for j in range(i - SWING_LOOKBACK, i))
        right_h = max(rows[j]["high"] for j in range(i + 1, i + SWING_LOOKBACK + 1))
        left_l = min(rows[j]["low"] for j in range(i - SWING_LOOKBACK, i))
        right_l = min(rows[j]["low"] for j in range(i + 1, i + SWING_LOOKBACK + 1))
        if h >= left_h and h >= right_h:
            highs.append(i)
        if l <= left_l and l <= right_l:
            lows.append(i)
    return highs, lows


def health(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    start = max(0, idx - 11)
    closes = [rows[j]["close"] for j in range(start, idx + 1)]
    moves = [signed_return(closes[k - 1], closes[k], prior) for k in range(1, len(closes))]
    adverse = sum(x < 0 for x in moves)
    progress = sum(x > 0 for x in moves)
    net = signed_return(closes[0], closes[-1], prior) if len(closes) > 1 else 0.0
    consecutive = 0
    for x in reversed(moves):
        if x < 0:
            consecutive += 1
        else:
            break
    return {"adverse": adverse, "progress": progress, "net": net, "consecutive": consecutive}


def structure_break(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    if prior == "LONG":
        candidates = [j for j in lows if j < idx]
        if candidates and rows[idx]["close"] < rows[candidates[-1]]["low"]:
            j = candidates[-1]
            return True, f"break_higher_low_{rows[j]['timestamp'].strftime('%H:%M')}"
    else:
        candidates = [j for j in highs if j < idx]
        if candidates and rows[idx]["close"] > rows[candidates[-1]]["high"]:
            j = candidates[-1]
            return True, f"break_lower_high_{rows[j]['timestamp'].strftime('%H:%M')}"
    return False, ""


def candidate_signal(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    """Causal candidate only. No future candles are consulted here."""
    h = health(rows, idx, prior)
    structural, reason = structure_break(rows, idx, prior)
    persistent = h["consecutive"] >= 2 and h["net"] <= -0.20
    balanced = h["adverse"] >= 6 and h["net"] <= -0.30
    if structural:
        return True, reason
    if persistent:
        return True, "two_or_more_consecutive_adverse_closes"
    if balanced:
        return True, "persistent_adverse_balance"
    return False, ""


def forward_closes(rows: Sequence[Dict[str, Any]], idx: int, minutes: int) -> List[int]:
    base_time = rows[idx]["timestamp"] + timedelta(minutes=5)
    out: List[int] = []
    for j in range(idx + 1, len(rows)):
        elapsed = (rows[j]["timestamp"] + timedelta(minutes=5) - base_time).total_seconds() / 60.0
        if elapsed > minutes:
            break
        out.append(j)
    return out


def evaluate(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    """Future-only evaluation of a candidate; never used by candidate_signal."""
    future = forward_closes(rows, idx, EVAL_MINUTES)
    if not future:
        return {"status": "UNKNOWN", "hold_60": None, "exit_advantage": None, "best": None, "worst": None}
    base = rows[idx]["close"]
    vals = [signed_return(base, rows[j]["close"], prior) for j in future]
    final = vals[-1]
    best = max(vals)
    worst = min(vals)
    # Exiting at the candidate gives approximately 0% over this evaluation window.
    advantage = -final
    if final <= -EXIT_BUFFER:
        status = "GOOD_EXIT"
    elif final >= EXIT_BUFFER:
        status = "FALSE_EXIT"
    else:
        status = "NEUTRAL"
    return {"status": status, "hold_60": final, "exit_advantage": advantage, "best": best, "worst": worst}


def outcome_at(rows: Sequence[Dict[str, Any]], idx: int, prior: str, minutes: int) -> Optional[float]:
    j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=minutes))
    if j is None:
        return None
    return signed_return(rows[idx]["close"], rows[j]["close"], prior)


def run_case(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    candidates: List[Dict[str, Any]] = []
    for idx in range(start, end + 1):
        ok, reason = candidate_signal(rows, idx, prior)
        if not ok:
            continue
        ev = evaluate(rows, idx, prior)
        candidates.append({
            "idx": idx,
            "time": rows[idx]["timestamp"] + timedelta(minutes=5),
            "minutes_to_t0": (t0 - (rows[idx]["timestamp"] + timedelta(minutes=5))).total_seconds() / 60.0,
            "boundary": idx == start,
            "reason": reason,
            "evaluation": ev,
            "ret15": outcome_at(rows, idx, prior, 15),
            "ret30": outcome_at(rows, idx, prior, 30),
            "ret60": outcome_at(rows, idx, prior, 60),
            "ret120": outcome_at(rows, idx, prior, 120),
        })
    return {"usable": True, "candidates": candidates}


def fmt(v: Optional[float]) -> str:
    return "--" if v is None else f"{v:+.3f}%"


def print_case(n: int, symbol: str, event: Dict[str, Any], result: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    cs = result["candidates"]
    print(f"  CAUSAL CANDIDATES: {len(cs)}")
    for c in cs[:8]:
        b = " [WINDOW_BOUNDARY]" if c["boundary"] else ""
        ev = c["evaluation"]
        print(f"  {c['time']} ({c['minutes_to_t0']:+.0f}m){b} {c['reason']} -> {ev['status']} hold60={fmt(ev['hold_60'])} advantage={fmt(ev['exit_advantage'])}")
        print(f"    15m={fmt(c['ret15'])} 30m={fmt(c['ret30'])} 60m={fmt(c['ret60'])} 120m={fmt(c['ret120'])}")


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.7 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.7 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    all_candidates: List[Dict[str, Any]] = []
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rs = [x for x in records if x["direction"] == direction]
        cs = [c for x in rs for c in x["result"]["candidates"]]
        all_candidates.extend(cs)
        print(f"\n{direction} TRANSITIONS N={len(rs)}")
        print(f"  CANDIDATE EVENTS: {len(cs)}")
        for status in ("GOOD_EXIT", "FALSE_EXIT", "NEUTRAL", "UNKNOWN"):
            n = sum(c["evaluation"]["status"] == status for c in cs)
            print(f"  {status:<12} {n}")
        if cs:
            print(f"  BOUNDARY CANDIDATES: {sum(c['boundary'] for c in cs)}")
            valid = [c for c in cs if c["evaluation"]["hold_60"] is not None]
            if valid:
                avg = sum(c["evaluation"]["hold_60"] for c in valid) / len(valid)
                print(f"  AVG HOLD-60M FROM CANDIDATE: {avg:+.3f}%")

    print(f"\nALL CANDIDATE EVENTS: {len(all_candidates)}")
    for status in ("GOOD_EXIT", "FALSE_EXIT", "NEUTRAL", "UNKNOWN"):
        n = sum(c["evaluation"]["status"] == status for c in all_candidates)
        print(f"  {status:<12} {n}")
    valid = [c for c in all_candidates if c["evaluation"]["hold_60"] is not None]
    if valid:
        good = [c for c in valid if c["evaluation"]["status"] == "GOOD_EXIT"]
        false = [c for c in valid if c["evaluation"]["status"] == "FALSE_EXIT"]
        neutral = [c for c in valid if c["evaluation"]["status"] == "NEUTRAL"]
        avg_hold = sum(c["evaluation"]["hold_60"] for c in valid) / len(valid)
        avg_good = sum(c["evaluation"]["hold_60"] for c in good) / len(good) if good else 0.0
        avg_false = sum(c["evaluation"]["hold_60"] for c in false) / len(false) if false else 0.0
        print(f"  VALID EVALUATIONS: {len(valid)}")
        print(f"  GOOD EXIT RATE: {len(good)/len(valid)*100:.1f}%")
        print(f"  FALSE EXIT RATE: {len(false)/len(valid)*100:.1f}%")
        print(f"  NEUTRAL RATE: {len(neutral)/len(valid)*100:.1f}%")
        print(f"  AVG HOLD-60M: {avg_hold:+.3f}%")
        print(f"  AVG GOOD-EXIT HOLD-60M: {avg_good:+.3f}%")
        print(f"  AVG FALSE-EXIT HOLD-60M: {avg_false:+.3f}%")

    print("\nV5.6.7 KEY TEST: WAS EXITING HERE ACTUALLY BETTER THAN HOLDING?")
    print("V5.6.7 separates causal detection from future truth evaluation.")
    print("V5.6.7 is research only — no trading rule or engine change.")


def main() -> None:
    ap = argparse.ArgumentParser(description="KISS V5.6.7 unbiased thesis survival research")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    case_no = 0
    for symbol in args.symbols:
        rows30 = load(symbol, "30m", 100000)
        rows5 = load(symbol, "5m", 300000)
        for event in transitions(rows30):
            total += 1
            result = run_case(rows5, event)
            if not result["usable"]:
                skipped += 1
                continue
            direction = f"{event['from']}->{event['to']}"
            records.append({"symbol": symbol, "direction": direction, "event": event, "result": result})
            case_no += 1
            if case_no <= 12:
                print_case(case_no, symbol, event, result)
    summarize(records, total, skipped)


if __name__ == "__main__":
    main()
