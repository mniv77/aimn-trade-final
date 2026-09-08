"""KISS Transition Detector V2 — sequence-based, research only.

Goal
----
Test whether a real LONG <-> SHORT transition can be recognized earlier and
more cleanly when evidence is treated as a SEQUENCE instead of an additive
score:

    WARNING -> PERSISTENCE -> STRUCTURE BREAK -> CONFIRMATION -> ACTION

This is deliberately research-only. It does not change KISS execution, place
orders, or write to MySQL.

Timing model
------------
The candle timestamps are candle START times. A 30m state is knowable only at
that candle's close (start + 30m). A 5m observation is knowable at its close
(start + 5m). The official direct transition is therefore the close time of
the 30m candle that changes LONG -> SHORT or SHORT -> LONG.

Important design choice
-----------------------
V2 does NOT add more indicator weights. RSI is context only. The detector
looks for a character change in the 5m path and requires ordered evidence.
A later stage cannot be counted before its prerequisite stage.

Stages
------
WARNING      : first completed 5m close moving against the prior trend.
PERSISTENCE  : at least 2 of the latest 3 completed 5m closes move against it.
STRUCTURE    : current close breaks the previous 3-bar high/low structure.
CONFIRMATION : after persistence/structure, another opposite close occurs and
               the sequence has not reset.

Two action variants are measured:
    SEQUENCE_3 = WARNING + PERSISTENCE + STRUCTURE
    SEQUENCE_4 = WARNING + PERSISTENCE + STRUCTURE + CONFIRMATION

The point is not to declare either a rule. We want to see the tradeoff between
speed and false alarms before touching the engine.
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
RSI_PERIOD = 14
MIN_5M_HISTORY = 20
LOOKBACK_MINUTES = 60
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
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cur.fetchall() or []
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5]
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
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def opposite(state: str) -> str:
    return "SHORT" if state == "LONG" else "LONG"


def rsi_series(closes: Sequence[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        gain, loss = max(d, 0.0), max(-d, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def direct_transitions(rows30: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    out: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(rows30)):
        a, b = states[i - 1], states[i]
        if a in ("LONG", "SHORT") and b == opposite(a):
            out.append({
                "index": i,
                "bar_time": rows30[i]["timestamp"],
                "known_time": rows30[i]["timestamp"] + timedelta(minutes=30),
                "from": a,
                "to": b,
                "price": rows30[i]["close"],
            })
    return out


def hist5_until(rows5: Sequence[Dict[str, Any]], obs_time: datetime) -> List[Dict[str, Any]]:
    return [r for r in rows5 if r["timestamp"] + timedelta(minutes=5) <= obs_time]


def sequence_stage(
    bars: Sequence[Dict[str, Any]], prior_state: str
) -> Tuple[int, Dict[str, bool], List[str]]:
    """Return the highest ordered stage currently reached.

    0 = none, 1 = warning, 2 = persistence, 3 = structure, 4 = confirmation.
    No stage is allowed to skip its predecessor.
    """
    if len(bars) < MIN_5M_HISTORY:
        return 0, {}, []
    closes = [x["close"] for x in bars]
    highs = [x["high"] for x in bars]
    lows = [x["low"] for x in bars]

    def adverse_move(a: float, b: float) -> bool:
        return b < a if prior_state == "LONG" else b > a

    warning = adverse_move(closes[-2], closes[-1])
    if not warning:
        return 0, {"warning": False}, []

    recent_moves = [adverse_move(closes[i - 1], closes[i]) for i in range(len(closes) - 3, len(closes))]
    persistence = sum(recent_moves) >= 2

    if prior_state == "LONG":
        structure = closes[-1] < min(lows[-4:-1])
    else:
        structure = closes[-1] > max(highs[-4:-1])

    # Confirmation must occur AFTER persistence and structure are both true.
    confirmation = False
    if persistence and structure and len(closes) >= 2:
        confirmation = adverse_move(closes[-2], closes[-1])

    flags = {
        "warning": warning,
        "persistence": persistence,
        "structure": structure,
        "confirmation": confirmation,
    }
    reasons = [k for k, v in flags.items() if v]
    stage = 4 if confirmation else 3 if persistence and structure else 2 if persistence else 1
    return stage, flags, reasons


def sequence_history(
    rows5: Sequence[Dict[str, Any]],
    event_time: datetime,
    prior_state: str,
) -> List[Dict[str, Any]]:
    start = event_time - timedelta(minutes=LOOKBACK_MINUTES)
    candidates = [
        r for r in rows5
        if start <= r["timestamp"] + timedelta(minutes=5) <= event_time
    ]
    out: List[Dict[str, Any]] = []
    for bar in candidates:
        obs_time = bar["timestamp"] + timedelta(minutes=5)
        hist = hist5_until(rows5, obs_time)
        stage, flags, reasons = sequence_stage(hist[-20:], prior_state)
        out.append({"time": obs_time, "stage": stage, "flags": flags, "reasons": reasons})
    return out


def has_opposite_within(events: Sequence[Dict[str, Any]], anchor: datetime, prior: str) -> bool:
    target = opposite(prior)
    end = anchor + timedelta(minutes=NEGATIVE_HORIZON_MINUTES)
    return any(anchor < e["known_time"] <= end and e["to"] == target for e in events)


def build_cases(
    rows30: Sequence[Dict[str, Any]], rows5: Sequence[Dict[str, Any]], symbol: str
) -> List[Dict[str, Any]]:
    closes30 = [r["close"] for r in rows30]
    states = [market_state(closes30, i) for i in range(len(rows30))]
    events = direct_transitions(rows30)
    out: List[Dict[str, Any]] = []

    for e in events:
        seq = sequence_history(rows5, e["known_time"], e["from"])
        if seq:
            out.append({
                "kind": "REAL", "symbol": symbol, "event_time": e["known_time"],
                "from": e["from"], "to": e["to"], "sequence": seq,
            })

    for i in range(TREND_WINDOW + 1, len(rows30) - 2):
        prior = states[i - 1]
        if prior not in ("LONG", "SHORT"):
            continue
        anchor = rows30[i]["timestamp"] + timedelta(minutes=30)
        if has_opposite_within(events, anchor, prior):
            continue
        start = rows30[i]["timestamp"]
        end = start + timedelta(minutes=30)
        bars = [r for r in rows5 if start <= r["timestamp"] + timedelta(minutes=5) <= end]
        if not bars:
            continue
        seq: List[Dict[str, Any]] = []
        for bar in bars:
            obs = bar["timestamp"] + timedelta(minutes=5)
            hist = hist5_until(rows5, obs)
            stage, flags, reasons = sequence_stage(hist[-20:], prior)
            seq.append({"time": obs, "stage": stage, "flags": flags, "reasons": reasons})
        out.append({
            "kind": "NEGATIVE", "symbol": symbol, "event_time": anchor,
            "from": prior, "to": opposite(prior), "sequence": seq,
        })
    return out


def split_cases(cases: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in cases:
        by[c["symbol"]].append(c)
    discovery: List[Dict[str, Any]] = []
    holdout: List[Dict[str, Any]] = []
    for symbol, rows in by.items():
        rows.sort(key=lambda x: x["event_time"])
        cut = int(len(rows) * 0.70)
        discovery.extend(rows[:cut])
        holdout.extend(rows[cut:])
    return discovery, holdout


def first_fire(c: Dict[str, Any], required_stage: int) -> Optional[Dict[str, Any]]:
    for x in c["sequence"]:
        if x["stage"] >= required_stage:
            return x
    return None


def evaluate(cases: Sequence[Dict[str, Any]], required_stage: int, label: str) -> None:
    real = [c for c in cases if c["kind"] == "REAL"]
    neg = [c for c in cases if c["kind"] == "NEGATIVE"]
    recognized: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    late: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    false = 0

    for c in real:
        fire = first_fire(c, required_stage)
        if fire is None:
            continue
        if fire["time"] <= c["event_time"]:
            recognized.append((c, fire))
        else:
            late.append((c, fire))

    for c in neg:
        if first_fire(c, required_stage) is not None:
            false += 1

    leads = [(c["event_time"] - f["time"]).total_seconds() / 60.0 for c, f in recognized]
    detected = len(recognized) + len(late)
    total = len(real)
    false_rate = 100.0 * false / len(neg) if neg else 0.0
    precision = 100.0 * detected / (detected + false) if detected + false else 0.0
    before_pct = 100.0 * len(recognized) / total if total else 0.0
    late_pct = 100.0 * len(late) / total if total else 0.0
    within5 = 100.0 * sum(1 for x in leads if x <= 5.0) / len(leads) if leads else 0.0
    within15 = 100.0 * sum(1 for x in leads if x <= 15.0) / len(leads) if leads else 0.0

    print(f"{label} stage={required_stage}")
    print(f"  REAL={total} NEG={len(neg)} recognized_before={before_pct:.1f}% late={late_pct:.1f}%")
    print(f"  false_alarm={false_rate:.1f}% precision={precision:.1f}%")
    if leads:
        print(f"  lead_mean={mean(leads):.1f}m lead_median={median(leads):.1f}m within5={within5:.1f}% within15={within15:.1f}%")
    else:
        print("  lead_mean=n/a lead_median=n/a within5=0.0% within15=0.0%")


def stage_progress(cases: Sequence[Dict[str, Any]], label: str) -> None:
    real = [c for c in cases if c["kind"] == "REAL"]
    counts = {stage: 0 for stage in range(1, 5)}
    for c in real:
        max_stage = max((x["stage"] for x in c["sequence"]), default=0)
        for stage in counts:
            if max_stage >= stage:
                counts[stage] += 1
    print(f"{label} REAL sequence reach")
    for stage, n in counts.items():
        print(f"  stage{stage}={n}/{len(real)} ({100.0*n/len(real) if real else 0.0:.1f}%)")


def run(symbols: Sequence[str]) -> None:
    all_cases: List[Dict[str, Any]] = []
    for symbol in symbols:
        rows30 = load(symbol, "30m", 6000)
        rows5 = load(symbol, "5m", 30000)
        cases = build_cases(rows30, rows5, symbol)
        all_cases.extend(cases)
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} cases={len(cases)} real={sum(c['kind']=='REAL' for c in cases)} neg={sum(c['kind']=='NEGATIVE' for c in cases)}")

    discovery, holdout = split_cases(all_cases)
    print(f"TOTAL cases={len(all_cases)} discovery={len(discovery)} holdout={len(holdout)}")
    print("\nFULL")
    stage_progress(all_cases, "FULL")
    evaluate(all_cases, 3, "SEQUENCE_3")
    evaluate(all_cases, 4, "SEQUENCE_4")
    print("\nDISCOVERY 70%")
    stage_progress(discovery, "DISCOVERY")
    evaluate(discovery, 3, "SEQUENCE_3")
    evaluate(discovery, 4, "SEQUENCE_4")
    print("\nHOLDOUT 30%")
    stage_progress(holdout, "HOLDOUT")
    evaluate(holdout, 3, "SEQUENCE_3")
    evaluate(holdout, 4, "SEQUENCE_4")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Research-only KISS Transition Detector V2 sequence test")
    parser.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    args = parser.parse_args()
    run(args.symbols)
