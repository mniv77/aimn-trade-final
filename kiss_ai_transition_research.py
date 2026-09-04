"""
AI Vision Transition Research Harness

Research-only. Does NOT modify the KISS engine, place trades, or write to DB.

Purpose:
    Build a clean dataset of 30m trend transitions across the symbols that
    currently have usable candle data, expose only information available at
    the transition, and produce an AI Vision prompt for REAL / WEAK / FALSE
    classification. The future outcome is kept separate so the AI prediction
    can later be scored against reality.

This first version is intentionally provider-neutral. It creates JSONL-style
research cases on stdout and a compact summary. It does not call an external
AI API, because we want the feature set and labels frozen before connecting
AI Vision to live inference.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_left
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection
from engine.kiss_execution_5m import (
    TREND_BAND,
    TREND_WINDOW,
    _v_shape,
    get_market_state,
    rsi_wilder,
)

SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "META", "AMD", "SPY", "QQQ"]
TIMEFRAME = "30m"
EXECUTION_TIMEFRAME = "5m"
LIMIT = 5000
FUTURE_BARS = 48  # 4 hours of 5m data for research labeling
REAL_MFE = 0.010
REAL_RATIO = 1.50
FALSE_MAE = 0.010
FALSE_MFE = 0.005


def _db_rows(symbol: str, timeframe: str, limit: int = LIMIT) -> List[Dict[str, Any]]:
    conn, cursor = get_db_connection()
    try:
        cursor.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC
               LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        cursor.close()
        conn.close()


def _dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _pct(a: float, b: float) -> float:
    return (a / b) - 1.0 if b else 0.0


def _safe_float(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def build_states(rows: Sequence[Dict[str, Any]]) -> List[str]:
    closes = [float(r["close"]) for r in rows]
    return [get_market_state(closes, i) for i in range(len(rows))]


def transition_events(rows: Sequence[Dict[str, Any]], states: Sequence[str]) -> List[Dict[str, Any]]:
    closes = [float(r["close"]) for r in rows]
    rsi = rsi_wilder(closes)
    events: List[Dict[str, Any]] = []
    for i in range(1, len(rows)):
        prev, cur = states[i - 1], states[i]
        if prev == cur or cur == "FLAT":
            continue
        if prev not in ("LONG", "SHORT", "FLAT"):
            continue

        ma_start = max(0, i - TREND_WINDOW)
        ma_window = closes[ma_start:i]
        ma20 = sum(ma_window) / len(ma_window) if ma_window else closes[i]
        ma_prev_start = max(0, i - TREND_WINDOW - 1)
        ma_prev_window = closes[ma_prev_start:i - 1]
        ma20_prev = sum(ma_prev_window) / len(ma_prev_window) if ma_prev_window else ma20
        ma_slope = "UP" if ma20 > ma20_prev else "DOWN" if ma20 < ma20_prev else "FLAT"

        prev_duration = 1
        j = i - 2
        while j >= 0 and states[j] == prev:
            prev_duration += 1
            j -= 1

        churn = 0
        for j in range(max(1, i - 6), i):
            if states[j] != states[j - 1]:
                churn += 1

        def move(n: int) -> Optional[float]:
            if i - n < 0:
                return None
            return _pct(closes[i], closes[i - n])

        recent = closes[max(0, i - 12):i]
        recent_high = max(recent) if recent else closes[i]
        recent_low = min(recent) if recent else closes[i]

        events.append({
            "index": i,
            "time": _dt(rows[i]["timestamp"]),
            "from": prev,
            "to": cur,
            "price": closes[i],
            "ma20": ma20,
            "distance_pct": _pct(closes[i], ma20),
            "ma_slope": ma_slope,
            "rsi": _safe_float(rsi[i]) if i < len(rsi) else None,
            "shape": _v_shape(closes, i),
            "previous_state_duration_bars": prev_duration,
            "state_churn_6bars": churn,
            "move_1bar_pct": move(1),
            "move_2bar_pct": move(2),
            "move_3bar_pct": move(3),
            "move_4bar_pct": move(4),
            "move_6bar_pct": move(6),
            "move_12bar_pct": move(12),
            "recent_12bar_high_distance_pct": _pct(recent_high, closes[i]),
            "recent_12bar_low_distance_pct": _pct(closes[i], recent_low),
        })
    return events


def future_label(entry_price: float, future_rows: Sequence[Dict[str, Any]], direction: str) -> Tuple[str, float, float]:
    favorable: List[float] = []
    adverse_signed: List[float] = []
    for row in future_rows:
        hi = float(row["high"])
        lo = float(row["low"])
        if direction == "LONG":
            favorable.append(_pct(hi, entry_price))
            adverse_signed.append(_pct(lo, entry_price))
        else:
            favorable.append(_pct(entry_price, lo))
            adverse_signed.append(_pct(entry_price, hi))

    if not favorable:
        return "UNLABELED", 0.0, 0.0

    mfe = max(0.0, max(favorable))
    mae = max(0.0, -min(adverse_signed))
    if mfe >= REAL_MFE and mfe >= max(mae, 0.0001) * REAL_RATIO:
        return "REAL", mfe, mae
    if mae >= FALSE_MAE and mfe < FALSE_MFE:
        return "FALSE", mfe, mae
    return "WEAK", mfe, mae


def make_case(symbol: str, event: Dict[str, Any], exec_rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    exec_times = [_dt(r["timestamp"]) for r in exec_rows]
    ex_i = bisect_left(exec_times, event["time"])
    future = exec_rows[ex_i:ex_i + FUTURE_BARS]
    if len(future) < FUTURE_BARS:
        return None

    label, mfe, mae = future_label(event["price"], future, event["to"])
    features = {k: v for k, v in event.items() if k not in ("index", "time")}
    return {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "execution_timeframe": EXECUTION_TIMEFRAME,
        "transition_time": event["time"].isoformat(),
        "direction": event["to"],
        "features_available_at_transition": features,
        "future_outcome": {
            "label": label,
            "mfe_pct": round(mfe * 100.0, 4),
            "mae_pct": round(mae * 100.0, 4),
            "horizon_5m_bars": FUTURE_BARS,
        },
        "ai_prediction": None,
        "ai_confidence": None,
        "ai_reason": None,
    }


def ai_prompt(case: Dict[str, Any]) -> str:
    return (
        "You are AI Vision evaluating a market trend transition. "
        "Use ONLY the supplied information; do not use future outcome fields. "
        "Classify the transition as REAL, WEAK, or FALSE. Return JSON with "
        "prediction, confidence_0_to_100, and a short reason. "
        "REAL means a transition likely to produce a meaningful move in the "
        "new direction; WEAK means uncertain or limited; FALSE means likely "
        "to fail/reverse. Do not use generic trading advice.\n\n"
        + json.dumps(case["features_available_at_transition"], sort_keys=True)
    )


def main() -> None:
    all_cases: List[Dict[str, Any]] = []
    print("AI VISION TRANSITION RESEARCH")
    print("Research only: no engine changes, no trades, no DB writes")
    print(f"Future label horizon: {FUTURE_BARS} x 5m = 4 hours")
    print("=" * 80)

    for symbol in SYMBOLS:
        trend = _db_rows(symbol, TIMEFRAME)
        execution = _db_rows(symbol, EXECUTION_TIMEFRAME)
        if len(trend) < TREND_WINDOW + 2 or len(execution) < FUTURE_BARS:
            print(f"{symbol}: SKIP (30m={len(trend)}, 5m={len(execution)})")
            continue
        states = build_states(trend)
        events = transition_events(trend, states)
        cases = []
        for event in events:
            case = make_case(symbol, event, execution)
            if case:
                cases.append(case)
        all_cases.extend(cases)
        counts = Counter(c["future_outcome"]["label"] for c in cases)
        print(f"{symbol}: cases={len(cases)} REAL={counts['REAL']} WEAK={counts['WEAK']} FALSE={counts['FALSE']}")

    counts = Counter(c["future_outcome"]["label"] for c in all_cases)
    print("=" * 80)
    print(f"TOTAL CASES: {len(all_cases)}")
    print(f"REAL={counts['REAL']} WEAK={counts['WEAK']} FALSE={counts['FALSE']}")
    print()
    print("AI INPUT CONTRACT:")
    print("  AI sees only features_available_at_transition.")
    print("  future_outcome is hidden during prediction and revealed only for scoring.")
    print("  ai_prediction / confidence / reason are reserved for the AI result.")
    print()

    # Show a few cases so the exact AI input contract can be inspected before
    # connecting an external model.
    for n, case in enumerate(all_cases[:5], 1):
        print(f"--- CASE {n}: {case['symbol']} {case['direction']} {case['transition_time']} ---")
        print(ai_prompt(case))
        print("ACTUAL (for scoring only):", json.dumps(case["future_outcome"], sort_keys=True))


if __name__ == "__main__":
    main()
