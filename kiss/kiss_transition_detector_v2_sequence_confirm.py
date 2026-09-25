"""KISS Transition Detector V2.1 — true later-bar confirmation, research only.

This is a research experiment. It does NOT change KISS execution, place orders,
or write to MySQL.

Purpose
-------
V2 Sequence showed that ordered evidence can recognize many real transitions,
but SEQUENCE_3 and SEQUENCE_4 produced identical results because the original
confirmation was evaluated on the same 5m bar as the structure break.

V2.1 fixes that experiment. Confirmation is now required on a STRICTLY LATER
completed 5m bar after the structure stage.

Sequence:
    WARNING -> PERSISTENCE -> STRUCTURE -> LATER BAR -> CONFIRMATION

SEQUENCE_3 fires when persistence + structure are first reached.
SEQUENCE_4 fires only when a later completed 5m bar closes against the prior
trend after SEQUENCE_3 has already been reached.

A sequence resets when its warning loses persistence before structure is reached.
This keeps the test causal: every stage uses only information available at that
5m candle close.

Timing model
------------
30m candle timestamps are candle START times. A 30m state is knowable at
start + 30m. 5m observations are knowable at start + 5m.
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


def adverse(prior_state: str, previous_close: float, current_close: float) -> bool:
    if prior_state == "LONG":
        return current_close < previous_close
    return current_close > previous_close


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


def scan_sequence(
    bars: Sequence[Dict[str, Any]], prior_state: str
) -> Dict[str, Any]:
    """Scan completed 5m bars causally and return the first sequence stages.

    A warning starts a sequence. Persistence requires >=2 adverse closes in the
    latest three moves while the sequence is active. Structure is a close beyond
    the previous three completed bars' high/low. Confirmation MUST occur on a
    later bar than structure and must itself close against the prior trend.
    """
    result: Dict[str, Any] = {
        "stage1_time": None,
        "stage2_time": None,
        "stage3_time": None,
        "stage4_time": None,
        "max_stage": 0,
    }
    if len(bars) < MIN_5M_HISTORY:
        return result

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    warning_idx: Optional[int] = None
    stage3_idx: Optional[int] = None

    for i in range(1, len(bars)):
        is_adverse = adverse(prior_state, closes[i - 1], closes[i])

        if stage3_idx is not None:
            # Stage 4 is deliberately a NEW bar after structure.
            if i > stage3_idx and is_adverse:
                result["stage4_time"] = bars[i]["timestamp"] + timedelta(minutes=5)
                result["max_stage"] = 4
                break
            continue

        if not is_adverse:
            # A non-adverse close before structure resets the sequence.
            warning_idx = None
            result["stage1_time"] = None
            result["stage2_time"] = None
            continue

        if warning_idx is None:
            warning_idx = i
            result["stage1_time"] = bars[i]["timestamp"] + timedelta(minutes=5)
            result["max_stage"] = max(result["max_stage"], 1)

        if i >= 2:
            moves = [adverse(prior_state, closes[j - 1], closes[j]) for j in range(i - 2, i + 1)]
            persistence = sum(moves) >= 2
        else:
            persistence = False

        # Keep persistence tied to the current warning. A sequence cannot
        # quietly survive an old warning after several new bars.
        active_window = warning_idx is not None and i - warning_idx <= 2
        if not persistence or not active_window:
            result["stage1_time"] = bars[i]["timestamp"] + timedelta(minutes=5)
            result["stage2_time"] = None
            result["max_stage"] = max(result["max_stage"], 1)
            continue

        if result["stage2_time"] is None:
            result["stage2_time"] = bars[i]["timestamp"] + timedelta(minutes=5)
            result["max_stage"] = max(result["max_stage"], 2)

        if i < 3:
            continue

        if prior_state == "LONG":
            structure = closes[i] < min(lows[i - 3:i])
        else:
            structure = closes[i] > max(highs[i - 3:i])

        if structure:
            stage3_idx = i
            result["stage3_time"] = bars[i]["timestamp"] + timedelta(minutes=5)
            result["max_stage"] = 3

    return result


def sequence_at_observations(
    rows5: Sequence[Dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
    prior_state: str,
) -> List[Dict[str, Any]]:
    observations = [
        r for r in rows5
        if start_time <= r["timestamp"] + timedelta(minutes=5) <= end_time
    ]
    out: List[Dict[str, Any]] = []
    for r in observations:
        obs_time = r["timestamp"] + timedelta(minutes=5)
        hist = hist5_until(rows5, obs_time)
        scan = scan_sequence(hist[-20:], prior_state)
        out.append({"time": obs_time, **scan})
    return out


def has_opposite_within(
    events: Sequence[Dict[str, Any]], anchor: datetime, prior: str
) -> bool:
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

    # REAL: inspect only observations that were actually knowable before the
    # official 30m transition close.
    for e in events:
        start = e["known_time"] - timedelta(minutes=LOOKBACK_MINUTES)
        seq = sequence_at_observations(rows5, start, e["known_time"], e["from"])
        if seq:
            out.append({
                "kind": "REAL",
                "symbol": symbol,
                "event_time": e["known_time"],
                "from": e["from"],
                "to": e["to"],
                "sequence": seq,
            })

    # NEGATIVE: no direct opposite transition in the following 60 minutes.
    # We examine the first 30 minutes after the anchor, because a signal there
    # would be an attempted early exit on an event that did not transition.
    for i in range(TREND_WINDOW + 1, len(rows30) - 2):
        prior = states[i - 1]
        if prior not in ("LONG", "SHORT"):
            continue
        anchor = rows30[i]["timestamp"] + timedelta(minutes=30)
        if has_opposite_within(events, anchor, prior):
            continue
        start = anchor
        end = anchor + timedelta(minutes=30)
        seq = sequence_at_observations(rows5, start, end, prior)
        if seq:
            out.append({
                "kind": "NEGATIVE",
                "symbol": symbol,
                "event_time": anchor,
                "from": prior,
                "to": opposite(prior),
                "sequence": seq,
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


def first_stage_time(c: Dict[str, Any], stage: int) -> Optional[datetime]:
    return c["sequence"][-1].get(f"stage{stage}_time") if c["sequence"] else None


def earliest_stage_time(c: Dict[str, Any], stage: int) -> Optional[datetime]:
    key = f"stage{stage}_time"
    for obs in c["sequence"]:
        t = obs.get(key)
        if t is not None:
            return t
    return None


def evaluate(cases: Sequence[Dict[str, Any]], stage: int, label: str) -> None:
    real = [c for c in cases if c["kind"] == "REAL"]
    neg = [c for c in cases if c["kind"] == "NEGATIVE"]

    recognized: List[Tuple[Dict[str, Any], datetime]] = []
    late = 0
    missed = 0
    false = 0

    for c in real:
        fire = earliest_stage_time(c, stage)
        if fire is None:
            missed += 1
        elif fire <= c["event_time"]:
            recognized.append((c, fire))
        else:
            late += 1

    for c in neg:
        if earliest_stage_time(c, stage) is not None:
            false += 1

    leads = [(c["event_time"] - t).total_seconds() / 60.0 for c, t in recognized]
    detected = len(recognized) + late
    before_pct = 100.0 * len(recognized) / len(real) if real else 0.0
    late_pct = 100.0 * late / len(real) if real else 0.0
    missed_pct = 100.0 * missed / len(real) if real else 0.0
    false_pct = 100.0 * false / len(neg) if neg else 0.0
    precision = 100.0 * detected / (detected + false) if detected + false else 0.0
    within5 = 100.0 * sum(x <= 5.0 for x in leads) / len(leads) if leads else 0.0
    within15 = 100.0 * sum(x <= 15.0 for x in leads) / len(leads) if leads else 0.0

    print(label)
    print(f"  stage={stage} REAL={len(real)} NEG={len(neg)}")
    print(f"  recognized_before={before_pct:.1f}% late={late_pct:.1f}% missed={missed_pct:.1f}%")
    print(f"  false_alarm={false_pct:.1f}% precision={precision:.1f}%")
    if leads:
        print(
            f"  lead_mean={mean(leads):.1f}m lead_median={median(leads):.1f}m "
            f"within5={within5:.1f}% within15={within15:.1f}%"
        )
    else:
        print("  lead_mean=n/a lead_median=n/a within5=0.0% within15=0.0%")


def stage_progress(cases: Sequence[Dict[str, Any]], label: str) -> None:
    real = [c for c in cases if c["kind"] == "REAL"]
    print(f"{label} REAL sequence reach")
    for stage in range(1, 5):
        n = sum(earliest_stage_time(c, stage) is not None for c in real)
        pct = 100.0 * n / len(real) if real else 0.0
        print(f"  stage{stage}={n}/{len(real)} ({pct:.1f}%)")


def run(symbols: Sequence[str]) -> None:
    all_cases: List[Dict[str, Any]] = []
    for symbol in symbols:
        rows30 = load(symbol, "30m", 6000)
        rows5 = load(symbol, "5m", 12000)
        cases = build_cases(rows30, rows5, symbol)
        all_cases.extend(cases)
        real = sum(c["kind"] == "REAL" for c in cases)
        neg = sum(c["kind"] == "NEGATIVE" for c in cases)
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} cases={len(cases)} real={real} neg={neg}")

    discovery, holdout = split_cases(all_cases)
    print(f"TOTAL cases={len(all_cases)} discovery={len(discovery)} holdout={len(holdout)}")

    for label, cases in (("FULL", all_cases), ("DISCOVERY 70%", discovery), ("HOLDOUT 30%", holdout)):
        print(label)
        stage_progress(cases, label)
        evaluate(cases, 3, "SEQUENCE_3")
        evaluate(cases, 4, "SEQUENCE_4")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    args = parser.parse_args()
    run(args.symbols)
