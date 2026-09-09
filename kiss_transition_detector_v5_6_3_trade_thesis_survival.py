"""KISS V5.6.3 — Trade Thesis Survival Test.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.6.2 asked when the old trend became unhealthy. V5.6.3 asks the more
practical question for an open trade:

    Is the existing LONG/SHORT thesis still alive at this exact 5m close?

The experiment deliberately separates two decisions:
  1. THESIS_BROKEN = the existing trade is no longer safe to keep holding.
  2. OPPOSITE_DEVELOPING = evidence that the opposite direction is actually
     developing after the old thesis has broken.

A thesis break is therefore an EXIT/risk-management concept, not an automatic
reversal signal.

All observations are causal: only completed 5m candles and already-confirmed
3-bar swings are used. The official 30m MA transition is a reference event,
not the definition of truth.

The output measures post-recognition signed returns at +15/+30/+60/+120m.
Those outcomes are evaluation only and never feed the recognition logic.
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


def local_health(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    start = max(0, idx - 11)
    closes = [rows[j]["close"] for j in range(start, idx + 1)]
    moves = [signed_return(closes[k - 1], closes[k], prior) for k in range(1, len(closes))]
    progress = sum(1 for x in moves if x > 0.0)
    adverse = sum(1 for x in moves if x < 0.0)
    net = signed_return(closes[0], closes[-1], prior) if len(closes) >= 2 else 0.0
    consecutive = 0
    for x in reversed(moves):
        if x < 0.0:
            consecutive += 1
        else:
            break
    return {
        "progress": progress,
        "adverse": adverse,
        "net": net,
        "consecutive": consecutive,
        "moves": moves,
    }


def immediate_structure(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    # Only use the most recent confirmed old-trend support/resistance.
    if prior == "LONG":
        candidates = [j for j in lows if j < idx]
        if candidates:
            j = candidates[-1]
            if rows[idx]["close"] < rows[j]["low"]:
                return True, f"break_higher_low_{rows[j]['timestamp'].strftime('%H:%M')}"
    else:
        candidates = [j for j in highs if j < idx]
        if candidates:
            j = candidates[-1]
            if rows[idx]["close"] > rows[j]["high"]:
                return True, f"break_lower_high_{rows[j]['timestamp'].strftime('%H:%M')}"
    return False, ""


def opposite_structure(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    if prior == "LONG":
        # A confirmed lower high followed by a lower low is opposite structure.
        hs = [j for j in highs if j < idx]
        ls = [j for j in lows if j < idx]
        if len(hs) >= 2 and ls:
            h1, h2 = hs[-2], hs[-1]
            if rows[h2]["high"] < rows[h1]["high"]:
                if rows[idx]["close"] < rows[ls[-1]]["low"]:
                    return True, f"lower_high_then_lower_low_{rows[h2]['timestamp'].strftime('%H:%M')}"
    else:
        hs = [j for j in highs if j < idx]
        ls = [j for j in lows if j < idx]
        if len(ls) >= 2 and hs:
            l1, l2 = ls[-2], ls[-1]
            if rows[l2]["low"] > rows[l1]["low"]:
                if rows[idx]["close"] > rows[hs[-1]]["high"]:
                    return True, f"higher_low_then_higher_high_{rows[l2]['timestamp'].strftime('%H:%M')}"
    return False, ""


def post_returns(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Optional[float]]:
    base = rows[idx]["close"]
    out: Dict[str, Optional[float]] = {}
    for mins in (15, 30, 60, 120):
        j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=mins))
        out[f"ret_{mins}m"] = None if j is None else signed_return(base, rows[j]["close"], prior)
    return out


def causal_thesis(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    # Strict state machine. A later state cannot be recognized before the prior state.
    stage = "HEALTHY"
    warning_idx: Optional[int] = None
    risk_idx: Optional[int] = None
    broken_idx: Optional[int] = None
    opposite_idx: Optional[int] = None
    events: List[Dict[str, Any]] = []

    for idx in range(start, end + 1):
        h = local_health(rows, idx, prior)
        adverse_now = h["adverse"] >= 3 and h["net"] <= -0.10
        persistent = h["consecutive"] >= 2 and h["net"] <= -0.10
        structural_break, break_reason = immediate_structure(rows, idx, prior)

        if stage == "HEALTHY":
            if adverse_now or persistent:
                stage = "WARNING"
                warning_idx = idx
                events.append({"stage":"WARNING","idx":idx,"time":rows[idx]["timestamp"] + timedelta(minutes=5),"reason":"continuation_is_no_longer_clean","health":h})
                continue

        if stage == "WARNING":
            # Thesis at risk requires persistence, not one bad candle.
            if persistent or (adverse_now and h["progress"] <= h["adverse"]):
                stage = "THESIS_AT_RISK"
                risk_idx = idx
                events.append({"stage":"THESIS_AT_RISK","idx":idx,"time":rows[idx]["timestamp"] + timedelta(minutes=5),"reason":"persistent_adverse_pressure","health":h})
                continue

        if stage == "THESIS_AT_RISK":
            if structural_break:
                stage = "THESIS_BROKEN"
                broken_idx = idx
                events.append({"stage":"THESIS_BROKEN","idx":idx,"time":rows[idx]["timestamp"] + timedelta(minutes=5),"reason":break_reason,"health":h})
                continue
            if h["adverse"] >= 4 and h["net"] <= -0.30 and h["consecutive"] >= 2:
                stage = "THESIS_BROKEN"
                broken_idx = idx
                events.append({"stage":"THESIS_BROKEN","idx":idx,"time":rows[idx]["timestamp"] + timedelta(minutes=5),"reason":"failure_follow_through","health":h})
                continue

        if stage == "THESIS_BROKEN":
            opp, reason = opposite_structure(rows, idx, prior)
            if opp:
                stage = "OPPOSITE_DEVELOPING"
                opposite_idx = idx
                events.append({"stage":"OPPOSITE_DEVELOPING","idx":idx,"time":rows[idx]["timestamp"] + timedelta(minutes=5),"reason":reason,"health":h})
                break

    for e in events:
        e["minutes_to_t0"] = (t0 - e["time"]).total_seconds() / 60.0
        e["boundary_hit"] = e["idx"] == start
        e["post"] = post_returns(rows, e["idx"], prior)

    return {
        "usable": True,
        "stage": stage,
        "events": events,
        "warning_idx": warning_idx,
        "risk_idx": risk_idx,
        "broken_idx": broken_idx,
        "opposite_idx": opposite_idx,
    }


def fmt(v: Optional[float]) -> str:
    return "--" if v is None else f"{v:+.3f}%"


def print_case(n: int, symbol: str, event: Dict[str, Any], result: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    print("TRADE THESIS SURVIVAL (V5.6.3):")
    if not result["events"]:
        print("  NO_THESIS_CHANGE")
    for e in result["events"]:
        b = " [WINDOW_BOUNDARY]" if e["boundary_hit"] else ""
        print(f"  {e['stage']:<22} {e['time']} ({e['minutes_to_t0']:+.0f}m){b} {e['reason']}")
        h = e["health"]
        print(f"    HEALTH: progress={h['progress']} adverse={h['adverse']} net={h['net']:+.3f}% consecutive={h['consecutive']}")
        p = e["post"]
        print("    POST OLD-THESIS RETURNS: " + " ".join(f"{k}={fmt(v)}" for k,v in p.items()))
    print(f"FINAL THESIS STATE: {result['stage']}")


def summary(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.3 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.3 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rr = [r for r in records if r["direction"] == direction]
        print(f"{direction}: N={len(rr)}")
        for stage in ("WARNING", "THESIS_AT_RISK", "THESIS_BROKEN", "OPPOSITE_DEVELOPING"):
            vals = [r[stage] for r in rr if r[stage] is not None]
            boundary = sum(1 for r in rr if r.get(stage + "_boundary"))
            if not vals:
                print(f"  {stage:<22} N=0")
                continue
            vals.sort()
            med = vals[len(vals)//2] if len(vals) % 2 else (vals[len(vals)//2-1] + vals[len(vals)//2]) / 2
            print(f"  {stage:<22} N={len(vals):2d} mean={sum(vals)/len(vals):.1f}m median={med:.1f}m earliest={max(vals):.1f}m boundary={boundary}")
        broken = sum(1 for r in rr if r["THESIS_BROKEN"] is not None)
        opposite = sum(1 for r in rr if r["OPPOSITE_DEVELOPING"] is not None)
        print(f"  THESIS BROKEN         {broken}/{len(rr)}")
        print(f"  OPPOSITE DEVELOPING   {opposite}/{len(rr)}")


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
            result = causal_thesis(rows5, event)
            if not result["usable"]:
                skipped += 1
                continue
            case_no += 1
            print_case(case_no, symbol, event, result)
            row: Dict[str, Any] = {
                "symbol": symbol,
                "direction": f"{event['from']}->{event['to']}",
                "WARNING": None,
                "THESIS_AT_RISK": None,
                "THESIS_BROKEN": None,
                "OPPOSITE_DEVELOPING": None,
            }
            for e in result["events"]:
                row[e["stage"]] = e["minutes_to_t0"]
                row[e["stage"] + "_boundary"] = e["boundary_hit"]
            records.append(row)

    summary(records, total, skipped)
    print("V5.6.3 KEY QUESTION: when did the existing trade thesis stop being safe?")
    print("V5.6.3 SEPARATION: thesis break is an EXIT concept; opposite development is a separate reversal concept.")
    print("V5.6.3 is a causal research timeline, not a trading rule.")


if __name__ == "__main__":
    main()
