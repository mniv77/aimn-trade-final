"""KISS V5.6.5 — Causal Trade Thesis Survival Test.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.4 showed that assigning independent severity labels can produce
impossible timelines (BROKEN before PRESSURE, etc.). V5.6.5 removes those
independent severity labels.

The question is now deliberately simpler:

    FOR AN EXISTING TRADE, IS THE ORIGINAL THESIS STILL ALIVE?

The causal state machine is:

    HEALTHY -> PRESSURE -> THESIS_BROKEN

After THESIS_BROKEN, a separate test asks:

    IS THE OPPOSITE DIRECTION ACTUALLY DEVELOPING?

A broken thesis is therefore an EXIT candidate, not an automatic reversal.
The experiment measures whether exiting at the first causal break would have
been better than continuing to hold the old direction.

All recognition uses only completed 5m candles and already-confirmed 3-bar
swings. Future candles are used only for evaluation after recognition.
The official 30m MA transition is only a reference timestamp.
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
    worst = 0.0
    running = 0.0
    for x in moves:
        running += x
        worst = min(worst, running)
    return {
        "adverse": adverse,
        "progress": progress,
        "net": net,
        "consecutive": consecutive,
        "worst_path": worst,
    }


def old_structure_break(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
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


def thesis_pressure(h: Dict[str, Any]) -> bool:
    # Pressure requires more than one bad candle: measurable adverse balance.
    return h["adverse"] >= 3 and h["net"] <= -0.10


def thesis_break_candidate(h: Dict[str, Any], broken: bool) -> bool:
    # A thesis is broken only by structural failure or persistent adverse
    # pressure. This is deliberately stricter than a one-candle reversal.
    persistent = h["consecutive"] >= 2 and h["net"] <= -0.20
    severe_balance = h["adverse"] >= 6 and h["net"] <= -0.30
    return broken or persistent or severe_balance


def post_outcomes(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    base = rows[idx]["close"]
    out: Dict[str, Any] = {}
    for mins in (15, 30, 60, 120):
        j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=mins))
        out[f"ret_{mins}m"] = None if j is None else signed_return(base, rows[j]["close"], prior)
    # Best and worst signed close-to-close outcome over the first 120 minutes.
    vals: List[float] = []
    for j in range(idx + 1, len(rows)):
        mins = (rows[j]["timestamp"] + timedelta(minutes=5) - (rows[idx]["timestamp"] + timedelta(minutes=5))).total_seconds() / 60.0
        if mins > POST_MINUTES:
            break
        vals.append(signed_return(base, rows[j]["close"], prior))
    out["best_120m"] = max(vals) if vals else None
    out["worst_120m"] = min(vals) if vals else None
    return out


def recovery_after_break(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    base = rows[idx]["close"]
    vals: List[float] = []
    for j in range(idx + 1, len(rows)):
        mins = (rows[j]["timestamp"] + timedelta(minutes=5) - (rows[idx]["timestamp"] + timedelta(minutes=5))).total_seconds() / 60.0
        if mins > 120:
            break
        vals.append(signed_return(base, rows[j]["close"], prior))
    if not vals:
        return {"recovered": None, "continued_against": None}
    return {
        "recovered": max(vals) >= 0.20,
        "continued_against": min(vals) <= -0.50,
    }


def run_case(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    stage = "HEALTHY"
    pressure_idx: Optional[int] = None
    break_idx: Optional[int] = None
    pressure_reason = ""
    break_reason = ""
    opposite_idx: Optional[int] = None
    opposite_reason = ""

    # Strictly forward state machine. Once pressure is reached, we never
    # retroactively label earlier candles as pressure or broken.
    for idx in range(start, end + 1):
        h = health(rows, idx, prior)
        broken_struct, struct_reason = old_structure_break(rows, idx, prior)

        if stage == "HEALTHY" and thesis_pressure(h):
            stage = "PRESSURE"
            pressure_idx = idx
            pressure_reason = "persistent_adverse_balance"

        if stage == "PRESSURE" and thesis_break_candidate(h, broken_struct):
            stage = "THESIS_BROKEN"
            break_idx = idx
            break_reason = struct_reason if broken_struct else (
                "persistent_adverse_pressure" if h["consecutive"] >= 2 else "severe_adverse_balance"
            )

        if stage == "THESIS_BROKEN" and opposite_idx is None:
            opp, opp_reason = opposite_developing(rows, idx, prior)
            if opp:
                opposite_idx = idx
                opposite_reason = opp_reason
                break

    def event_record(level: str, idx: Optional[int], reason: str) -> Optional[Dict[str, Any]]:
        if idx is None:
            return None
        known = rows[idx]["timestamp"] + timedelta(minutes=5)
        return {
            "level": level,
            "idx": idx,
            "time": known,
            "minutes_to_t0": (t0 - known).total_seconds() / 60.0,
            "boundary": idx == start,
            "reason": reason,
            "health": health(rows, idx, prior),
            "post": post_outcomes(rows, idx, prior),
        }

    pressure = event_record("PRESSURE", pressure_idx, pressure_reason)
    broken = event_record("THESIS_BROKEN", break_idx, break_reason)
    opposite = event_record("OPPOSITE_DEVELOPING", opposite_idx, opposite_reason)

    return {
        "usable": True,
        "pressure": pressure,
        "broken": broken,
        "opposite": opposite,
    }


def fmt(v: Optional[float]) -> str:
    return "--" if v is None else f"{v:+.3f}%"


def print_case(n: int, symbol: str, event: Dict[str, Any], result: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    for label, rec in (("PRESSURE", result["pressure"]), ("THESIS_BROKEN", result["broken"]), ("OPPOSITE_DEVELOPING", result["opposite"])):
        if rec is None:
            print(f"  {label:<22} NOT REACHED")
            continue
        boundary = " [WINDOW_BOUNDARY]" if rec["boundary"] else ""
        h = rec["health"]
        p = rec["post"]
        print(f"  {label:<22} {rec['time']} ({rec['minutes_to_t0']:+.0f}m){boundary} {rec['reason']}")
        print(f"    HEALTH: progress={h['progress']} adverse={h['adverse']} net={h['net']:+.3f}% consecutive={h['consecutive']} worst_path={h['worst_path']:+.3f}%")
        print("    HOLDING OLD THESIS: " + " ".join(f"{k}={fmt(v)}" for k, v in p.items() if k.startswith("ret_")))
        print(f"    120M RANGE: best={fmt(p['best_120m'])} worst={fmt(p['worst_120m'])}")


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.5 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.5 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rr = [r for r in records if r["direction"] == direction]
        print(f"\n{direction}: N={len(rr)}")
        for level, key in (("PRESSURE", "pressure"), ("THESIS_BROKEN", "broken"), ("OPPOSITE_DEVELOPING", "opposite")):
            vals = [r[key] for r in rr if r[key] is not None]
            if not vals:
                print(f"  {level:<22} N=0")
                continue
            times = sorted(x["minutes_to_t0"] for x in vals)
            med = times[len(times)//2] if len(times) % 2 else (times[len(times)//2 - 1] + times[len(times)//2]) / 2.0
            mean = sum(times) / len(times)
            boundary = sum(1 for x in vals if x["boundary"])
            print(f"  {level:<22} N={len(vals)} mean={mean:.1f}m median={med:.1f}m earliest={max(times):.1f}m boundary={boundary}")

        broken = [r["broken"] for r in rr if r["broken"] is not None]
        if broken:
            improved = 0
            worsened = 0
            recovered = 0
            continued = 0
            for b in broken:
                p = b["post"]
                if p["ret_60m"] is not None:
                    if p["ret_60m"] < 0:
                        improved += 1
                    elif p["ret_60m"] > 0:
                        worsened += 1
                if p["best_120m"] is not None and p["best_120m"] >= 0.20:
                    recovered += 1
                if p["worst_120m"] is not None and p["worst_120m"] <= -0.50:
                    continued += 1
            print(f"  EXIT-VS-HOLD @60m    improved={improved} worsened={worsened} unknown={len(broken)-improved-worsened}")
            print(f"  OLD THESIS RECOVERED 120m: {recovered}/{len(broken)}")
            print(f"  OLD THESIS CONTINUED FAILING 120m: {continued}/{len(broken)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="KISS V5.6.5 causal trade thesis survival test")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--cases", type=int, default=20)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    case_no = 0

    for symbol in args.symbols:
        rows30 = load(symbol, "30m", args.limit)
        rows5 = load(symbol, "5m", args.limit)
        events = transitions(rows30)
        total += len(events)
        for event in events:
            result = run_case(rows5, event)
            if not result["usable"]:
                skipped += 1
                continue
            rec = {"symbol": symbol, "direction": f"{event['from']}->{event['to']}", **result}
            records.append(rec)
            case_no += 1
            if case_no <= args.cases:
                print_case(case_no, symbol, event, result)

    summarize(records, total, skipped)
    print("\nV5.6.5 KEY QUESTION: was the existing trade actually safer to exit than to hold?")
    print("V5.6.5 SEPARATION: thesis failure is an EXIT concept; opposite development is a separate reversal concept.")
    print("V5.6.5 is a causal research test, not a trading rule.")


if __name__ == "__main__":
    main()
