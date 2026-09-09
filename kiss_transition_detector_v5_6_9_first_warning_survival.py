"""KISS V5.6.9 — First Warning -> Survival Decision.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.8 showed that the FIRST causal deterioration point inside an episode
performed materially better than waiting for the strongest/last candidate.
V5.6.9 asks the next question:

    Can the FIRST warning be treated as a warning, followed by a causal
    survival test, instead of treating the warning itself as an exit?

Flow:
    FIRST WARNING -> SURVIVAL TEST -> SURVIVES / FAILS
                                      |
                                      +--> TRUE FAILURE -> OPPOSITE DEVELOPING?

Candidate selection uses only completed 5m candles available at that moment.
Future candles are used only after the warning to evaluate survival truth.

Important: this is a research truth test, not a trading rule. The survival
label deliberately uses a future window, so it cannot be used directly by a
live system. The useful output is whether a simple causal warning can be
followed by a later decision point that improves exit-vs-hold outcomes.
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
MIN_HISTORY_MINUTES = 120
SURVIVAL_MINUTES = 60
POST_MINUTES = 120
EXIT_BUFFER = 0.10
RECOVERY_THRESHOLD = 0.20
FAILURE_THRESHOLD = -0.50
EPISODE_GAP_MINUTES = 15
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


def close_time(r: Dict[str, Any]) -> datetime:
    return r["timestamp"] + timedelta(minutes=5)


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
                "time": close_time(rows[i]),
                "price": rows[i]["close"],
            })
    return out


def nearest_completed_close(rows: Sequence[Dict[str, Any]], target: datetime) -> Tuple[Optional[int], Optional[float]]:
    best = None
    best_diff = None
    for i, r in enumerate(rows):
        ct = close_time(r)
        if ct > target:
            continue
        diff = (target - ct).total_seconds() / 60.0
        if best_diff is None or diff < best_diff:
            best = i
            best_diff = diff
    return best, best_diff


def exact_close_index(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    for i, r in enumerate(rows):
        if close_time(r) == target:
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
    consecutive = 0
    for x in reversed(moves):
        if x < 0:
            consecutive += 1
        else:
            break
    net = signed_return(closes[0], closes[-1], prior) if len(closes) > 1 else 0.0
    return {"adverse": adverse, "consecutive": consecutive, "net": net}


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


def candidate_signal(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str, float]:
    """FIRST-warning candidate using causal information only."""
    h = health(rows, idx, prior)
    structural, reason = structure_break(rows, idx, prior)
    persistent = h["consecutive"] >= 2 and h["net"] <= -0.20
    balanced = h["adverse"] >= 6 and h["net"] <= -0.30

    score = 0.0
    if structural:
        score += 3.0
    if persistent:
        score += 2.0
    if balanced:
        score += 1.0
    score += min(1.0, max(0.0, -h["net"]))
    score += min(0.5, h["consecutive"] * 0.10)

    if structural:
        return True, reason, score
    if persistent:
        return True, "two_or_more_consecutive_adverse_closes", score
    if balanced:
        return True, "persistent_adverse_balance", score
    return False, "", score


def survival_test(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    """Evaluate recovery/continued failure using future candles only."""
    base = rows[idx]["close"]
    base_time = close_time(rows[idx])
    future: List[int] = []
    for j in range(idx + 1, len(rows)):
        elapsed = (close_time(rows[j]) - base_time).total_seconds() / 60.0
        if elapsed > SURVIVAL_MINUTES:
            break
        future.append(j)
    if not future:
        return {"status": "UNKNOWN", "best": None, "worst": None, "ret60": None, "recovery_min": None}

    vals = [signed_return(base, rows[j]["close"], prior) for j in future]
    best = max(vals)
    worst = min(vals)
    recovery_min = None
    for j in future:
        r = signed_return(base, rows[j]["close"], prior)
        if r >= RECOVERY_THRESHOLD:
            recovery_min = (close_time(rows[j]) - base_time).total_seconds() / 60.0
            break

    if recovery_min is not None:
        status = "SURVIVED"
    elif worst <= FAILURE_THRESHOLD:
        status = "TRUE_FAILURE"
    else:
        status = "UNRESOLVED"
    return {"status": status, "best": best, "worst": worst, "ret60": vals[-1], "recovery_min": recovery_min}


def outcome_at(rows: Sequence[Dict[str, Any]], idx: int, prior: str, minutes: int) -> Optional[float]:
    j = exact_close_index(rows, close_time(rows[idx]) + timedelta(minutes=minutes))
    if j is None:
        return None
    return signed_return(rows[idx]["close"], rows[j]["close"], prior)


def opposite_developing(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    """Causal-only opposite structure after a warning/true failure point."""
    for j in range(idx + 1, min(len(rows), idx + 13)):
        structural, reason = structure_break(rows, j, prior)
        if structural:
            return True, reason
    return False, ""


def run_case(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    requested_start = t0 - timedelta(minutes=LOOKBACK_MINUTES)
    start, start_diff = nearest_completed_close(rows, requested_start)
    if start is None:
        return {"usable": False}
    end, end_diff = nearest_completed_close(rows, t0 + timedelta(minutes=POST_MINUTES))
    if end is None or end <= start:
        return {"usable": False}
    available_history = (t0 - close_time(rows[start])).total_seconds() / 60.0
    if available_history < MIN_HISTORY_MINUTES:
        return {"usable": False}

    # Build causal candidates first. No future outcome is consulted here.
    candidates: List[Dict[str, Any]] = []
    for idx in range(start, end + 1):
        ok, reason, score = candidate_signal(rows, idx, prior)
        if not ok:
            continue
        candidates.append({
            "idx": idx,
            "time": close_time(rows[idx]),
            "minutes_to_t0": (t0 - close_time(rows[idx])).total_seconds() / 60.0,
            "boundary": idx == start,
            "reason": reason,
            "score": score,
        })

    # Cluster overlapping candidates. FIRST is the earliest causal warning in
    # each episode; the survival test starts only after that warning.
    episodes: List[List[Dict[str, Any]]] = []
    for c in candidates:
        if not episodes:
            episodes.append([c])
            continue
        gap = (c["time"] - episodes[-1][-1]["time"]).total_seconds() / 60.0
        if gap <= EPISODE_GAP_MINUTES:
            episodes[-1].append(c)
        else:
            episodes.append([c])

    episode_results: List[Dict[str, Any]] = []
    for ep in episodes:
        first = min(ep, key=lambda x: x["time"])
        s = survival_test(rows, first["idx"], prior)
        opp = False
        opp_reason = ""
        if s["status"] == "TRUE_FAILURE":
            opp, opp_reason = opposite_developing(rows, first["idx"], prior)
        episode_results.append({
            "first": first,
            "survival": s,
            "opposite": opp,
            "opposite_reason": opp_reason,
            "ret15": outcome_at(rows, first["idx"], prior, 15),
            "ret30": outcome_at(rows, first["idx"], prior, 30),
            "ret60": outcome_at(rows, first["idx"], prior, 60),
            "ret120": outcome_at(rows, first["idx"], prior, 120),
        })

    return {
        "usable": True,
        "requested_start": requested_start,
        "actual_start": close_time(rows[start]),
        "start_offset": start_diff,
        "actual_end": close_time(rows[end]),
        "end_offset": end_diff,
        "available_history": available_history,
        "episodes": episode_results,
    }


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.9 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.9 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INSUFFICIENT 5M COVERAGE: {skipped}")

    all_eps: List[Dict[str, Any]] = []
    for rec in records:
        all_eps.extend(rec["result"]["episodes"])
    print(f"FIRST-WARNING EPISODES: {len(all_eps)}")
    print(f"EPISODE GAP RULE: <= {EPISODE_GAP_MINUTES} MINUTES")

    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        selected = all_eps if direction == "ALL" else [
            e for rec in records if rec["direction"] == direction for e in rec["result"]["episodes"]
        ]
        print(f"\n{direction} FIRST-WARNING SURVIVAL")
        print(f"EPISODES: {len(selected)}")
        for status in ("SURVIVED", "TRUE_FAILURE", "UNRESOLVED", "UNKNOWN"):
            print(f"  {status}: {sum(e['survival']['status'] == status for e in selected)}")
        failures = [e for e in selected if e["survival"]["status"] == "TRUE_FAILURE"]
        if failures:
            print(f"  TRUE_FAILURE WITH OPPOSITE DEVELOPING: {sum(e['opposite'] for e in failures)}")
        valid = [e for e in selected if e["ret60"] is not None]
        good = [e for e in valid if e["ret60"] <= -EXIT_BUFFER]
        false = [e for e in valid if e["ret60"] >= EXIT_BUFFER]
        neutral = [e for e in valid if -EXIT_BUFFER < e["ret60"] < EXIT_BUFFER]
        print(f"  FIRST-WARNING HOLD-60 VALID: {len(valid)}")
        print(f"  IF EXITED AT FIRST WARNING: GOOD_EXIT={len(good)} FALSE_EXIT={len(false)} NEUTRAL={len(neutral)}")
        print(f"  FIRST-WARNING AVG HOLD-60: {avg([e['ret60'] for e in valid]):+.3f}%")
        failure_rets = [e["ret60"] for e in failures if e["ret60"] is not None]
        survive_rets = [e["ret60"] for e in selected if e["survival"]["status"] == "SURVIVED" and e["ret60"] is not None]
        print(f"  TRUE_FAILURE AVG HOLD-60: {avg(failure_rets):+.3f}%")
        print(f"  SURVIVED AVG HOLD-60: {avg(survive_rets):+.3f}%")
        times = [e["first"]["minutes_to_t0"] for e in selected]
        print(f"  FIRST WARNING AVG MINUTES TO T0: {avg(times):+.1f}")

    print("\nV5.6.9 REPRESENTATIVE FIRST-WARNING CASES")
    shown = 0
    for rec in records:
        for e in rec["result"]["episodes"]:
            if shown >= 12:
                break
            f = e["first"]
            s = e["survival"]
            print(
                f"{rec['symbol']} {rec['direction']} FIRST {f['time']} "
                f"T0={rec['event']['time']} ({f['minutes_to_t0']:+.0f}m) "
                f"reason={f['reason']} score={f['score']:.2f} "
                f"SURVIVAL={s['status']} best={s['best']} worst={s['worst']} "
                f"ret60={e['ret60']} opposite={e['opposite']}"
            )
            shown += 1
        if shown >= 12:
            break

    print("\nV5.6.9 KEY TEST: CAN FIRST WARNING BE FOLLOWED BY A SURVIVAL DECISION?")
    print("FIRST WARNING is causal; survival truth is evaluated only after the warning.")
    print("A survived warning should not force an exit. A failure that survives recovery testing becomes an EXIT candidate.")
    print("TRUE FAILURE and OPPOSITE DEVELOPING remain separate decisions.")
    print("V5.6.9 is research only — no trading rule or engine change.")


def main() -> None:
    ap = argparse.ArgumentParser(description="KISS V5.6.9 first-warning survival research")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    for symbol in args.symbols:
        rows = load(symbol, "30m", 5000)
        rows5 = load(symbol, "5m", 50000)
        if not rows or not rows5:
            continue
        events = transitions(rows)
        total += len(events)
        for event in events:
            result = run_case(rows5, event)
            if not result.get("usable"):
                skipped += 1
                continue
            records.append({"symbol": symbol, "direction": f"{event['from']}->{event['to']}", "event": event, "result": result})

    summarize(records, total, skipped)


if __name__ == "__main__":
    main()
