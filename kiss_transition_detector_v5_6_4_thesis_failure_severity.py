"""KISS V5.6.4 — Thesis Failure Severity / Survival Test.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.6.3 separated THESIS_BROKEN (exit concept) from OPPOSITE_DEVELOPING
(reversal concept). V5.6.4 asks the next question:

    HOW SERIOUS IS THE THESIS FAILURE RIGHT NOW?

The experiment deliberately avoids treating every weakness as an exit.
It measures four causal severity levels for an existing LONG/SHORT trade:

  HEALTHY
  PRESSURE      = the trend is under measurable pressure
  DETERIORATING = pressure is persistent and recovery is failing
  SEVERE        = adverse movement is persistent/accelerating OR old structure
                   has broken
  BROKEN        = the old thesis has failed through structural break or strong
                  failure follow-through

Severity is evaluated candle-by-candle using only completed 5m candles and
already-confirmed 3-bar swings. The official 30m MA transition is only a
reference event.

For every severity point we measure the subsequent signed return at
+15/+30/+60/+120m from the recognition candle. These future outcomes are
EVALUATION ONLY and never feed recognition.

The goal is not to create a trading rule yet. The goal is to discover whether
there is a useful separation between:
  - harmless weakness,
  - dangerous deterioration,
  - a genuinely unsafe existing trade, and
  - an actual opposite trend developing.
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
            out.append({"i": i, "from": states[i - 1], "to": states[i],
                        "time": rows[i]["timestamp"] + timedelta(minutes=30),
                        "price": rows[i]["close"]})
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
    progress = sum(x > 0 for x in moves)
    adverse = sum(x < 0 for x in moves)
    net = signed_return(closes[0], closes[-1], prior) if len(closes) > 1 else 0.0
    consecutive = 0
    for x in reversed(moves):
        if x < 0:
            consecutive += 1
        else:
            break
    first_half = sum(moves[:5]) if len(moves) >= 5 else sum(moves)
    second_half = sum(moves[5:]) if len(moves) > 5 else 0.0
    return {"progress": progress, "adverse": adverse, "net": net,
            "consecutive": consecutive, "first_half": first_half,
            "second_half": second_half, "moves": moves}


def old_structure_break(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    if prior == "LONG":
        candidates = [j for j in lows if j < idx]
        if candidates and rows[idx]["close"] < rows[candidates[-1]]["low"]:
            return True, f"break_higher_low_{rows[candidates[-1]]['timestamp'].strftime('%H:%M')}"
    else:
        candidates = [j for j in highs if j < idx]
        if candidates and rows[idx]["close"] > rows[candidates[-1]]["high"]:
            return True, f"break_lower_high_{rows[candidates[-1]]['timestamp'].strftime('%H:%M')}"
    return False, ""


def opposite_developing(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    hs = [j for j in highs if j < idx]
    ls = [j for j in lows if j < idx]
    if prior == "LONG" and len(hs) >= 2 and ls:
        h1, h2 = hs[-2], hs[-1]
        if rows[h2]["high"] < rows[h1]["high"] and rows[idx]["close"] < rows[ls[-1]]["low"]:
            return True, f"lower_high_then_lower_low_{rows[h2]['timestamp'].strftime('%H:%M')}"
    if prior == "SHORT" and len(ls) >= 2 and hs:
        l1, l2 = ls[-2], ls[-1]
        if rows[l2]["low"] > rows[l1]["low"] and rows[idx]["close"] > rows[hs[-1]]["high"]:
            return True, f"higher_low_then_higher_high_{rows[l2]['timestamp'].strftime('%H:%M')}"
    return False, ""


def post(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Optional[float]]:
    base = rows[idx]["close"]
    out: Dict[str, Optional[float]] = {}
    for mins in (15, 30, 60, 120):
        j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=mins))
        out[f"ret_{mins}m"] = None if j is None else signed_return(base, rows[j]["close"], prior)
    return out


def classify(h: Dict[str, Any], broken: bool, prior: str) -> Tuple[str, str]:
    # Severity intentionally uses persistence + acceleration, not one bad candle.
    persistent = h["consecutive"] >= 2 and h["net"] <= -0.10
    pressure = h["adverse"] >= 3 and h["net"] <= -0.10
    accelerating = h["second_half"] < h["first_half"] - 0.05
    severe_pressure = (h["adverse"] >= 5 and h["net"] <= -0.30 and h["consecutive"] >= 2)
    if broken:
        return "BROKEN", "old_structure_break"
    if severe_pressure and accelerating:
        return "SEVERE", "persistent_accelerating_adverse_pressure"
    if severe_pressure:
        return "SEVERE", "persistent_adverse_pressure"
    if persistent and (accelerating or h["adverse"] > h["progress"]):
        return "DETERIORATING", "persistent_pressure_with_weak_recovery"
    if pressure:
        return "PRESSURE", "measurable_adverse_pressure"
    return "HEALTHY", "trend_still_behaving_normally"


def run_case(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    last_level = "HEALTHY"
    observations: List[Dict[str, Any]] = []
    seen = {"PRESSURE": False, "DETERIORATING": False, "SEVERE": False, "BROKEN": False, "OPPOSITE_DEVELOPING": False}

    for idx in range(start, end + 1):
        h = health(rows, idx, prior)
        broken, break_reason = old_structure_break(rows, idx, prior)
        level, reason = classify(h, broken, prior)

        # Record the first time each meaningful severity is reached.
        if level in seen and not seen[level]:
            seen[level] = True
            observations.append({"level": level, "idx": idx, "time": rows[idx]["timestamp"] + timedelta(minutes=5),
                                 "reason": break_reason if broken else reason, "health": h})

        if last_level == "BROKEN":
            continue
        if level == "BROKEN":
            last_level = "BROKEN"
        elif level == "SEVERE" and last_level not in ("BROKEN",):
            last_level = "SEVERE"
        elif level == "DETERIORATING" and last_level == "HEALTHY":
            last_level = "DETERIORATING"
        elif level == "PRESSURE" and last_level == "HEALTHY":
            last_level = "PRESSURE"

        if seen["BROKEN"] and not seen["OPPOSITE_DEVELOPING"]:
            opp, opp_reason = opposite_developing(rows, idx, prior)
            if opp:
                seen["OPPOSITE_DEVELOPING"] = True
                observations.append({"level":"OPPOSITE_DEVELOPING","idx":idx,
                                     "time":rows[idx]["timestamp"] + timedelta(minutes=5),
                                     "reason":opp_reason,"health":h})
                break

    for o in observations:
        o["minutes_to_t0"] = (t0 - o["time"]).total_seconds() / 60.0
        o["boundary"] = o["idx"] == start
        o["post"] = post(rows, o["idx"], prior)
    return {"usable": True, "observations": observations,
            "final": observations[-1]["level"] if observations else "HEALTHY"}


def fmt(v: Optional[float]) -> str:
    return "--" if v is None else f"{v:+.3f}%"


def print_case(n: int, symbol: str, event: Dict[str, Any], result: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    print("THESIS FAILURE SEVERITY (V5.6.4):")
    for o in result["observations"]:
        b = " [WINDOW_BOUNDARY]" if o["boundary"] else ""
        print(f"  {o['level']:<22} {o['time']} ({o['minutes_to_t0']:+.0f}m){b} {o['reason']}")
        h = o["health"]
        print(f"    HEALTH: progress={h['progress']} adverse={h['adverse']} net={h['net']:+.3f}% consecutive={h['consecutive']} first_half={h['first_half']:+.3f}% second_half={h['second_half']:+.3f}%")
        print("    POST OLD-THESIS RETURNS: " + " ".join(f"{k}={fmt(v)}" for k,v in o["post"].items()))
    print(f"FINAL THESIS STATE: {result['final']}")


def summary(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.4 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.4 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    levels = ("PRESSURE", "DETERIORATING", "SEVERE", "BROKEN", "OPPOSITE_DEVELOPING")
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rr = [r for r in records if r["direction"] == direction]
        print(f"{direction}: N={len(rr)}")
        for level in levels:
            vals = [r[level] for r in rr if r[level] is not None]
            boundary = sum(1 for r in rr if r.get(level + "_boundary"))
            if not vals:
                print(f"  {level:<22} N=0")
                continue
            vals.sort()
            med = vals[len(vals)//2] if len(vals) % 2 else (vals[len(vals)//2-1] + vals[len(vals)//2]) / 2
            print(f"  {level:<22} N={len(vals):2d} mean={sum(vals)/len(vals):.1f}m median={med:.1f}m earliest={max(vals):.1f}m boundary={boundary}")
        print(f"  BROKEN               {sum(r['BROKEN'] is not None for r in rr)}/{len(rr)}")
        print(f"  OPPOSITE DEVELOPING  {sum(r['OPPOSITE_DEVELOPING'] is not None for r in rr)}/{len(rr)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    all_records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    case_no = 0

    for symbol in args.symbols:
        rows30 = load(symbol, "30m", 10000)
        rows5 = load(symbol, "5m", 100000)
        events = transitions(rows30)
        total += len(events)
        for event in events:
            result = run_case(rows5, event)
            if not result.get("usable"):
                skipped += 1
                continue
            case_no += 1
            print_case(case_no, symbol, event, result)
            rec: Dict[str, Any] = {"symbol":symbol,
                                   "direction":f"{event['from']}->{event['to']}"}
            for level in ("PRESSURE", "DETERIORATING", "SEVERE", "BROKEN", "OPPOSITE_DEVELOPING"):
                hit = next((o for o in result["observations"] if o["level"] == level), None)
                rec[level] = None if hit is None else hit["minutes_to_t0"]
                rec[level + "_boundary"] = bool(hit and hit["boundary"])
            all_records.append(rec)

    summary(all_records, total, skipped)
    print("V5.6.4 KEY QUESTION: how serious was the thesis failure at each causal recognition point?")
    print("V5.6.4 SEPARATION: severity is an EXIT-risk concept; opposite development remains a separate reversal concept.")
    print("V5.6.4 is a causal research timeline, not a trading rule.")


if __name__ == "__main__":
    main()
