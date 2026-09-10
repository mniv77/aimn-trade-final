#!/usr/bin/env python3
"""
V5.6.12 — Trend Health Persistence

Research only.

Purpose:
V5.6.11 showed that the first warning is useful as a NOTICE, but the
binary THESIS_FAILED state fired too easily. V5.6.12 therefore treats
trend damage as a persistent, reversible process instead of a one-bar
failure decision.

Causal state machine:
    HEALTHY -> STRESSED -> DETERIORATING -> CRITICAL

The state can recover one level when the old trend resumes. A single
bad candle cannot jump HEALTHY directly to CRITICAL.

At every completed 5m candle we measure only information available at
that candle close. Future candles are used only after a state decision
to score EXIT-vs-HOLD.

This experiment does NOT:
- change the KISS engine
- place orders
- write to the database
- use RSI
- use ML
- create an opposite-direction entry rule

The official 30m MA transition remains only a reference point.
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import mysql.connector

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
SWING_LOOKBACK = 3
LOOKBACK_MINUTES = 480
POST_MINUTES = 120
EVAL_MINUTES = 60
EPISODE_GAP_MINUTES = 15
EXIT_BUFFER = 0.10

DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a / b - 1.0) * 100.0


def avg(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def state_at(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def opposite(direction: str) -> str:
    return "SHORT" if direction == "LONG->SHORT" else "LONG"


def old_sign(direction: str) -> float:
    return 1.0 if direction == "LONG->SHORT" else -1.0


def nearest_completed_close(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    best = None
    best_diff = None
    for i, r in enumerate(rows):
        close_at = r["timestamp"] + timedelta(minutes=5)
        if close_at <= target:
            d = (target - close_at).total_seconds()
            if d <= 300 and (best_diff is None or d < best_diff):
                best = i
                best_diff = d
    return best


def causal_swing_high(rows: Sequence[Dict[str, Any]], idx: int) -> Optional[float]:
    j = idx - SWING_LOOKBACK
    if j < SWING_LOOKBACK or j + SWING_LOOKBACK >= len(rows):
        return None
    h = float(rows[j]["high"])
    for k in range(j - SWING_LOOKBACK, j + SWING_LOOKBACK + 1):
        if float(rows[k]["high"]) > h:
            return None
    return h


def causal_swing_low(rows: Sequence[Dict[str, Any]], idx: int) -> Optional[float]:
    j = idx - SWING_LOOKBACK
    if j < SWING_LOOKBACK or j + SWING_LOOKBACK >= len(rows):
        return None
    lo = float(rows[j]["low"])
    for k in range(j - SWING_LOOKBACK, j + SWING_LOOKBACK + 1):
        if float(rows[k]["low"]) < lo:
            return None
    return lo


def health_features(rows: Sequence[Dict[str, Any]], idx: int, direction: str) -> Dict[str, Any]:
    start = max(0, idx - 12)
    closes = [float(r["close"]) for r in rows]
    c = closes[idx]
    old = old_sign(direction)
    recent = closes[start:idx + 1]
    if len(recent) < 3:
        return {"adverse": 0, "net": 0.0, "consecutive": 0, "structure": False, "severe": False, "score": 0.0}

    moves = [pct(recent[i], recent[i - 1]) for i in range(1, len(recent))]
    signed_moves = [m * old for m in moves]
    adverse = sum(1 for m in signed_moves if m < 0)
    consecutive = 0
    for m in reversed(signed_moves):
        if m < 0:
            consecutive += 1
        else:
            break
    net = pct(c, recent[0]) * old

    structure = False
    if direction == "LONG->SHORT":
        lows = []
        for j in range(max(SWING_LOOKBACK * 2, idx - 15), idx + 1):
            x = causal_swing_low(rows, j)
            if x is not None:
                lows.append((j, x))
        if lows:
            prior = lows[-1][1]
            structure = c < prior * (1.0 - 0.0005)
    else:
        highs = []
        for j in range(max(SWING_LOOKBACK * 2, idx - 15), idx + 1):
            x = causal_swing_high(rows, j)
            if x is not None:
                highs.append((j, x))
        if highs:
            prior = highs[-1][1]
            structure = c > prior * (1.0 + 0.0005)

    severe = net <= -0.50 or consecutive >= 3 or (structure and adverse >= 4)
    score = 0.0
    if adverse >= 2:
        score += 1.0
    if consecutive >= 2:
        score += 1.0
    if net <= -0.20:
        score += 1.0
    if net <= -0.50:
        score += 1.0
    if structure:
        score += 2.0
    return {"adverse": adverse, "net": net, "consecutive": consecutive, "structure": structure, "severe": severe, "score": score}


def classify_health(f: Dict[str, Any]) -> str:
    # Sequential thresholds: no direct HEALTHY -> CRITICAL jump.
    if f["severe"] and f["score"] >= 4.0:
        return "CRITICAL"
    if f["score"] >= 2.0 or f["net"] <= -0.20:
        return "DETERIORATING"
    if f["adverse"] >= 1 or f["net"] < -0.05:
        return "STRESSED"
    return "HEALTHY"


def transition_state(previous: str, observed: str) -> str:
    levels = {"HEALTHY": 0, "STRESSED": 1, "DETERIORATING": 2, "CRITICAL": 3}
    p = levels[previous]
    o = levels[observed]
    if o > p + 1:
        o = p + 1
    if o < p - 1:
        o = p - 1
    return min(levels, key=lambda k: abs(levels[k] - o))


def hold_return(rows: Sequence[Dict[str, Any]], idx: int, direction: str, minutes: int) -> Optional[float]:
    target = rows[idx]["timestamp"] + timedelta(minutes=5 + minutes)
    j = nearest_completed_close(rows, target)
    if j is None or j <= idx:
        return None
    return pct(float(rows[j]["close"]), float(rows[idx]["close"])) * old_sign(direction)


def evaluate_decision(rows: Sequence[Dict[str, Any]], idx: int, direction: str) -> Dict[str, Any]:
    r60 = hold_return(rows, idx, direction, EVAL_MINUTES)
    if r60 is None:
        status = "UNKNOWN"
    elif r60 <= -EXIT_BUFFER:
        status = "GOOD_EXIT"
    elif r60 >= EXIT_BUFFER:
        status = "FALSE_EXIT"
    else:
        status = "NEUTRAL"
    return {"status": status, "ret15": hold_return(rows, idx, direction, 15), "ret30": hold_return(rows, idx, direction, 30), "ret60": r60, "ret120": hold_return(rows, idx, direction, 120)}


def load_rows(symbol: str, timeframe: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT timestamp, open, high, low, close, volume FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY timestamp ASC",
            (symbol, timeframe),
        )
        return list(cur.fetchall())
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


def find_transitions(rows30: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [float(r["close"]) for r in rows30]
    out = []
    prev = "FLAT"
    for i in range(len(rows30)):
        s = state_at(closes, i)
        if s in ("LONG", "SHORT") and prev in ("LONG", "SHORT") and s != prev:
            out.append({"time": rows30[i]["timestamp"] + timedelta(minutes=30), "direction": f"{prev}->{s}"})
        prev = s
    return out


def candidate_reason(f: Dict[str, Any]) -> Optional[str]:
    if f["structure"]:
        return "structure_break"
    if f["consecutive"] >= 2 and f["net"] <= -0.20:
        return "persistent_adverse"
    if f["severe"]:
        return "severe_balance"
    if f["adverse"] >= 3 and f["net"] <= -0.10:
        return "repeated_adverse"
    return None


def run_case(rows5: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    t0 = event["time"]
    start = t0 - timedelta(minutes=LOOKBACK_MINUTES)
    end = t0 + timedelta(minutes=POST_MINUTES + 5)
    i0 = nearest_completed_close(rows5, t0)
    if i0 is None:
        return None
    candidates = []
    previous_health = "HEALTHY"
    for i in range(max(0, i0 - LOOKBACK_MINUTES // 5), i0 + 1):
        if rows5[i]["timestamp"] + timedelta(minutes=5) < start:
            continue
        f = health_features(rows5, i, event["direction"])
        observed = classify_health(f)
        health = transition_state(previous_health, observed)
        reason = candidate_reason(f)
        if reason and health in ("DETERIORATING", "CRITICAL"):
            candidates.append({"idx": i, "time": rows5[i]["timestamp"] + timedelta(minutes=5), "health": health, "reason": reason, "score": f["score"], "net": f["net"]})
        previous_health = health

    if not candidates:
        return {"event": event, "episodes": []}

    episodes = []
    for c in candidates:
        if not episodes or (c["time"] - episodes[-1]["last_time"]).total_seconds() / 60.0 > EPISODE_GAP_MINUTES:
            episodes.append({"first": c, "last_time": c["time"], "members": [c]})
        else:
            episodes[-1]["last_time"] = c["time"]
            episodes[-1]["members"].append(c)

    result = []
    for ep in episodes:
        first = ep["first"]
        idx = first["idx"]
        score = evaluate_decision(rows5, idx, event["direction"])
        minutes_to_t0 = (t0 - first["time"]).total_seconds() / 60.0
        result.append({"first": first, "decision": score, "minutes_to_t0": minutes_to_t0})
    return {"event": event, "episodes": result}


def fmt(v: Any, spec: str = "+.3f") -> str:
    if v is None:
        return "N/A"
    try:
        return format(v, spec)
    except (TypeError, ValueError):
        return "N/A"


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.12 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.12 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INSUFFICIENT 5M COVERAGE: {skipped}")
    episodes = [e for rec in records for e in rec["result"]["episodes"]]
    print(f"TREND-HEALTH EPISODES: {len(episodes)}")
    print("CAUSAL STATES: HEALTHY -> STRESSED -> DETERIORATING -> CRITICAL")
    print("STATE RULE: one level of deterioration/recovery per completed 5m candle")
    print("SCORING: GOOD_EXIT if HOLD-60 <= -0.10%, FALSE_EXIT if HOLD-60 >= +0.10%")

    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        selected = episodes if direction == "ALL" else [e for rec in records if rec["direction"] == direction for e in rec["result"]["episodes"]]
        print(f"\n{direction} TREND-HEALTH PERSISTENCE")
        print(f"EPISODES: {len(selected)}")
        for health in ("STRESSED", "DETERIORATING", "CRITICAL"):
            xs = [e for e in selected if e["first"]["health"] == health]
            print(f"  FIRST {health}: {len(xs)}")
        vals = [e["decision"]["ret60"] for e in selected if e["decision"]["ret60"] is not None]
        good = [v for v in vals if v <= -EXIT_BUFFER]
        false = [v for v in vals if v >= EXIT_BUFFER]
        neutral = len(vals) - len(good) - len(false)
        print(f"  FIRST-STATE DECISION: VALID={len(vals)} GOOD={len(good)} ({100*len(good)/len(vals):.1f}%) FALSE={len(false)} ({100*len(false)/len(vals):.1f}%) NEUTRAL={neutral} AVG_HOLD60={fmt(avg(vals))}%")
        if vals:
            print(f"  AVG GOOD HOLD60: {fmt(avg(good))}%")
            print(f"  AVG FALSE HOLD60: {fmt(avg(false))}%")

    print("\nV5.6.12 REPRESENTATIVE CASES")
    shown = 0
    for rec in records:
        for e in rec["result"]["episodes"]:
            if shown >= 12:
                return
            f = e["first"]
            d = e["decision"]
            print(f"{rec['symbol']} {rec['direction']} FIRST {f['time']} T0={rec['event']['time']} ({e['minutes_to_t0']:+.0f}m) health={f['health']} reason={f['reason']} score={f['score']:.2f} net={f['net']:+.3f}%")
            print(f"  DECISION -> {d['status']} hold15={fmt(d['ret15'])}% hold30={fmt(d['ret30'])}% hold60={fmt(d['ret60'])}% hold120={fmt(d['ret120'])}%")
            shown += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()
    print("V5.6.12 is research only — no trading rule or engine change.")
    records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    for symbol in args.symbols:
        rows30 = load_rows(symbol, "30m")
        rows5 = load_rows(symbol, "5m")
        events = find_transitions(rows30)
        for event in events:
            total += 1
            result = run_case(rows5, event)
            if result is None:
                skipped += 1
                continue
            records.append({"symbol": symbol, "direction": event["direction"], "event": event, "result": result})
    summarize(records, total, skipped)
    print("\nV5.6.12 KEY TEST")
    print("Trend damage must persist before becoming an EXIT CANDIDATE.")
    print("Recovery is allowed; a single adverse candle cannot create CRITICAL state.")
    print("EXIT remains separate from opposite-direction entry.")
    print("Future candles are used only after each causal decision to score exit-vs-hold.")
    print("V5.6.12 is research only — no trading rule or engine change.")


if __name__ == "__main__":
    main()
