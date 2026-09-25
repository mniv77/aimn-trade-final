"""KISS V5.6.10 — Causal Decision Point Test.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.9 established an important distinction:

    FIRST WARNING != EXIT

A warning can survive and recover, or it can continue into a genuine failure.
V5.6.10 asks the next practical question:

    After the FIRST WARNING, when is the best CAUSAL decision point?

For every deterioration episode we compare decision policies that can be
implemented without knowing the future:

    IMMEDIATE      = act at the first causal warning
    WAIT_15M       = wait 15 minutes, then act only if deterioration is still present
    WAIT_30M       = wait 30 minutes, then act only if deterioration is still present
    WAIT_45M       = wait 45 minutes, then act only if deterioration is still present
    WAIT_60M       = wait 60 minutes, then act only if deterioration is still present

At each decision point the policy sees only completed 5m candles available
at that moment. Future candles are used ONLY afterward to score the decision.

A decision is scored against HOLDING the old thesis for 60 minutes:

    GOOD_EXIT  = holding loses <= -0.10%
    FALSE_EXIT = holding gains >= +0.10%
    NEUTRAL    = between those values
    UNKNOWN    = insufficient future data

The key output is not the official 30m MA transition. The key output is:

    which causal delay gives the best exit-vs-hold result,
    separately for LONG->SHORT and SHORT->LONG?

This is still a research truth test. It does not create a trading rule.
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
EVAL_MINUTES = 60
POST_MINUTES = 120
EXIT_BUFFER = 0.10
EPISODE_GAP_MINUTES = 15
DECISION_DELAYS = (0, 15, 30, 45, 60)
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


def decision_index(rows: Sequence[Dict[str, Any]], warning_idx: int, prior: str, delay: int) -> Optional[int]:
    """Choose a decision point using only data available by the delay."""
    target = close_time(rows[warning_idx]) + timedelta(minutes=delay)
    idx, _ = nearest_completed_close(rows, target)
    if idx is None or idx < warning_idx:
        return None

    # At the decision point the deterioration must still be present.
    # This is deliberately causal: no future outcome is consulted.
    if delay == 0:
        ok, _, _ = candidate_signal(rows, idx, prior)
        return idx if ok else None

    ok, _, _ = candidate_signal(rows, idx, prior)
    if ok:
        return idx

    # If the warning has relaxed by this exact point, the policy does not exit.
    return None


def score_exit_vs_hold(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    base = rows[idx]["close"]
    target = close_time(rows[idx]) + timedelta(minutes=EVAL_MINUTES)
    j = exact_close_index(rows, target)
    if j is None:
        return {"status": "UNKNOWN", "ret60": None}
    ret60 = signed_return(base, rows[j]["close"], prior)
    if ret60 <= -EXIT_BUFFER:
        status = "GOOD_EXIT"
    elif ret60 >= EXIT_BUFFER:
        status = "FALSE_EXIT"
    else:
        status = "NEUTRAL"
    return {"status": status, "ret60": ret60}


def evaluate_policy(rows: Sequence[Dict[str, Any]], warning_idx: int, prior: str, delay: int) -> Dict[str, Any]:
    idx = decision_index(rows, warning_idx, prior, delay)
    if idx is None:
        return {
            "acted": False, "idx": None, "time": None, "status": "NO_EXIT",
            "ret60": None, "minutes_to_t0": None,
        }
    scored = score_exit_vs_hold(rows, idx, prior)
    t = close_time(rows[idx])
    return {
        "acted": True,
        "idx": idx,
        "time": t,
        "status": scored["status"],
        "ret60": scored["ret60"],
        "minutes_to_t0": None,
    }


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

    # Discover causal warning candidates first. No future information here.
    candidates: List[Dict[str, Any]] = []
    for idx in range(start, end + 1):
        ok, reason, score = candidate_signal(rows, idx, prior)
        if not ok:
            continue
        candidates.append({
            "idx": idx,
            "time": close_time(rows[idx]),
            "reason": reason,
            "score": score,
        })

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

    results: List[Dict[str, Any]] = []
    for ep in episodes:
        first = min(ep, key=lambda x: x["time"])
        policy_results: Dict[int, Dict[str, Any]] = {}
        for delay in DECISION_DELAYS:
            r = evaluate_policy(rows, first["idx"], prior, delay)
            if r["acted"]:
                r["minutes_to_t0"] = (t0 - r["time"]).total_seconds() / 60.0
            policy_results[delay] = r
        results.append({
            "first": first,
            "policies": policy_results,
        })

    return {
        "usable": True,
        "requested_start": requested_start,
        "actual_start": close_time(rows[start]),
        "start_offset": start_diff,
        "actual_end": close_time(rows[end]),
        "end_offset": end_diff,
        "available_history": available_history,
        "episodes": results,
    }


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def pct(n: int, d: int) -> float:
    return (100.0 * n / d) if d else 0.0


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.10 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.10 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INSUFFICIENT 5M COVERAGE: {skipped}")
    all_eps: List[Dict[str, Any]] = []
    for rec in records:
        all_eps.extend(rec["result"]["episodes"])
    print(f"FIRST-WARNING EPISODES: {len(all_eps)}")
    print(f"DECISION DELAYS: {DECISION_DELAYS} minutes")
    print(f"EPISODE GAP RULE: <= {EPISODE_GAP_MINUTES} MINUTES")
    print("SCORING: GOOD_EXIT if HOLD-60 <= -0.10%, FALSE_EXIT if HOLD-60 >= +0.10%")

    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        selected = all_eps if direction == "ALL" else [
            e for rec in records if rec["direction"] == direction for e in rec["result"]["episodes"]
        ]
        print(f"\n{direction} CAUSAL DECISION-POINT TEST")
        print(f"EPISODES: {len(selected)}")
        for delay in DECISION_DELAYS:
            acted = [e["policies"][delay] for e in selected if e["policies"][delay]["acted"]]
            good = [r for r in acted if r["status"] == "GOOD_EXIT"]
            false = [r for r in acted if r["status"] == "FALSE_EXIT"]
            neutral = [r for r in acted if r["status"] == "NEUTRAL"]
            valid = [r for r in acted if r["ret60"] is not None]
            print(
                f"  WAIT_{delay:02d}M: ACTED={len(acted)} VALID={len(valid)} "
                f"GOOD={len(good)} ({pct(len(good),len(valid)):.1f}%) "
                f"FALSE={len(false)} ({pct(len(false),len(valid)):.1f}%) "
                f"NEUTRAL={len(neutral)} "
                f"AVG_HOLD60={avg([r['ret60'] for r in valid]):+.3f}%"
            )
            acted_times = [r["minutes_to_t0"] for r in acted if r["minutes_to_t0"] is not None]
            if acted_times:
                print(f"             AVG MINUTES TO T0: {avg(acted_times):+.1f}")

    print("\nV5.6.10 REPRESENTATIVE DECISION CASES")
    shown = 0
    for rec in records:
        for e in rec["result"]["episodes"]:
            if shown >= 12:
                break
            f = e["first"]
            print(
                f"{rec['symbol']} {rec['direction']} FIRST {f['time']} "
                f"T0={rec['event']['time']} ({(rec['event']['time']-f['time']).total_seconds()/60.0:+.0f}m) "
                f"reason={f['reason']} score={f['score']:.2f}"
            )
            for delay in DECISION_DELAYS:
                r = e["policies"][delay]
                if r["acted"]:
                    print(
                        f"  WAIT_{delay:02d}M -> {r['time']} "
                        f"({r['minutes_to_t0']:+.0f}m to T0) {r['status']} "
                        f"hold60={r['ret60']:+.3f}%"
                    )
                else:
                    print(f"  WAIT_{delay:02d}M -> NO_EXIT")
            shown += 1
        if shown >= 12:
            break

    print("\nV5.6.10 KEY TEST")
    print("FIRST WARNING is a NOTICE, not automatically an EXIT.")
    print("Every WAIT policy makes its decision using only completed 5m information available at that point.")
    print("Future candles are used only after the causal decision to score exit-vs-hold.")
    print("The goal is to identify a useful causal decision delay, not to predict the 30m MA transition.")
    print("V5.6.10 is research only — no trading rule or engine change.")


def main() -> None:
    ap = argparse.ArgumentParser(description="KISS V5.6.10 causal decision point research")
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
            records.append({
                "symbol": symbol,
                "direction": f"{event['from']}->{event['to']}",
                "event": event,
                "result": result,
            })

    summarize(records, total, skipped)


if __name__ == "__main__":
    main()
