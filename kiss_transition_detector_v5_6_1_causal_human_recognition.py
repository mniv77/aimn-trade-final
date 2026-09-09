"""KISS V5.6.1 — Expanded Causal Human Recognition / Boundary Truth Test.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.6 fixed the impossible stage ordering seen in V5.5 by using a strict
forward state machine. V5.6.1 keeps that causal sequencing and fixes the next
measurement problem: the V5.6 observation window was only 120 minutes wide,
so an "earliest" recognition at -120m could simply be a window boundary.

V5.6.1 therefore:
  * uses T-240m through T+120m;
  * processes completed 5m candles strictly forward;
  * locks NORMAL -> WARNING -> CHARACTER_CHANGE -> CONFIRMED_TRANSITION;
  * records boundary hits explicitly;
  * keeps the official 30m MA transition as a reference event only;
  * measures post-recognition price behavior separately from detection.

The goal is not to predict the MA transition. The goal is to measure when the
old trend stopped behaving normally, using only information available then.
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
                "i": i, "from": states[i - 1], "to": states[i],
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
    if idx < SWING_LOOKBACK * 2:
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


def find_warning(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> bool:
    if idx < 3:
        return False
    base = rows[idx-2]["close"]
    a = signed_return(base, rows[idx-1]["close"], prior)
    b = signed_return(base, rows[idx]["close"], prior)
    # A local continuation impulse followed by a completed adverse close.
    if a <= 0.0 or b >= a:
        return False
    recent_moves = [signed_return(rows[j-1]["close"], rows[j]["close"], prior) for j in range(idx-2, idx+1)]
    return any(x < 0.0 for x in recent_moves)


def find_character_change(rows: Sequence[Dict[str, Any]], idx: int, prior: str, warning_idx: int) -> Tuple[bool, str]:
    if idx <= warning_idx + 1:
        return False, ""
    base = rows[warning_idx]["close"]
    vals = [signed_return(base, rows[j]["close"], prior) for j in range(warning_idx, idx + 1)]
    if len(vals) < 3:
        return False, ""
    peak = max(vals[:-1])
    recovery_attempted = peak > 0.0
    recovery_failed = recovery_attempted and vals[-1] < peak and vals[-1] < 0.0

    highs, lows = confirmed_swings(rows, idx)
    rh = [j for j in highs if warning_idx < j < idx]
    rl = [j for j in lows if warning_idx < j < idx]
    opposite = False
    if prior == "LONG":
        if rh and rl:
            opposite = rows[rh[-1]]["high"] < rows[warning_idx]["high"] or rows[rl[-1]]["low"] < rows[warning_idx]["low"]
    else:
        if rh and rl:
            opposite = rows[rh[-1]]["high"] > rows[warning_idx]["high"] or rows[rl[-1]]["low"] > rows[warning_idx]["low"]

    if recovery_failed:
        return True, "recovery_attempt_failed"
    if opposite:
        return True, "confirmed_opposite_structure"
    return False, ""


def find_confirmation(rows: Sequence[Dict[str, Any]], idx: int, prior: str, warning_idx: int, change_idx: int) -> Tuple[bool, str]:
    if idx <= change_idx:
        return False, ""
    highs, lows = confirmed_swings(rows, idx)
    old_highs = [j for j in highs if warning_idx <= j < change_idx]
    old_lows = [j for j in lows if warning_idx <= j < change_idx]
    if prior == "LONG" and old_lows:
        j = old_lows[-1]
        if rows[idx]["close"] < rows[j]["low"]:
            return True, f"break_prior_higher_low_{rows[j]['timestamp'].strftime('%H:%M')}"
    if prior == "SHORT" and old_highs:
        j = old_highs[-1]
        if rows[idx]["close"] > rows[j]["high"]:
            return True, f"break_prior_lower_high_{rows[j]['timestamp'].strftime('%H:%M')}"
    return False, ""


def post_returns(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Optional[float]]:
    base = rows[idx]["close"]
    out: Dict[str, Optional[float]] = {}
    for mins in (15, 30, 60, 120):
        j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=mins))
        if j is None:
            out[f"ret_{mins}m"] = None
        else:
            out[f"ret_{mins}m"] = signed_return(base, rows[j]["close"], prior)
    return out


def causal_state_machine(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    stage = "NORMAL"
    warning_idx: Optional[int] = None
    change_idx: Optional[int] = None
    confirm_idx: Optional[int] = None
    events: List[Dict[str, Any]] = []

    for idx in range(start, end + 1):
        obs = rows[idx]["timestamp"] + timedelta(minutes=5)
        if stage == "NORMAL" and find_warning(rows, idx, prior):
            stage = "WARNING"
            warning_idx = idx
            events.append({"stage":"WARNING","idx":idx,"time":obs,"minutes_to_t0":(t0-obs).total_seconds()/60.0,"reason":"continuation_weakens_after_local_progress"})
            continue
        if stage == "WARNING" and warning_idx is not None:
            ok, reason = find_character_change(rows, idx, prior, warning_idx)
            if ok:
                stage = "CHARACTER_CHANGE"
                change_idx = idx
                events.append({"stage":"CHARACTER_CHANGE","idx":idx,"time":obs,"minutes_to_t0":(t0-obs).total_seconds()/60.0,"reason":reason})
                continue
        if stage == "CHARACTER_CHANGE" and warning_idx is not None and change_idx is not None:
            ok, reason = find_confirmation(rows, idx, prior, warning_idx, change_idx)
            if ok:
                stage = "CONFIRMED_TRANSITION"
                confirm_idx = idx
                events.append({"stage":"CONFIRMED_TRANSITION","idx":idx,"time":obs,"minutes_to_t0":(t0-obs).total_seconds()/60.0,"reason":reason})
                break

    result = {"usable":True,"stage":stage,"events":events,"warning_idx":warning_idx,"change_idx":change_idx,"confirm_idx":confirm_idx}
    # Economic follow-through is deliberately measured from each recognition point,
    # never used to create or alter that recognition.
    for e in events:
        e["post"] = post_returns(rows, e["idx"], prior)
        e["boundary_hit"] = e["idx"] == start
    return result


def fmt_minutes(v: Optional[float]) -> str:
    if v is None:
        return "--"
    return f"{v:.1f}m"


def print_case(n: int, symbol: str, event: Dict[str, Any], result: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    print("EXPANDED CAUSAL RECOGNITION (V5.6.1):")
    if not result["events"]:
        print("  NO_RECOGNITION")
    for e in result["events"]:
        b = " [WINDOW_BOUNDARY]" if e["boundary_hit"] else ""
        print(f"  {e['stage']:<22} {e['time']} ({e['minutes_to_t0']:+.0f}m){b} {e['reason']}")
        p = e.get("post", {})
        print("    POST: " + " ".join(f"{k}={fmt_minutes(v)}" for k,v in p.items()))
    print(f"FINAL CAUSAL STATE: {result['stage']}")


def summarize(records: List[Dict[str, Any]]) -> None:
    print("\n================ V5.6.1 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {records[0]['total'] if records else 0}")
    print(f"USABLE COMPLETE V5.6.1 WINDOWS: {len(records)}")
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rr = [x for x in records if x["direction"] == direction]
        print(f"{direction}: N={len(rr)}")
        for stage in ("WARNING", "CHARACTER_CHANGE", "CONFIRMED_TRANSITION"):
            vals = [x[stage] for x in rr if x[stage] is not None]
            boundary = sum(1 for x in rr if x.get(stage + "_boundary"))
            if not vals:
                print(f"  {stage:<22} N=0")
                continue
            vals_sorted = sorted(vals)
            med = vals_sorted[len(vals_sorted)//2] if len(vals_sorted)%2 else (vals_sorted[len(vals_sorted)//2-1]+vals_sorted[len(vals_sorted)//2])/2
            print(f"  {stage:<22} N={len(vals):2d} mean={sum(vals)/len(vals):.1f}m median={med:.1f}m earliest={max(vals):.1f}m boundary={boundary}")
        complete = sum(1 for x in rr if x["CONFIRMED_TRANSITION"] is not None)
        print(f"  COMPLETE SEQUENCE     {complete}/{len(rr)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit30", type=int, default=5000)
    ap.add_argument("--limit5", type=int, default=50000)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    total = 0
    case_no = 0
    skipped = 0

    for symbol in args.symbols:
        rows30 = load(symbol, "30m", args.limit30)
        rows5 = load(symbol, "5m", args.limit5)
        evs = transitions(rows30)
        total += len(evs)
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} transitions={len(evs)}")
        for event in evs:
            result = causal_state_machine(rows5, event)
            if not result["usable"]:
                skipped += 1
                continue
            case_no += 1
            print_case(case_no, symbol, event, result)
            row: Dict[str, Any] = {"symbol":symbol,"direction":f"{event['from']}->{event['to']}","total":0,"WARNING":None,"CHARACTER_CHANGE":None,"CONFIRMED_TRANSITION":None}
            for e in result["events"]:
                row[e["stage"]] = e["minutes_to_t0"]
                row[e["stage"] + "_boundary"] = e["boundary_hit"]
            records.append(row)

    for r in records:
        r["total"] = total
    print(f"\nTOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.1 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    summarize(records)
    print("V5.6.1 KEY RULE: every stage is discovered only after the preceding stage.")
    print("V5.6.1 KEY MEASUREMENT: expanded T-240 boundary makes early-recognition claims testable.")
    print("V5.6.1 is a causal research timeline, not a trading rule.")


if __name__ == "__main__":
    main()
