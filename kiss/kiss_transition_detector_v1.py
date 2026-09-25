"""Research-only KISS real-time transition detector v1.

GOAL
====
Find the earliest 5m point at which the evidence says an existing 30m trend
has ACTUALLY reversed, while keeping false exits manageable.

This file does NOT change KISS execution, place orders, or write to the DB.
It deliberately separates:
    - OBSERVATION: features available at the current completed 5m bar
    - LABEL: the future 30m state change, used only for evaluation

The detector is intentionally simple and testable.  It combines independent
5m reversal evidence rather than requiring one indicator to predict a turn:
    1. consecutive 5m closes against the open-trade direction
    2. break of recent 5m structure
    3. persistence of the reversal over a short window
    4. adverse displacement from the recent 5m extreme
    5. RSI as context only (never a standalone entry/exit signal)
    6. 30m distance from its MA as structural context

The script sweeps score thresholds and reports the speed/false-exit frontier.
No threshold is declared a trading rule by this experiment.

IMPORTANT METHODOLOGY
=====================
The old post-gap diagnostic compared evidence with a 30m transition using
session-open evidence.  This detector works on EVERY completed 5m bar around
an actual 30m transition, so it is not dependent on a session gap.

The current 30m state is calculated exactly like KISS: the MA uses the 20
completed 30m closes BEFORE the state bar.  A future opposite state is used
only as the evaluation label; it is never an input feature.

Run examples:
    python kiss_transition_detector_v1.py
    python kiss_transition_detector_v1.py NVDA AAPL MSFT AMZN TSLA SPY QQQ
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
FIVE_MIN_WINDOW = 3
PERSIST_WINDOW = 3
LOOKAHEAD_MINUTES = 60
CANDIDATE_BEFORE_MINUTES = 120
MIN_5M_HISTORY = 20
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]
SCORE_THRESHOLDS = (2, 3, 4)


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


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
            if isinstance(r, dict):
                d = dict(r)
            else:
                d = {"timestamp": r[0], "open": r[1], "high": r[2],
                     "low": r[3], "close": r[4], "volume": r[5]}
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
    """KISS 30m state at idx; MA uses only closes before idx."""
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


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
        gain = max(d, 0.0)
        loss = max(-d, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def nearest_5m(rows: Sequence[Dict[str, Any]], start: datetime, end: datetime) -> List[Dict[str, Any]]:
    return [r for r in rows if start <= r["timestamp"] <= end]


def opposite(state: str) -> str:
    return "SHORT" if state == "LONG" else "LONG"


def future_opposite_time(
    rows30: Sequence[Dict[str, Any]],
    closes30: Sequence[float],
    start_idx: int,
    prior_state: str,
    horizon_minutes: int,
) -> Optional[datetime]:
    target = opposite(prior_state)
    start_time = rows30[start_idx]["timestamp"]
    end_time = start_time + timedelta(minutes=horizon_minutes)
    for j in range(start_idx, len(rows30)):
        if rows30[j]["timestamp"] > end_time:
            break
        if market_state(closes30, j) == target:
            return rows30[j]["timestamp"]
    return None


def structural_context(rows30: Sequence[Dict[str, Any]], closes30: Sequence[float], idx: int) -> float:
    if idx < TREND_WINDOW:
        return 0.0
    ma = sum(closes30[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if ma == 0:
        return 0.0
    return (closes30[idx] / ma - 1.0) * 100.0


def feature_score(
    bars: Sequence[Dict[str, Any]],
    prior_state: str,
    rsi: Optional[float],
    ma_distance_pct: float,
) -> Tuple[int, List[str]]:
    """Score only information available through the final completed 5m bar."""
    if len(bars) < MIN_5M_HISTORY:
        return 0, []

    closes = [float(x["close"]) for x in bars]
    highs = [float(x["high"]) for x in bars]
    lows = [float(x["low"]) for x in bars]
    score = 0
    reasons: List[str] = []

    against = (lambda a, b: a < b) if prior_state == "LONG" else (lambda a, b: a > b)

    # 1) Recent consecutive closes against the open-trade direction.
    streak = 0
    for a, b in zip(reversed(closes), reversed(closes[:-1])):
        if against(a, b):
            streak += 1
        else:
            break
    if streak >= 2:
        score += 1
        reasons.append(f"opposite_streak={streak}")

    # 2) Break of the previous 3-bar structure.
    prior_high = max(highs[-4:-1])
    prior_low = min(lows[-4:-1])
    if prior_state == "LONG" and closes[-1] < prior_low:
        score += 1
        reasons.append("break_recent_low")
    elif prior_state == "SHORT" and closes[-1] > prior_high:
        score += 1
        reasons.append("break_recent_high")

    # 3) Persistence: at least 2 of the last 3 closes move against direction.
    moves = [closes[i] - closes[i - 1] for i in range(len(closes) - 3, len(closes))]
    opposite_moves = sum(1 for x in moves if (x < 0 if prior_state == "LONG" else x > 0))
    if opposite_moves >= 2:
        score += 1
        reasons.append(f"2of3_opposite={opposite_moves}")

    # 4) Displacement from the recent extreme (context, not a magic threshold).
    if prior_state == "LONG":
        ref = max(highs[-PERSIST_WINDOW:])
        adverse_pct = (1.0 - closes[-1] / ref) * 100.0 if ref else 0.0
    else:
        ref = min(lows[-PERSIST_WINDOW:])
        adverse_pct = (closes[-1] / ref - 1.0) * 100.0 if ref else 0.0
    if adverse_pct >= 0.20:
        score += 1
        reasons.append(f"adverse={adverse_pct:.3f}%")

    # 5) RSI is context only.  It earns one point only when it agrees with
    # the reversal direction; it is never sufficient by itself.
    if rsi is not None:
        if prior_state == "LONG" and rsi < 45.0:
            score += 1
            reasons.append(f"rsi_context={rsi:.1f}")
        elif prior_state == "SHORT" and rsi > 55.0:
            score += 1
            reasons.append(f"rsi_context={rsi:.1f}")

    # 6) Structural context: if the 30m close has already moved back toward
    # the MA, reversal evidence gets one point.  This is NOT a state change.
    if prior_state == "LONG" and ma_distance_pct < 0.40:
        score += 1
        reasons.append(f"30m_distance={ma_distance_pct:.3f}%")
    elif prior_state == "SHORT" and ma_distance_pct > -0.40:
        score += 1
        reasons.append(f"30m_distance={ma_distance_pct:.3f}%")

    return score, reasons


def build_events(rows30: Sequence[Dict[str, Any]], rows5: Sequence[Dict[str, Any]], symbol: str) -> List[Dict[str, Any]]:
    if len(rows30) < TREND_WINDOW + 5 or len(rows5) < MIN_5M_HISTORY:
        return []

    closes30 = [r["close"] for r in rows30]
    closes5 = [r["close"] for r in rows5]
    rsi5 = rsi_series(closes5)
    by5 = rows5
    events: List[Dict[str, Any]] = []

    for i in range(TREND_WINDOW + 1, len(rows30) - 2):
        prior_state = market_state(closes30, i - 1)
        if prior_state not in ("LONG", "SHORT"):
            continue

        # Evaluate the first 5m bars from the beginning of this 30m bar.
        start = rows30[i]["timestamp"]
        end = start + timedelta(minutes=CANDIDATE_BEFORE_MINUTES)
        candidates = nearest_5m(by5, start, end)
        if not candidates:
            continue

        label_time = future_opposite_time(rows30, closes30, i, prior_state, LOOKAHEAD_MINUTES)
        label = label_time is not None

        for bar in candidates:
            bt = bar["timestamp"]
            history = [r for r in by5 if r["timestamp"] <= bt]
            if len(history) < MIN_5M_HISTORY:
                continue
            # Only use 5m information available at bt.  The latest 30m
            # structural context is the last completed 30m bar BEFORE the
            # current 30m bar.
            ctx_idx = i - 1
            ctx_distance = structural_context(rows30, closes30, ctx_idx)
            rsi_idx = len(history) - 1
            rsi_value = rsi5[rsi_idx] if rsi_idx < len(rsi5) else None
            score, reasons = feature_score(history[-20:], prior_state, rsi_value, ctx_distance)
            events.append({
                "symbol": symbol,
                "time": bt,
                "prior_state": prior_state,
                "target": opposite(prior_state),
                "label": label,
                "transition_time": label_time,
                "score": score,
                "reasons": reasons,
            })
    return events


def chronological_split(events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by = defaultdict(list)
    for e in events:
        by[e["symbol"]].append(e)
    discovery: List[Dict[str, Any]] = []
    holdout: List[Dict[str, Any]] = []
    for symbol, rows in by.items():
        rows.sort(key=lambda x: x["time"])
        cut = int(len(rows) * 0.70)
        discovery.extend(rows[:cut])
        holdout.extend(rows[cut:])
    return discovery, holdout


def pct(n: int, d: int) -> float:
    return 0.0 if d == 0 else 100.0 * n / d


def evaluate(events: List[Dict[str, Any]], threshold: int, label: str) -> None:
    """Evaluate a threshold without double-counting each transition.

    A detector fires on the FIRST bar at/after each 30m transition window where
    score >= threshold.  False exits are counted on candidate windows with no
    future opposite state.  For real transitions, timing is measured from the
    first 5m bar in the 30m window to the future opposite-state label.
    """
    by_window: Dict[Tuple[str, datetime, str], List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        key = (e["symbol"], e["time"].replace(minute=(e["time"].minute // 30) * 30, second=0, microsecond=0), e["prior_state"])
        by_window[key].append(e)

    windows = []
    for key, rows in by_window.items():
        rows.sort(key=lambda x: x["time"])
        first = rows[0]
        fires = [x for x in rows if x["score"] >= threshold]
        fire = fires[0] if fires else None
        windows.append((first, fire))

    real = [(first, fire) for first, fire in windows if first["label"]]
    no_change = [(first, fire) for first, fire in windows if not first["label"]]
    recognized = [(first, fire) for first, fire in real if fire is not None and fire["time"] <= first["transition_time"]]
    late = [(first, fire) for first, fire in real if fire is not None and fire["time"] > first["transition_time"]]
    false = [(first, fire) for first, fire in no_change if fire is not None]

    delays = []
    for first, fire in recognized:
        # Positive means the detector fired before the actual transition.
        delays.append((first["transition_time"] - fire["time"]).total_seconds() / 60.0)

    print(f"{label} threshold={threshold}")
    print(f"  windows={len(windows)} real={len(real)} no_change={len(no_change)}")
    print(f"  recognized_before={pct(len(recognized), len(real)):.1f}% | late={pct(len(late), len(real)):.1f}%")
    print(f"  false_exit_rate={pct(len(false), len(no_change)):.1f}%")
    if delays:
        print(f"  lead_minutes mean={mean(delays):.1f} median={median(delays):.1f} | within5={pct(sum(x <= 5 for x in delays), len(delays)):.1f}% | within15={pct(sum(x <= 15 for x in delays), len(delays)):.1f}%")
    else:
        print("  lead_minutes n/a")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit", type=int, default=10000)
    args = ap.parse_args()

    print("KISS TRANSITION DETECTOR V1")
    print("Research only — NO strategy/engine changes, NO orders, NO DB writes")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Future opposite-state label horizon: {LOOKAHEAD_MINUTES}m")
    print("Score components: 5m reversal structure + persistence + displacement + RSI context + 30m context")

    events: List[Dict[str, Any]] = []
    for symbol in args.symbols:
        try:
            r30 = load(symbol, "30m", args.limit)
            r5 = load(symbol, "5m", args.limit)
            e = build_events(r30, r5, symbol)
            events.extend(e)
            print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} candidate_rows={len(e)}")
        except Exception as exc:
            print(f"{symbol}: ERROR: {exc}")

    discovery, holdout = chronological_split(events)
    print(f"\nTOTAL candidate rows: {len(events)}")
    print(f"DISCOVERY rows: {len(discovery)} | HOLDOUT rows: {len(holdout)}")

    for name, data in (("FULL", events), ("DISCOVERY", discovery), ("HOLDOUT", holdout)):
        print(f"\n{'=' * 72}\n{name}\n{'=' * 72}")
        for threshold in SCORE_THRESHOLDS:
            evaluate(data, threshold, name)

    print("\nINTERPRETATION")
    print("-------------")
    print("We want the HOLDOUT result to show a useful frontier:")
    print("  - most real transitions recognized before the official opposite 30m state")
    print("  - a substantial fraction recognized within 5–15 minutes")
    print("  - false exits low enough to be operationally manageable")
    print("A threshold is NOT a production rule from this experiment alone.")
    print("The next step is to inspect the holdout frontier and individual cases")
    print("before connecting any detector to KISS execution.")


if __name__ == "__main__":
    main()
