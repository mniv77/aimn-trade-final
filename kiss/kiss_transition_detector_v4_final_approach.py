"""KISS Transition Detector V4 — Final Approach, research only.

Research-only detector. No orders, no DB writes.

Goal:
    V3 CHARACTER_4 reduced false alarms substantially but still fired too early.
    V4 studies the final approach to the official 30m LONG<->SHORT transition.

The detector deliberately separates:
    1) CHARACTER_4: the market has changed character.
    2) FINAL_APPROACH: after character change, the new direction persists and
       the latest 5m structure breaks again.
    3) FINAL_CONFIRM: a later completed 5m bar continues the break after a
       small retest/recovery, attempting to move the decision closer to T5.

Timing model:
    - 30m candle timestamp is candle START; its state is knowable at +30m.
    - 5m candle timestamp is candle START; its observation is knowable at +5m.

This is an experiment only. Do not connect it to KISS execution yet.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
MIN_5M_HISTORY = 20
LOOKBACK_MINUTES = 120
NEGATIVE_HORIZON_MINUTES = 60
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("+00:00", "")).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cur.fetchall() or []
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5],
            }
            d["timestamp"] = ts(d["timestamp"])
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


def market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def opposite(s: str) -> str:
    return "SHORT" if s == "LONG" else "LONG"


def direct_transitions(rows30: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    out: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(rows30)):
        a, b = states[i - 1], states[i]
        if a in ("LONG", "SHORT") and b == opposite(a):
            out.append({
                "index": i,
                "known_time": rows30[i]["timestamp"] + timedelta(minutes=30),
                "from": a,
                "to": b,
                "price": rows30[i]["close"],
            })
    return out


def hist5_until(rows5: Sequence[Dict[str, Any]], obs: datetime) -> List[Dict[str, Any]]:
    return [r for r in rows5 if r["timestamp"] + timedelta(minutes=5) <= obs]


def character_stage(bars: Sequence[Dict[str, Any]], prior: str) -> Tuple[int, Dict[str, bool]]:
    """Strict sequential character detector.

    Stage 1: adverse warning.
    Stage 2: first 3-bar structure break.
    Stage 3: recovery after that break fails.
    Stage 4: a later bar breaks beyond the first break again.

    Every later stage must occur on a later completed 5m bar.
    """
    if len(bars) < MIN_5M_HISTORY:
        return 0, {}

    c = [b["close"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]

    # T0: latest completed close moves against the prior trend.
    warning = c[-1] < c[-2] if prior == "LONG" else c[-1] > c[-2]
    if not warning:
        return 0, {"warning": False}

    # T1: find the most recent earlier structure break.
    break_idx: Optional[int] = None
    for i in range(max(3, len(c) - 15), len(c) - 1):
        if prior == "LONG" and c[i] < min(l[i - 3:i]):
            break_idx = i
        elif prior == "SHORT" and c[i] > max(h[i - 3:i]):
            break_idx = i

    if break_idx is None:
        return 1, {"warning": True, "structure": False}

    # T2: require a genuine recovery bar after the break, before latest bar.
    recovery_idx: Optional[int] = None
    if break_idx + 1 >= len(c) - 1:
        return 2, {"warning": True, "structure": True, "failed_recovery": False}

    if prior == "LONG":
        for j in range(break_idx + 1, len(c) - 1):
            if c[j] > c[j - 1]:
                recovery_idx = j
    else:
        for j in range(break_idx + 1, len(c) - 1):
            if c[j] < c[j - 1]:
                recovery_idx = j

    if recovery_idx is None:
        return 2, {"warning": True, "structure": True, "failed_recovery": False}

    # T3: latest bar fails the recovery.
    if prior == "LONG":
        failed_recovery = c[-1] < c[recovery_idx]
    else:
        failed_recovery = c[-1] > c[recovery_idx]

    if not failed_recovery:
        return 2, {"warning": True, "structure": True, "failed_recovery": False}

    # T4: latest bar must be beyond the first structure-break close.
    if prior == "LONG":
        second_break = c[-1] < c[break_idx]
    else:
        second_break = c[-1] > c[break_idx]

    return (4 if second_break else 3), {
        "warning": True,
        "structure": True,
        "failed_recovery": True,
        "second_break": second_break,
    }


def final_approach_stage(bars: Sequence[Dict[str, Any]], prior: str) -> Tuple[int, Dict[str, bool]]:
    """Return 0..6 for the final approach.

    Stage 4 is the strict V3-style character change.
    Stage 5 requires a NEW later bar to continue beyond the stage-4 extreme.
    Stage 6 requires a later retest/recovery followed by another break.

    The stage is evaluated using only bars completed by the observation time.
    """
    if len(bars) < MIN_5M_HISTORY:
        return 0, {}

    c = [b["close"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]

    # Reconstruct stage-4 time by finding the earliest stage-4 occurrence
    # within the recent history. This keeps the sequence causal.
    stage4_idx: Optional[int] = None
    for k in range(MIN_5M_HISTORY, len(c) + 1):
        s, _ = character_stage(bars[:k], prior)
        if s >= 4:
            stage4_idx = k - 1
            break

    if stage4_idx is None:
        return character_stage(bars, prior)

    flags = {
        "warning": True,
        "structure": True,
        "failed_recovery": True,
        "second_break": True,
        "continuation": False,
        "retest": False,
        "final_break": False,
    }

    # Stage 5: at least one later completed bar extends beyond the stage-4
    # close in the new direction. No same-bar confirmation.
    continuation_idx: Optional[int] = None
    if prior == "LONG":
        for j in range(stage4_idx + 1, len(c)):
            if c[j] < c[stage4_idx] or l[j] < l[stage4_idx]:
                continuation_idx = j
                break
    else:
        for j in range(stage4_idx + 1, len(c)):
            if c[j] > c[stage4_idx] or h[j] > h[stage4_idx]:
                continuation_idx = j
                break

    if continuation_idx is None:
        return 4, flags

    flags["continuation"] = True

    # Stage 6: after continuation, require a small counter-move (retest)
    # followed by a fresh break beyond the continuation extreme.
    retest_idx: Optional[int] = None
    if prior == "LONG":
        for j in range(continuation_idx + 1, len(c)):
            if c[j] > c[j - 1]:
                retest_idx = j
    else:
        for j in range(continuation_idx + 1, len(c)):
            if c[j] < c[j - 1]:
                retest_idx = j

    if retest_idx is None:
        return 5, flags

    flags["retest"] = True

    if prior == "LONG":
        final_break = any(c[j] < c[continuation_idx] or l[j] < l[continuation_idx]
                          for j in range(retest_idx + 1, len(c)))
    else:
        final_break = any(c[j] > c[continuation_idx] or h[j] > h[continuation_idx]
                          for j in range(retest_idx + 1, len(c)))

    flags["final_break"] = final_break
    return (6 if final_break else 5), flags


def sequence_history(rows5: Sequence[Dict[str, Any]], event_time: datetime, prior: str) -> List[Dict[str, Any]]:
    start = event_time - timedelta(minutes=LOOKBACK_MINUTES)
    out: List[Dict[str, Any]] = []
    for bar in rows5:
        obs = bar["timestamp"] + timedelta(minutes=5)
        if start <= obs <= event_time:
            hist = hist5_until(rows5, obs)
            recent = hist[-30:]
            cstage, cflags = character_stage(recent, prior)
            fstage, fflags = final_approach_stage(recent, prior)
            out.append({
                "time": obs,
                "character_stage": cstage,
                "final_stage": fstage,
                "character_flags": cflags,
                "final_flags": fflags,
            })
    return out


def has_opposite(events: Sequence[Dict[str, Any]], anchor: datetime, prior: str) -> bool:
    end = anchor + timedelta(minutes=NEGATIVE_HORIZON_MINUTES)
    target = opposite(prior)
    return any(anchor < e["known_time"] <= end and e["to"] == target for e in events)


def build_cases(rows30, rows5, symbol):
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    events = direct_transitions(rows30)
    out = []

    for e in events:
        seq = sequence_history(rows5, e["known_time"], e["from"])
        if seq:
            out.append({
                "kind": "REAL", "symbol": symbol,
                "event_time": e["known_time"], "from": e["from"],
                "to": e["to"], "sequence": seq,
            })

    for i in range(TREND_WINDOW + 1, len(rows30) - 2):
        prior = states[i - 1]
        if prior not in ("LONG", "SHORT"):
            continue
        anchor = rows30[i]["timestamp"] + timedelta(minutes=30)
        if has_opposite(events, anchor, prior):
            continue
        start = rows30[i]["timestamp"]
        end = start + timedelta(minutes=30)
        seq = []
        for bar in rows5:
            obs = bar["timestamp"] + timedelta(minutes=5)
            if start < obs <= end:
                hist = hist5_until(rows5, obs)
                recent = hist[-30:]
                cstage, cflags = character_stage(recent, prior)
                fstage, fflags = final_approach_stage(recent, prior)
                seq.append({
                    "time": obs,
                    "character_stage": cstage,
                    "final_stage": fstage,
                    "character_flags": cflags,
                    "final_flags": fflags,
                })
        if seq:
            out.append({
                "kind": "NEGATIVE", "symbol": symbol,
                "event_time": anchor, "from": prior,
                "to": opposite(prior), "sequence": seq,
            })
    return out


def split_cases(cases):
    by = defaultdict(list)
    for c in cases:
        by[c["symbol"]].append(c)
    d, h = [], []
    for rows in by.values():
        rows.sort(key=lambda x: x["event_time"])
        cut = int(len(rows) * 0.70)
        d += rows[:cut]
        h += rows[cut:]
    return d, h


def first_fire(c, required):
    for x in c["sequence"]:
        if x["final_stage"] >= required:
            return x
    return None


def evaluate(cases, required, label):
    real = [c for c in cases if c["kind"] == "REAL"]
    neg = [c for c in cases if c["kind"] == "NEGATIVE"]
    rec = []
    late = miss = 0
    for c in real:
        f = first_fire(c, required)
        if f is None:
            miss += 1
        elif f["time"] <= c["event_time"]:
            rec.append((c, f))
        else:
            late += 1
    false = sum(first_fire(c, required) is not None for c in neg)
    leads = [(c["event_time"] - f["time"]).total_seconds() / 60 for c, f in rec]
    before = 100 * len(rec) / len(real) if real else 0
    latep = 100 * late / len(real) if real else 0
    missp = 100 * miss / len(real) if real else 0
    fp = 100 * false / len(neg) if neg else 0
    detected = len(rec) + late
    precision = 100 * detected / (detected + false) if detected + false else 0
    w5 = 100 * sum(x <= 5 for x in leads) / len(leads) if leads else 0
    w15 = 100 * sum(x <= 15 for x in leads) / len(leads) if leads else 0
    w30 = 100 * sum(x <= 30 for x in leads) / len(leads) if leads else 0
    w45 = 100 * sum(x <= 45 for x in leads) / len(leads) if leads else 0
    w60 = 100 * sum(x <= 60 for x in leads) / len(leads) if leads else 0
    print(f"{label} stage={required} REAL={len(real)} NEG={len(neg)}")
    print(f"  recognized_before={before:.1f}% late={latep:.1f}% missed={missp:.1f}%")
    print(f"  false_alarm={fp:.1f}% precision={precision:.1f}%")
    if leads:
        print(f"  lead_mean={mean(leads):.1f}m lead_median={median(leads):.1f}m")
    else:
        print("  lead_mean=n/a lead_median=n/a")
    print(f"  within5={w5:.1f}% within15={w15:.1f}% within30={w30:.1f}% within45={w45:.1f}% within60={w60:.1f}%")


def stage_reach(cases, label):
    real = [c for c in cases if c["kind"] == "REAL"]
    print(f"{label} REAL final-approach reach")
    for s in range(4, 7):
        n = sum(any(x["final_stage"] >= s for x in c["sequence"]) for c in real)
        print(f"  stage{s}={n}/{len(real)} ({100*n/len(real) if real else 0:.1f}%)")


def run(symbols):
    all_cases = []
    for symbol in symbols:
        rows30 = load(symbol, "30m", 6000)
        rows5 = load(symbol, "5m", 20000)
        cases = build_cases(rows30, rows5, symbol)
        all_cases += cases
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} cases={len(cases)} real={sum(c['kind']=='REAL' for c in cases)} neg={sum(c['kind']=='NEGATIVE' for c in cases)}")

    d, h = split_cases(all_cases)
    print(f"TOTAL cases={len(all_cases)} discovery={len(d)} holdout={len(h)}")

    for label, cases in (("FULL", all_cases), ("DISCOVERY 70%", d), ("HOLDOUT 30%", h)):
        print(label)
        stage_reach(cases, label)
        evaluate(cases, 4, "FINAL_APPROACH")
        evaluate(cases, 5, "FINAL_CONTINUATION")
        evaluate(cases, 6, "FINAL_CONFIRM")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    run(p.parse_args().symbols)
