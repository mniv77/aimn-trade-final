"""KISS V5.6.6 — Causal Thesis Survival / Recovery Test.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.5 showed that a simple THESIS_BROKEN label is not enough:
about half of the observed transitions recovered after the proposed break.
V5.6.6 therefore asks the harder question:

    DID THE DAMAGE ACTUALLY SURVIVE?

For an existing trade, every completed 5m candle is evaluated causally.
The state machine is deliberately simple:

    HEALTHY -> PRESSURE -> FAILURE_CANDIDATE
                         |
                         +-> RECOVERY -> THESIS_SURVIVED
                         |
                         +-> CONTINUED_FAILURE -> TRUE_FAILURE

A TRUE_FAILURE is an EXIT candidate. It is NOT an automatic reversal.
After TRUE_FAILURE, opposite structure is measured independently.

The important evaluation is not merely whether price looked bad. It is:

    If we had exited at the candidate candle, was that actually better than
    holding the original trade over the next 15/30/60/120 minutes?

Recognition uses only completed 5m candles and already-confirmed 3-bar swings.
Future candles are used only to determine whether the candidate survived,
recovered, or continued failing. The official 30m MA transition is only a
reference timestamp.
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
RECOVERY_WINDOW = 60
RECOVERY_THRESHOLD = 0.20
CONTINUATION_THRESHOLD = -0.50
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
    return {"adverse": adverse, "progress": progress, "net": net, "consecutive": consecutive}


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


def pressure(h: Dict[str, Any]) -> bool:
    return h["adverse"] >= 3 and h["net"] <= -0.10


def failure_candidate(h: Dict[str, Any], structural_break: bool) -> bool:
    persistent = h["consecutive"] >= 2 and h["net"] <= -0.20
    severe_balance = h["adverse"] >= 6 and h["net"] <= -0.30
    return structural_break or persistent or severe_balance


def forward_values(rows: Sequence[Dict[str, Any]], idx: int, prior: str, minutes: int = POST_MINUTES) -> List[float]:
    base = rows[idx]["close"]
    vals: List[float] = []
    for j in range(idx + 1, len(rows)):
        elapsed = (rows[j]["timestamp"] + timedelta(minutes=5) - (rows[idx]["timestamp"] + timedelta(minutes=5))).total_seconds() / 60.0
        if elapsed > minutes:
            break
        vals.append(signed_return(base, rows[j]["close"], prior))
    return vals


def recovery_test(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    vals = forward_values(rows, idx, prior, RECOVERY_WINDOW)
    if not vals:
        return {"status": "UNKNOWN", "best": None, "worst": None, "time_to_recovery": None}
    best = max(vals)
    worst = min(vals)
    status = "RECOVERED" if best >= RECOVERY_THRESHOLD else ("CONTINUED_FAILURE" if worst <= CONTINUATION_THRESHOLD else "UNRESOLVED")
    recovery_time = None
    if status == "RECOVERED":
        for k, v in enumerate(vals, start=1):
            if v >= RECOVERY_THRESHOLD:
                recovery_time = k * 5
                break
    return {"status": status, "best": best, "worst": worst, "time_to_recovery": recovery_time}


def outcomes(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Optional[float]]:
    base = rows[idx]["close"]
    out: Dict[str, Optional[float]] = {}
    for mins in (15, 30, 60, 120):
        j = close_index(rows, rows[idx]["timestamp"] + timedelta(minutes=mins))
        out[f"ret_{mins}m"] = None if j is None else signed_return(base, rows[j]["close"], prior)
    return out


def run_case(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    stage = "HEALTHY"
    pressure_idx: Optional[int] = None
    candidate_idx: Optional[int] = None
    true_failure_idx: Optional[int] = None
    opposite_idx: Optional[int] = None
    reasons: Dict[str, str] = {}
    survival_status = "NOT_TESTED"

    # Phase 1: strictly forward. Candidate means damage is serious enough to
    # test, not that we have already proven the trend is dead.
    for idx in range(start, end + 1):
        h = health(rows, idx, prior)
        structural, structural_reason = old_structure_break(rows, idx, prior)
        if stage == "HEALTHY" and pressure(h):
            stage = "PRESSURE"
            pressure_idx = idx
            reasons["pressure"] = "persistent_adverse_balance"
        if stage == "PRESSURE" and candidate_idx is None and failure_candidate(h, structural):
            candidate_idx = idx
            reasons["candidate"] = structural_reason if structural else "persistent_adverse_pressure"
            break

    # Phase 2: survival test begins at the first candidate. We do not label it
    # TRUE_FAILURE until subsequent completed candles show the damage survived.
    if candidate_idx is not None:
        test_end = min(end, candidate_idx + int(RECOVERY_WINDOW / 5))
        for idx in range(candidate_idx, test_end + 1):
            rt = recovery_test(rows, idx, prior)
            if rt["status"] == "CONTINUED_FAILURE":
                true_failure_idx = idx
                survival_status = "CONTINUED_FAILURE"
                reasons["true_failure"] = "damage_survived"
                break
            if rt["status"] == "RECOVERED":
                survival_status = "THESIS_SURVIVED"
                reasons["survived"] = "price_recovered"
                break
        if true_failure_idx is None and survival_status == "NOT_TESTED":
            survival_status = "UNRESOLVED"

    # Phase 3: once true failure exists, independently look for opposite
    # structure. This is never used to decide whether the old thesis survived.
    if true_failure_idx is not None:
        for idx in range(true_failure_idx, end + 1):
            opp, reason = opposite_developing(rows, idx, prior)
            if opp:
                opposite_idx = idx
                reasons["opposite"] = reason
                break

    def rec(level: str, idx: Optional[int], reason: str) -> Optional[Dict[str, Any]]:
        if idx is None:
            return None
        known = rows[idx]["timestamp"] + timedelta(minutes=5)
        vals = outcomes(rows, idx, prior)
        return {
            "level": level,
            "idx": idx,
            "time": known,
            "minutes_to_t0": (t0 - known).total_seconds() / 60.0,
            "boundary": idx == start,
            "reason": reason,
            "recovery": recovery_test(rows, idx, prior),
            "outcomes": vals,
        }

    return {
        "usable": True,
        "pressure": rec("PRESSURE", pressure_idx, reasons.get("pressure", "")),
        "candidate": rec("FAILURE_CANDIDATE", candidate_idx, reasons.get("candidate", "")),
        "true_failure": rec("TRUE_FAILURE", true_failure_idx, reasons.get("true_failure", "")),
        "opposite": rec("OPPOSITE_DEVELOPING", opposite_idx, reasons.get("opposite", "")),
        "survival_status": survival_status,
    }


def fmt(v: Optional[float]) -> str:
    return "--" if v is None else f"{v:+.3f}%"


def print_case(n: int, symbol: str, event: Dict[str, Any], r: Dict[str, Any]) -> None:
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time']} official_price={event['price']:.2f}")
    print(f"  SURVIVAL RESULT: {r['survival_status']}")
    for label, key in (("PRESSURE", "pressure"), ("FAILURE_CANDIDATE", "candidate"), ("TRUE_FAILURE", "true_failure"), ("OPPOSITE_DEVELOPING", "opposite")):
        rec = r[key]
        if rec is None:
            print(f"  {label:<22} NOT REACHED")
            continue
        boundary = " [WINDOW_BOUNDARY]" if rec["boundary"] else ""
        rr = rec["recovery"]
        print(f"  {label:<22} {rec['time']} ({rec['minutes_to_t0']:+.0f}m){boundary} {rec['reason']}")
        print(f"    SURVIVAL TEST: {rr['status']} best={fmt(rr['best'])} worst={fmt(rr['worst'])} recovery_time={rr['time_to_recovery'] or '--'}m")
        print("    OLD THESIS RETURNS: " + " ".join(f"{k}={fmt(v)}" for k, v in rec["outcomes"].items()))


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.6 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.6 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        rs = [x for x in records if x["direction"] == direction]
        print(f"\n{direction} N={len(rs)}")
        for status in ("THESIS_SURVIVED", "CONTINUED_FAILURE", "UNRESOLVED", "NOT_TESTED"):
            print(f"  {status:<22} {sum(x['result']['survival_status'] == status for x in rs)}")
        candidates = [x["result"]["candidate"] for x in rs if x["result"]["candidate"]]
        true_fail = [x["result"]["true_failure"] for x in rs if x["result"]["true_failure"]]
        opposite = [x["result"]["opposite"] for x in rs if x["result"]["opposite"]]
        print(f"  FAILURE CANDIDATE N={len(candidates)}")
        print(f"  TRUE FAILURE N={len(true_fail)}")
        print(f"  OPPOSITE DEVELOPING N={len(opposite)}")
        if candidates:
            b = sum(x["boundary"] for x in candidates)
            print(f"  CANDIDATE BOUNDARY HITS={b}")
        if true_fail:
            improved = worsened = unknown = 0
            for x in true_fail:
                v = x["outcomes"].get("ret_60m")
                if v is None:
                    unknown += 1
                elif v < 0:
                    improved += 1
                else:
                    worsened += 1
            print(f"  TRUE FAILURE @60M OLD-THESIS: against={improved} favorable={worsened} unknown={unknown}")
    all_true = [x["result"]["true_failure"] for x in records if x["result"]["true_failure"]]
    if all_true:
        improved = sum((x["outcomes"].get("ret_60m") is not None and x["outcomes"]["ret_60m"] < 0) for x in all_true)
        favorable = sum((x["outcomes"].get("ret_60m") is not None and x["outcomes"]["ret_60m"] >= 0) for x in all_true)
        print(f"\nCOMBINED TRUE FAILURE @60M: {improved} against old thesis / {favorable} favorable")
    print("\nV5.6.6 KEY TEST: did the damage actually survive?")
    print("V5.6.6 KEY DECISION: EXIT only becomes justified when failure survives recovery testing.")
    print("V5.6.6 is causal research, not a trading rule.")


def main() -> None:
    ap = argparse.ArgumentParser(description="KISS V5.6.6 thesis survival / recovery research")
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
