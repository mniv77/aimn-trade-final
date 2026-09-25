#!/usr/bin/env python3
"""
V5.6.12 GOOD-vs-FALSE ANALYSIS
==============================

Research only.

Purpose:
    Study what separates a V5.6.12 FIRST WARNING that was useful
    from a FIRST WARNING that would have produced a premature exit.

This file DOES NOT:
    - modify the trading engine
    - place orders
    - modify database data
    - create trading rules
    - use future information to create warning features

The future is used ONLY to label the outcome AFTER the warning:

    GOOD_EXIT
        HOLD-60 <= -0.10%

    FALSE_EXIT
        HOLD-60 >= +0.10%

    NEUTRAL
        otherwise

The analysis compares the causal information available at the
warning moment:

    - direction
    - warning reason
    - health state
    - health score
    - adverse candle count
    - consecutive adverse candles
    - net signed move
    - structure break
    - severe balance
    - repeated adverse behavior
    - distance to official transition
    - warning timing

The goal is NOT to optimize thresholds.

The goal is to discover whether the existing V5.6.12 features
contain a useful separation between:

    "this is real trend damage"

and

    "this is temporary stress/noise"

That distinction is the next step toward:

    NOTICE
       ↓
    EVALUATE
       ↓
    CONTINUED DAMAGE?
       ↓
    EXIT

while keeping opposite-direction recognition separate.
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from db import get_db_connection


# ============================================================
# CONFIGURATION
# ============================================================

TREND_WINDOW = 20
TREND_BAND = 0.002

BAR_MINUTES = 5

LOOKBACK_MINUTES = 480
FUTURE_MINUTES = 120

EVAL_MINUTES = 60

EPISODE_GAP_MINUTES = 15

GOOD_THRESHOLD = -0.10
FALSE_THRESHOLD = 0.10

MIN_HISTORY_MINUTES = 120

DEFAULT_SYMBOLS = [
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "TSLA",
    "SPY",
    "QQQ",
]


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class WarningCase:
    symbol: str
    direction: str

    warning_time: datetime
    t0: datetime

    health: str
    reason: str

    score: float

    adverse_count: int
    consecutive_adverse: int

    net_signed_pct: float

    structure_break: bool
    severe_balance: bool
    persistent_adverse: bool
    repeated_adverse: bool

    price: float

    hold15: Optional[float]
    hold30: Optional[float]
    hold60: Optional[float]
    hold120: Optional[float]

    minutes_to_t0: float

    outcome: str = "UNKNOWN"


# ============================================================
# DB
# ============================================================

def load_rows(symbol: str, timeframe: str) -> List[dict]:
    """
    Load candles.

    db.py returns:
        (connection, cursor)

    Keep this compatible with the project DB contract.
    """

    conn, _ = get_db_connection()
    cur = None

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s
              AND timeframe=%s
            ORDER BY timestamp ASC
            """,
            (symbol, timeframe),
        )

        return list(cur.fetchall())

    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass

        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# ============================================================
# BASIC HELPERS
# ============================================================

def pct(a: float, b: float) -> float:
    """
    Percentage return from a to b.
    """
    if a == 0:
        return 0.0
    return ((b / a) - 1.0) * 100.0


def safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default

        x = float(value)

        if not math.isfinite(x):
            return default

        return x

    except Exception:
        return default


def median_or_zero(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return statistics.median(values)


def mean_or_zero(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return statistics.mean(values)


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"

    return f"{value:+.3f}%"


def fmt_num(value: Optional[float]) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}"


def fmt_time_delta(minutes: Optional[float]) -> str:
    if minutes is None:
        return "N/A"

    if minutes >= 0:
        return f"+{minutes:.0f}m"

    return f"{minutes:.0f}m"


# ============================================================
# TIMESTAMP / CANDLE HELPERS
# ============================================================

def normalize_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        return datetime.fromisoformat(value)

    raise TypeError(f"Unsupported timestamp type: {type(value)}")


def close_time(row: dict, timeframe_minutes: int) -> datetime:
    ts = normalize_timestamp(row["timestamp"])
    return ts + timedelta(minutes=timeframe_minutes)


def completed_5m_rows(rows: Sequence[dict]) -> List[dict]:
    """
    Return rows with normalized timestamps.

    The timestamp represents candle START.

    Therefore a 5m candle becomes available at:
        timestamp + 5 minutes
    """

    result = []

    for row in rows:
        r = dict(row)
        r["_timestamp"] = normalize_timestamp(r["timestamp"])
        r["_close_time"] = r["_timestamp"] + timedelta(minutes=5)
        r["_open"] = safe_float(r.get("open"))
        r["_high"] = safe_float(r.get("high"))
        r["_low"] = safe_float(r.get("low"))
        r["_close"] = safe_float(r.get("close"))
        result.append(r)

    return result


def completed_30m_rows(rows: Sequence[dict]) -> List[dict]:
    result = []

    for row in rows:
        r = dict(row)
        r["_timestamp"] = normalize_timestamp(row["timestamp"])
        r["_close_time"] = r["_timestamp"] + timedelta(minutes=30)
        r["_open"] = safe_float(r.get("open"))
        r["_high"] = safe_float(r.get("high"))
        r["_low"] = safe_float(r.get("low"))
        r["_close"] = safe_float(r.get("close"))
        result.append(r)

    return result


# ============================================================
# EXACT CLOSE LOOKUP
# ============================================================

def close_index_5m(
    rows: Sequence[dict],
    target: datetime,
) -> Optional[int]:
    """
    Exact completed 5m close lookup.

    A candle stamped T closes at T+5m.

    We intentionally do NOT use nearest candle logic because
    that can introduce timing leakage or repeated observations.
    """

    for i, row in enumerate(rows):

        if row["_close_time"] == target:
            return i

    return None


def close_index_30m(
    rows: Sequence[dict],
    target: datetime,
) -> Optional[int]:

    for i, row in enumerate(rows):

        if row["_close_time"] == target:
            return i

    return None


# ============================================================
# 30M KISS STATE
# ============================================================

def get_market_state(
    closes: Sequence[float],
    idx: int,
) -> str:

    if idx < TREND_WINDOW:
        return "FLAT"

    if idx >= len(closes):
        return "FLAT"

    window = closes[idx - TREND_WINDOW:idx]

    if len(window) < TREND_WINDOW:
        return "FLAT"

    ma = sum(window) / TREND_WINDOW

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def build_30m_states(rows: Sequence[dict]) -> List[str]:

    closes = [r["_close"] for r in rows]

    states = []

    for i in range(len(rows)):
        states.append(get_market_state(closes, i))

    return states


# ============================================================
# SESSION / TRANSITION DISCOVERY
# ============================================================

def find_session_boundaries(
    rows: Sequence[dict],
) -> List[int]:

    boundaries = []

    for i in range(1, len(rows)):

        previous = rows[i - 1]["_timestamp"]
        current = rows[i]["_timestamp"]

        gap_minutes = (
            current - previous
        ).total_seconds() / 60.0

        if gap_minutes > 120:
            boundaries.append(i)

    return boundaries


def find_directional_transitions(
    rows30: Sequence[dict],
    states30: Sequence[str],
) -> List[Tuple[datetime, str, str]]:

    transitions = []

    for i in range(1, len(rows30)):

        previous = states30[i - 1]
        current = states30[i]

        if previous == current:
            continue

        if previous == "LONG" and current == "SHORT":
            transitions.append(
                (
                    rows30[i]["_close_time"],
                    "LONG",
                    "SHORT",
                )
            )

        elif previous == "SHORT" and current == "LONG":
            transitions.append(
                (
                    rows30[i]["_close_time"],
                    "SHORT",
                    "LONG",
                )
            )

    return transitions


# ============================================================
# RELATIVE PRICE POSITION
# ============================================================

def relative_position(
    closes: Sequence[float],
    idx: int,
    lookback: int = 12,
) -> Optional[float]:

    if idx < lookback:
        return None

    window = closes[idx - lookback:idx]

    if not window:
        return None

    low = min(window)
    high = max(window)

    if high <= low:
        return 50.0

    return (
        (closes[idx] - low)
        / (high - low)
    ) * 100.0


# ============================================================
# CAUSAL 5M FEATURES
# ============================================================

def directional_signed_move(
    direction: str,
    start_price: float,
    end_price: float,
) -> float:

    raw = pct(start_price, end_price)

    if direction == "LONG":
        return raw

    if direction == "SHORT":
        return -raw

    return 0.0


def candle_is_adverse(
    row: dict,
    direction: str,
) -> bool:

    if direction == "LONG":
        return row["_close"] < row["_open"]

    if direction == "SHORT":
        return row["_close"] > row["_open"]

    return False


def calculate_consecutive_adverse(
    rows: Sequence[dict],
    end_idx: int,
    direction: str,
    max_bars: int = 12,
) -> int:

    count = 0

    start = max(0, end_idx - max_bars + 1)

    for i in range(end_idx, start - 1, -1):

        if candle_is_adverse(rows[i], direction):
            count += 1
        else:
            break

    return count


def calculate_adverse_count(
    rows: Sequence[dict],
    end_idx: int,
    direction: str,
    max_bars: int = 12,
) -> int:

    count = 0

    start = max(0, end_idx - max_bars + 1)

    for i in range(start, end_idx + 1):

        if candle_is_adverse(rows[i], direction):
            count += 1

    return count


def structure_break_detected(
    rows: Sequence[dict],
    idx: int,
    direction: str,
) -> bool:

    if idx < 4:
        return False

    previous = rows[idx - 4:idx]

    if direction == "LONG":

        previous_low = min(
            r["_low"] for r in previous
        )

        return rows[idx]["_close"] < previous_low

    if direction == "SHORT":

        previous_high = max(
            r["_high"] for r in previous
        )

        return rows[idx]["_close"] > previous_high

    return False


def severe_balance_detected(
    rows: Sequence[dict],
    idx: int,
    direction: str,
) -> bool:

    if idx < 5:
        return False

    window = rows[idx - 4:idx + 1]

    adverse = sum(
        1
        for r in window
        if candle_is_adverse(r, direction)
    )

    if direction == "LONG":

        move = directional_signed_move(
            direction,
            window[0]["_close"],
            window[-1]["_close"],
        )

        return (
            adverse >= 3
            and move <= -0.15
        )

    if direction == "SHORT":

        move = directional_signed_move(
            direction,
            window[0]["_close"],
            window[-1]["_close"],
        )

        return (
            adverse >= 3
            and move <= -0.15
        )

    return False


def persistent_adverse_detected(
    rows: Sequence[dict],
    idx: int,
    direction: str,
) -> bool:

    adverse = calculate_adverse_count(
        rows,
        idx,
        direction,
        max_bars=6,
    )

    consecutive = calculate_consecutive_adverse(
        rows,
        idx,
        direction,
        max_bars=6,
    )

    if idx < 5:
        return False

    start_price = rows[idx - 5]["_close"]
    end_price = rows[idx]["_close"]

    net = directional_signed_move(
        direction,
        start_price,
        end_price,
    )

    return (
        adverse >= 3
        and net <= -0.10
    ) or (
        consecutive >= 2
        and net <= -0.10
    )


def repeated_adverse_detected(
    rows: Sequence[dict],
    idx: int,
    direction: str,
) -> bool:

    if idx < 3:
        return False

    adverse = calculate_adverse_count(
        rows,
        idx,
        direction,
        max_bars=4,
    )

    consecutive = calculate_consecutive_adverse(
        rows,
        idx,
        direction,
        max_bars=4,
    )

    return (
        adverse >= 2
        or consecutive >= 2
    )


def calculate_health_score(
    rows: Sequence[dict],
    idx: int,
    direction: str,
) -> Tuple[
    float,
    int,
    int,
    float,
    bool,
    bool,
    bool,
    bool,
]:

    adverse_count = calculate_adverse_count(
        rows,
        idx,
        direction,
        max_bars=12,
    )

    consecutive_adverse = calculate_consecutive_adverse(
        rows,
        idx,
        direction,
        max_bars=12,
    )

    if idx >= 12:

        net_signed = directional_signed_move(
            direction,
            rows[idx - 12]["_close"],
            rows[idx]["_close"],
        )

    else:

        net_signed = directional_signed_move(
            direction,
            rows[0]["_close"],
            rows[idx]["_close"],
        )

    structure_break = structure_break_detected(
        rows,
        idx,
        direction,
    )

    severe_balance = severe_balance_detected(
        rows,
        idx,
        direction,
    )

    persistent_adverse = persistent_adverse_detected(
        rows,
        idx,
        direction,
    )

    repeated_adverse = repeated_adverse_detected(
        rows,
        idx,
        direction,
    )

    score = 0.0

    if structure_break:
        score += 3.0

    if persistent_adverse:
        score += 2.0

    if severe_balance:
        score += 1.0

    if repeated_adverse:
        score += 1.0

    if net_signed <= -0.50:
        score += 1.0

    elif net_signed <= -0.25:
        score += 0.5

    if consecutive_adverse >= 3:
        score += 0.5

    return (
        score,
        adverse_count,
        consecutive_adverse,
        net_signed,
        structure_break,
        severe_balance,
        persistent_adverse,
        repeated_adverse,
    )


# ============================================================
# V5.6.12 HEALTH CLASSIFICATION
# ============================================================

def classify_health(
    score: float,
    net_signed: float,
    adverse_count: int,
    severe_balance: bool,
) -> str:

    if severe_balance and score >= 4.0:
        return "CRITICAL"

    if score >= 2.0:
        return "DETERIORATING"

    if net_signed <= -0.20:
        return "DETERIORATING"

    if adverse_count >= 1 or net_signed < -0.05:
        return "STRESSED"

    return "HEALTHY"


# ============================================================
# CAUSAL STATE TRANSITION
# ============================================================

HEALTH_ORDER = {
    "HEALTHY": 0,
    "STRESSED": 1,
    "DETERIORATING": 2,
    "CRITICAL": 3,
}


def transition_state(
    previous: str,
    proposed: str,
) -> str:

    previous_level = HEALTH_ORDER[previous]
    proposed_level = HEALTH_ORDER[proposed]

    if proposed_level > previous_level:

        return min(
            proposed_level,
            previous_level + 1,
        ) and {
            0: "HEALTHY",
            1: "STRESSED",
            2: "DETERIORATING",
            3: "CRITICAL",
        }[min(proposed_level, previous_level + 1)]

    if proposed_level < previous_level:

        return {
            0: "HEALTHY",
            1: "STRESSED",
            2: "DETERIORATING",
            3: "CRITICAL",
        }[
            max(
                proposed_level,
                previous_level - 1,
            )
        ]

    return previous


# ============================================================
# WARNING EXTRACTION
# ============================================================

def warning_reason(
    structure_break: bool,
    persistent_adverse: bool,
    severe_balance: bool,
    repeated_adverse: bool,
) -> str:

    if structure_break:
        return "structure_break"

    if persistent_adverse:
        return "persistent_adverse"

    if severe_balance:
        return "severe_balance"

    if repeated_adverse:
        return "repeated_adverse"

    return "health_change"


def generate_health_warnings(
    rows5: Sequence[dict],
    warning_start: datetime,
    warning_end: datetime,
    direction: str,
) -> List[dict]:

    warnings = []

    state = "HEALTHY"

    for i, row in enumerate(rows5):

        close_at = row["_close_time"]

        if close_at < warning_start:
            continue

        if close_at > warning_end:
            break

        (
            score,
            adverse_count,
            consecutive_adverse,
            net_signed,
            structure_break,
            severe_balance,
            persistent_adverse,
            repeated_adverse,
        ) = calculate_health_score(
            rows5,
            i,
            direction,
        )

        proposed = classify_health(
            score,
            net_signed,
            adverse_count,
            severe_balance,
        )

        new_state = transition_state(
            state,
            proposed,
        )

        if new_state != state:

            # V5.6.12 warning candidate.
            # We are interested in the first deterioration episode,
            # not every candle afterward.

            if HEALTH_ORDER[new_state] > HEALTH_ORDER[state]:

                reason = warning_reason(
                    structure_break,
                    persistent_adverse,
                    severe_balance,
                    repeated_adverse,
                )

                warnings.append(
                    {
                        "time": close_at,
                        "health": new_state,
                        "reason": reason,
                        "score": score,
                        "adverse_count": adverse_count,
                        "consecutive_adverse": consecutive_adverse,
                        "net_signed": net_signed,
                        "structure_break": structure_break,
                        "severe_balance": severe_balance,
                        "persistent_adverse": persistent_adverse,
                        "repeated_adverse": repeated_adverse,
                        "price": row["_close"],
                    }
                )

        state = new_state

    return warnings


# ============================================================
# OUTCOME CALCULATION
# ============================================================

def close_at_or_after(
    rows: Sequence[dict],
    target: datetime,
) -> Optional[int]:

    for i, row in enumerate(rows):

        if row["_close_time"] >= target:
            return i

    return None


def future_return(
    rows: Sequence[dict],
    warning_time: datetime,
    direction: str,
    minutes: int,
) -> Optional[float]:

    start_idx = close_at_or_after(
        rows,
        warning_time,
    )

    if start_idx is None:
        return None

    target = warning_time + timedelta(
        minutes=minutes
    )

    end_idx = close_at_or_after(
        rows,
        target,
    )

    if end_idx is None:
        return None

    start_price = rows[start_idx]["_close"]
    end_price = rows[end_idx]["_close"]

    return directional_signed_move(
        direction,
        start_price,
        end_price,
    )


def classify_outcome(
    hold60: Optional[float],
) -> str:

    if hold60 is None:
        return "UNKNOWN"

    if hold60 <= GOOD_THRESHOLD:
        return "GOOD_EXIT"

    if hold60 >= FALSE_THRESHOLD:
        return "FALSE_EXIT"

    return "NEUTRAL"


# ============================================================
# EPISODE CLUSTERING
# ============================================================

def cluster_warnings(
    warnings: Sequence[dict],
) -> List[dict]:

    if not warnings:
        return []

    ordered = sorted(
        warnings,
        key=lambda x: x["time"],
    )

    episodes = []

    current = None

    for warning in ordered:

        if current is None:

            current = {
                "first": warning,
                "warnings": [warning],
            }

            continue

        gap = (
            warning["time"]
            - current["warnings"][-1]["time"]
        ).total_seconds() / 60.0

        if gap <= EPISODE_GAP_MINUTES:

            current["warnings"].append(warning)

        else:

            episodes.append(current)

            current = {
                "first": warning,
                "warnings": [warning],
            }

    if current is not None:
        episodes.append(current)

    return episodes


# ============================================================
# BUILD CASES
# ============================================================

def build_cases_for_transition(
    symbol: str,
    rows5: Sequence[dict],
    t0: datetime,
    direction: str,
) -> List[WarningCase]:

    warning_start = t0 - timedelta(
        minutes=LOOKBACK_MINUTES
    )

    warning_end = t0

    warnings = generate_health_warnings(
        rows5,
        warning_start,
        warning_end,
        direction,
    )

    episodes = cluster_warnings(
        warnings
    )

    cases = []

    for episode in episodes:

        first = episode["first"]

        warning_time = first["time"]

        hold15 = future_return(
            rows5,
            warning_time,
            direction,
            15,
        )

        hold30 = future_return(
            rows5,
            warning_time,
            direction,
            30,
        )

        hold60 = future_return(
            rows5,
            warning_time,
            direction,
            60,
        )

        hold120 = future_return(
            rows5,
            warning_time,
            direction,
            120,
        )

        outcome = classify_outcome(
            hold60
        )

        minutes_to_t0 = (
            t0 - warning_time
        ).total_seconds() / 60.0

        cases.append(
            WarningCase(
                symbol=symbol,
                direction=direction,
                warning_time=warning_time,
                t0=t0,
                health=first["health"],
                reason=first["reason"],
                score=safe_float(first["score"]),
                adverse_count=int(
                    first["adverse_count"]
                ),
                consecutive_adverse=int(
                    first["consecutive_adverse"]
                ),
                net_signed_pct=safe_float(
                    first["net_signed"]
                ),
                structure_break=bool(
                    first["structure_break"]
                ),
                severe_balance=bool(
                    first["severe_balance"]
                ),
                persistent_adverse=bool(
                    first["persistent_adverse"]
                ),
                repeated_adverse=bool(
                    first["repeated_adverse"]
                ),
                price=safe_float(
                    first["price"]
                ),
                hold15=hold15,
                hold30=hold30,
                hold60=hold60,
                hold120=hold120,
                minutes_to_t0=minutes_to_t0,
                outcome=outcome,
            )
        )

    return cases


# ============================================================
# FEATURE STATISTICS
# ============================================================

def group_cases(
    cases: Sequence[WarningCase],
    key_fn,
) -> Dict[str, List[WarningCase]]:

    groups = defaultdict(list)

    for case in cases:
        groups[str(key_fn(case))].append(case)

    return groups


def valid_cases(
    cases: Sequence[WarningCase],
) -> List[WarningCase]:

    return [
        c
        for c in cases
        if c.outcome in {
            "GOOD_EXIT",
            "FALSE_EXIT",
            "NEUTRAL",
        }
    ]


def outcome_counts(
    cases: Sequence[WarningCase],
) -> Counter:

    return Counter(
        c.outcome
        for c in cases
    )


def print_outcome_summary(
    title: str,
    cases: Sequence[WarningCase],
) -> None:

    valid = valid_cases(cases)

    counts = outcome_counts(valid)

    good = counts["GOOD_EXIT"]
    false = counts["FALSE_EXIT"]
    neutral = counts["NEUTRAL"]

    total = len(valid)

    good_pct = (
        100.0 * good / total
        if total
        else 0.0
    )

    false_pct = (
        100.0 * false / total
        if total
        else 0.0
    )

    neutral_pct = (
        100.0 * neutral / total
        if total
        else 0.0
    )

    hold60 = [
        c.hold60
        for c in valid
        if c.hold60 is not None
    ]

    print()
    print("=" * 72)
    print(title)
    print("=" * 72)

    print(
        f"TOTAL CASES: {len(cases)}"
    )

    print(
        f"VALID OUTCOMES: {total}"
    )

    print(
        f"GOOD_EXIT:    {good:4d} "
        f"({good_pct:5.1f}%)"
    )

    print(
        f"FALSE_EXIT:   {false:4d} "
        f"({false_pct:5.1f}%)"
    )

    print(
        f"NEUTRAL:      {neutral:4d} "
        f"({neutral_pct:5.1f}%)"
    )

    print(
        f"AVG HOLD60:   {mean_or_zero(hold60):+.3f}%"
    )


# ============================================================
# FEATURE COMPARISON
# ============================================================

def print_feature_comparison(
    cases: Sequence[WarningCase],
) -> None:

    good = [
        c for c in cases
        if c.outcome == "GOOD_EXIT"
    ]

    false = [
        c for c in cases
        if c.outcome == "FALSE_EXIT"
    ]

    neutral = [
        c for c in cases
        if c.outcome == "NEUTRAL"
    ]

    print()
    print("=" * 72)
    print("GOOD vs FALSE FEATURE COMPARISON")
    print("=" * 72)

    print()
    print(
        f"{'FEATURE':30s}"
        f"{'GOOD':>14s}"
        f"{'FALSE':>14s}"
        f"{'NEUTRAL':>14s}"
    )

    print("-" * 72)

    rows = [
        (
            "Score",
            lambda c: c.score,
        ),
        (
            "Adverse count",
            lambda c: c.adverse_count,
        ),
        (
            "Consecutive adverse",
            lambda c: c.consecutive_adverse,
        ),
        (
            "Net signed move",
            lambda c: c.net_signed_pct,
        ),
        (
            "Minutes to T0",
            lambda c: c.minutes_to_t0,
        ),
        (
            "HOLD15",
            lambda c: c.hold15,
        ),
        (
            "HOLD30",
            lambda c: c.hold30,
        ),
        (
            "HOLD60",
            lambda c: c.hold60,
        ),
        (
            "HOLD120",
            lambda c: c.hold120,
        ),
    ]

    for name, fn in rows:

        def vals(group):

            result = []

            for case in group:

                value = fn(case)

                if value is not None:
                    result.append(
                        float(value)
                    )

            return result

        g = vals(good)
        f = vals(false)
        n = vals(neutral)

        print(
            f"{name:30s}"
            f"{mean_or_zero(g):>14.3f}"
            f"{mean_or_zero(f):>14.3f}"
            f"{mean_or_zero(n):>14.3f}"
        )


# ============================================================
# BOOLEAN FEATURE COMPARISON
# ============================================================

def print_boolean_comparison(
    cases: Sequence[WarningCase],
) -> None:

    groups = {
        "GOOD_EXIT": [
            c for c in cases
            if c.outcome == "GOOD_EXIT"
        ],
        "FALSE_EXIT": [
            c for c in cases
            if c.outcome == "FALSE_EXIT"
        ],
        "NEUTRAL": [
            c for c in cases
            if c.outcome == "NEUTRAL"
        ],
    }

    print()
    print("=" * 72)
    print("BOOLEAN FEATURE RATES")
    print("=" * 72)

    print()
    print(
        f"{'FEATURE':30s}"
        f"{'GOOD':>12s}"
        f"{'FALSE':>12s}"
        f"{'NEUTRAL':>12s}"
    )

    print("-" * 72)

    features = [
        (
            "Structure break",
            lambda c: c.structure_break,
        ),
        (
            "Severe balance",
            lambda c: c.severe_balance,
        ),
        (
            "Persistent adverse",
            lambda c: c.persistent_adverse,
        ),
        (
            "Repeated adverse",
            lambda c: c.repeated_adverse,
        ),
    ]

    for name, fn in features:

        line = f"{name:30s}"

        for group_name in [
            "GOOD_EXIT",
            "FALSE_EXIT",
            "NEUTRAL",
        ]:

            group = groups[group_name]

            if not group:
                value = 0.0
            else:
                count = sum(
                    1
                    for c in group
                    if fn(c)
                )

                value = (
                    100.0
                    * count
                    / len(group)
                )

            line += f"{value:11.1f}% "

        print(line)


# ============================================================
# REASON ANALYSIS
# ============================================================

def print_reason_analysis(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("WARNING REASON ANALYSIS")
    print("=" * 72)

    groups = group_cases(
        cases,
        lambda c: c.reason,
    )

    print()
    print(
        f"{'REASON':28s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
    )

    print("-" * 72)

    for reason, group in sorted(
        groups.items(),
        key=lambda x: -len(x[1]),
    ):

        valid = valid_cases(group)

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        print(
            f"{reason:28s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
        )


# ============================================================
# HEALTH STATE ANALYSIS
# ============================================================

def print_health_analysis(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("HEALTH STATE ANALYSIS")
    print("=" * 72)

    groups = group_cases(
        cases,
        lambda c: c.health,
    )

    print()
    print(
        f"{'HEALTH':24s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
    )

    print("-" * 72)

    health_order = [
        "HEALTHY",
        "STRESSED",
        "DETERIORATING",
        "CRITICAL",
    ]

    for health in health_order:

        group = groups.get(
            health,
            [],
        )

        valid = valid_cases(group)

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        print(
            f"{health:24s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
        )


# ============================================================
# SCORE BUCKETS
# ============================================================

def score_bucket(score: float) -> str:

    if score < 1:
        return "<1"

    if score < 2:
        return "1-<2"

    if score < 3:
        return "2-<3"

    if score < 4:
        return "3-<4"

    return "4+"


def print_score_analysis(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("HEALTH SCORE BUCKET ANALYSIS")
    print("=" * 72)

    groups = group_cases(
        cases,
        lambda c: score_bucket(c.score),
    )

    order = [
        "<1",
        "1-<2",
        "2-<3",
        "3-<4",
        "4+",
    ]

    print()
    print(
        f"{'SCORE':15s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
    )

    print("-" * 72)

    for bucket in order:

        valid = valid_cases(
            groups.get(bucket, [])
        )

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        print(
            f"{bucket:15s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
        )


# ============================================================
# DIRECTION COMPARISON
# ============================================================

def print_direction_analysis(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("DIRECTION COMPARISON")
    print("=" * 72)

    print()
    print(
        f"{'DIRECTION':20s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
        f"{'MED T0':>12s}"
    )

    print("-" * 72)

    for direction in [
        "LONG->SHORT",
        "SHORT->LONG",
    ]:

        group = [
            c for c in cases
            if (
                (
                    direction == "LONG->SHORT"
                    and c.direction == "LONG"
                )
                or
                (
                    direction == "SHORT->LONG"
                    and c.direction == "SHORT"
                )
            )
        ]

        valid = valid_cases(group)

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        med_t0 = median_or_zero(
            [
                c.minutes_to_t0
                for c in valid
            ]
        )

        print(
            f"{direction:20s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
            f"{med_t0:11.1f}m"
        )


# ============================================================
# COMBINED FEATURE ANALYSIS
# ============================================================

def print_combined_analysis(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("COMBINED FEATURE ANALYSIS")
    print("=" * 72)

    combinations = [
        (
            "structure + persistent",
            lambda c:
                c.structure_break
                and c.persistent_adverse,
        ),
        (
            "structure + severe",
            lambda c:
                c.structure_break
                and c.severe_balance,
        ),
        (
            "persistent + repeated",
            lambda c:
                c.persistent_adverse
                and c.repeated_adverse,
        ),
        (
            "structure + persistent + severe",
            lambda c:
                c.structure_break
                and c.persistent_adverse
                and c.severe_balance,
        ),
        (
            "2+ consecutive adverse",
            lambda c:
                c.consecutive_adverse >= 2,
        ),
        (
            "3+ consecutive adverse",
            lambda c:
                c.consecutive_adverse >= 3,
        ),
        (
            "net <= -0.20%",
            lambda c:
                c.net_signed_pct <= -0.20,
        ),
        (
            "net <= -0.50%",
            lambda c:
                c.net_signed_pct <= -0.50,
        ),
    ]

    print()
    print(
        f"{'CONDITION':38s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
    )

    print("-" * 80)

    for name, fn in combinations:

        selected = [
            c
            for c in cases
            if fn(c)
        ]

        valid = valid_cases(
            selected
        )

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        print(
            f"{name:38s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
        )


# ============================================================
# FIRST WARNING VS LATER WARNING
# ============================================================

def print_timing_buckets(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("WARNING TIMING RELATIVE TO OFFICIAL T0")
    print("=" * 72)

    buckets = [
        ("0-15m", 0, 15),
        ("15-30m", 15, 30),
        ("30-60m", 30, 60),
        ("60-120m", 60, 120),
        ("120-240m", 120, 240),
        ("240m+", 240, 999999),
    ]

    print()
    print(
        f"{'TIMING':15s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
    )

    print("-" * 72)

    for name, low, high in buckets:

        selected = [
            c
            for c in cases
            if low <= c.minutes_to_t0 < high
        ]

        valid = valid_cases(
            selected
        )

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        print(
            f"{name:15s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
        )


# ============================================================
# SYMBOL ANALYSIS
# ============================================================

def print_symbol_analysis(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("SYMBOL ANALYSIS")
    print("=" * 72)

    groups = group_cases(
        cases,
        lambda c: c.symbol,
    )

    print()
    print(
        f"{'SYMBOL':12s}"
        f"{'N':>7s}"
        f"{'GOOD%':>10s}"
        f"{'FALSE%':>10s}"
        f"{'AVG60':>12s}"
    )

    print("-" * 72)

    for symbol, group in sorted(
        groups.items()
    ):

        valid = valid_cases(group)

        if not valid:
            continue

        counts = outcome_counts(valid)

        total = len(valid)

        good_pct = (
            100.0
            * counts["GOOD_EXIT"]
            / total
        )

        false_pct = (
            100.0
            * counts["FALSE_EXIT"]
            / total
        )

        avg60 = mean_or_zero(
            [
                c.hold60
                for c in valid
                if c.hold60 is not None
            ]
        )

        print(
            f"{symbol:12s}"
            f"{total:7d}"
            f"{good_pct:9.1f}%"
            f"{false_pct:9.1f}%"
            f"{avg60:+11.3f}%"
        )


# ============================================================
# REPRESENTATIVE CASES
# ============================================================

def print_representative_cases(
    cases: Sequence[WarningCase],
    max_cases: int = 20,
) -> None:

    good = sorted(
        [
            c for c in cases
            if c.outcome == "GOOD_EXIT"
        ],
        key=lambda c: (
            c.hold60
            if c.hold60 is not None
            else 999
        ),
    )

    false = sorted(
        [
            c for c in cases
            if c.outcome == "FALSE_EXIT"
        ],
        key=lambda c: (
            c.hold60
            if c.hold60 is not None
            else -999
        ),
        reverse=True,
    )

    print()
    print("=" * 72)
    print("REPRESENTATIVE GOOD EXITS")
    print("=" * 72)

    for case in good[:max_cases]:

        print()
        print(
            f"{case.symbol} "
            f"{case.direction} "
            f"{case.warning_time}"
        )

        print(
            f"  T0={case.t0} "
            f"({fmt_time_delta(case.minutes_to_t0)})"
        )

        print(
            f"  health={case.health} "
            f"reason={case.reason} "
            f"score={case.score:.2f}"
        )

        print(
            f"  adverse={case.adverse_count} "
            f"consecutive={case.consecutive_adverse} "
            f"net={fmt_pct(case.net_signed_pct)}"
        )

        print(
            f"  structure={case.structure_break} "
            f"severe={case.severe_balance} "
            f"persistent={case.persistent_adverse} "
            f"repeated={case.repeated_adverse}"
        )

        print(
            f"  HOLD15={fmt_pct(case.hold15)} "
            f"HOLD30={fmt_pct(case.hold30)} "
            f"HOLD60={fmt_pct(case.hold60)} "
            f"HOLD120={fmt_pct(case.hold120)}"
        )

    print()
    print("=" * 72)
    print("REPRESENTATIVE FALSE EXITS")
    print("=" * 72)

    for case in false[:max_cases]:

        print()
        print(
            f"{case.symbol} "
            f"{case.direction} "
            f"{case.warning_time}"
        )

        print(
            f"  T0={case.t0} "
            f"({fmt_time_delta(case.minutes_to_t0)})"
        )

        print(
            f"  health={case.health} "
            f"reason={case.reason} "
            f"score={case.score:.2f}"
        )

        print(
            f"  adverse={case.adverse_count} "
            f"consecutive={case.consecutive_adverse} "
            f"net={fmt_pct(case.net_signed_pct)}"
        )

        print(
            f"  structure={case.structure_break} "
            f"severe={case.severe_balance} "
            f"persistent={case.persistent_adverse} "
            f"repeated={case.repeated_adverse}"
        )

        print(
            f"  HOLD15={fmt_pct(case.hold15)} "
            f"HOLD30={fmt_pct(case.hold30)} "
            f"HOLD60={fmt_pct(case.hold60)} "
            f"HOLD120={fmt_pct(case.hold120)}"
        )


# ============================================================
# GOOD VS FALSE DIRECT DIFFERENCE
# ============================================================

def print_direct_difference(
    cases: Sequence[WarningCase],
) -> None:

    good = valid_cases(
        [
            c for c in cases
            if c.outcome == "GOOD_EXIT"
        ]
    )

    false = valid_cases(
        [
            c for c in cases
            if c.outcome == "FALSE_EXIT"
        ]
    )

    print()
    print("=" * 72)
    print("GOOD vs FALSE DIRECT DIFFERENCES")
    print("=" * 72)

    if not good or not false:
        print("Insufficient GOOD/FALSE cases.")
        return

    features = [
        (
            "score",
            lambda c: c.score,
        ),
        (
            "adverse_count",
            lambda c: c.adverse_count,
        ),
        (
            "consecutive_adverse",
            lambda c: c.consecutive_adverse,
        ),
        (
            "net_signed",
            lambda c: c.net_signed_pct,
        ),
        (
            "minutes_to_t0",
            lambda c: c.minutes_to_t0,
        ),
    ]

    print()
    print(
        f"{'FEATURE':30s}"
        f"{'GOOD AVG':>14s}"
        f"{'FALSE AVG':>14s}"
        f"{'GOOD-FALSE':>14s}"
    )

    print("-" * 72)

    for name, fn in features:

        g = mean_or_zero(
            [
                fn(c)
                for c in good
            ]
        )

        f = mean_or_zero(
            [
                fn(c)
                for c in false
            ]
        )

        print(
            f"{name:30s}"
            f"{g:14.3f}"
            f"{f:14.3f}"
            f"{g-f:14.3f}"
        )


# ============================================================
# DIRECTION × REASON
# ============================================================

def print_direction_reason_matrix(
    cases: Sequence[WarningCase],
) -> None:

    print()
    print("=" * 72)
    print("DIRECTION × WARNING REASON")
    print("=" * 72)

    directions = [
        ("LONG->SHORT", "LONG"),
        ("SHORT->LONG", "SHORT"),
    ]

    reasons = sorted(
        set(
            c.reason
            for c in cases
        )
    )

    for direction_name, direction in directions:

        print()
        print(direction_name)

        print(
            f"{'REASON':28s}"
            f"{'N':>7s}"
            f"{'GOOD%':>10s}"
            f"{'FALSE%':>10s}"
        )

        print("-" * 60)

        for reason in reasons:

            group = [
                c for c in cases
                if (
                    c.direction == direction
                    and c.reason == reason
                )
            ]

            valid = valid_cases(group)

            if not valid:
                continue

            counts = outcome_counts(valid)

            total = len(valid)

            good_pct = (
                100.0
                * counts["GOOD_EXIT"]
                / total
            )

            false_pct = (
                100.0
                * counts["FALSE_EXIT"]
                / total
            )

            print(
                f"{reason:28s}"
                f"{total:7d}"
                f"{good_pct:9.1f}%"
                f"{false_pct:9.1f}%"
            )


# ============================================================
# DATA QUALITY
# ============================================================

def print_data_quality(
    cases: Sequence[WarningCase],
    transitions_total: int,
    usable_windows: int,
) -> None:

    print()
    print("=" * 72)
    print("DATA QUALITY")
    print("=" * 72)

    print(
        f"KNOWN DIRECTIONAL TRANSITIONS: "
        f"{transitions_total}"
    )

    print(
        f"USABLE TRANSITION WINDOWS: "
        f"{usable_windows}"
    )

    print(
        f"WARNING CASES: "
        f"{len(cases)}"
    )

    print(
        f"VALID OUTCOME CASES: "
        f"{len(valid_cases(cases))}"
    )

    unknown = sum(
        1
        for c in cases
        if c.outcome == "UNKNOWN"
    )

    print(
        f"UNKNOWN / INCOMPLETE OUTCOMES: "
        f"{unknown}"
    )


# ============================================================
# RESEARCH INTERPRETATION
# ============================================================

def print_research_notes(
    cases: Sequence[WarningCase],
) -> None:

    valid = valid_cases(cases)

    if not valid:
        return

    counts = outcome_counts(valid)

    good = counts["GOOD_EXIT"]
    false = counts["FALSE_EXIT"]

    print()
    print("=" * 72)
    print("V5.6.12 ANALYSIS NOTES")
    print("=" * 72)

    print()
    print(
        "This experiment does NOT select a new trading threshold."
    )

    print(
        "It asks whether the existing causal warning features "
        "contain separation between continued trend damage and recovery."
    )

    if good > false:
        print()
        print(
            "GOOD_EXIT cases outnumber FALSE_EXIT cases."
        )

    elif false > good:
        print()
        print(
            "FALSE_EXIT cases outnumber GOOD_EXIT cases."
        )

    else:
        print()
        print(
            "GOOD_EXIT and FALSE_EXIT counts are equal."
        )

    reasons = Counter(
        c.reason
        for c in valid
    )

    if reasons:

        print()
        print(
            "Most common warning reasons:"
        )

        for reason, count in reasons.most_common():
            print(
                f"  {reason}: {count}"
            )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "A GOOD/FALSE classification is based on HOLD-60 "
        "after the warning. It is an evaluation label, not "
        "information available to the detector."
    )

    print(
        "Therefore the future is used only for scoring."
    )

    print()
    print(
        "NEXT DECISION SHOULD COME FROM THE DATA."
    )

    print(
        "Do not change the live engine from this report alone."
    )


# ============================================================
# MAIN
# ============================================================

def analyze_symbol(
    symbol: str,
) -> Tuple[
    List[WarningCase],
    int,
    int,
]:

    print()
    print(
        f"Loading {symbol}..."
    )

    rows30_raw = load_rows(
        symbol,
        "30m",
    )

    rows5_raw = load_rows(
        symbol,
        "5m",
    )

    rows30 = completed_30m_rows(
        rows30_raw
    )

    rows5 = completed_5m_rows(
        rows5_raw
    )

    if not rows30 or not rows5:

        print(
            f"{symbol}: insufficient data."
        )

        return [], 0, 0

    states30 = build_30m_states(
        rows30
    )

    transitions = find_directional_transitions(
        rows30,
        states30,
    )

    cases = []

    usable = 0

    for t0, old_state, new_state in transitions:

        direction = old_state

        # Need enough historical 5m data.
        if t0 - rows5[0]["_close_time"] < timedelta(
            minutes=MIN_HISTORY_MINUTES
        ):
            continue

        # Need future coverage for evaluation.
        if rows5[-1]["_close_time"] < (
            t0 + timedelta(
                minutes=EVAL_MINUTES
            )
        ):
            continue

        usable += 1

        transition_cases = build_cases_for_transition(
            symbol,
            rows5,
            t0,
            direction,
        )

        cases.extend(
            transition_cases
        )

    print(
        f"{symbol}: "
        f"transitions={len(transitions)} "
        f"usable={usable} "
        f"warnings={len(cases)}"
    )

    return cases, len(transitions), usable


def main():

    parser = argparse.ArgumentParser(
        description=(
            "V5.6.12 GOOD-vs-FALSE warning analysis"
        )
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
    )

    args = parser.parse_args()

    all_cases = []

    total_transitions = 0
    total_usable = 0

    print()
    print("=" * 72)
    print("V5.6.12 GOOD-vs-FALSE WARNING ANALYSIS")
    print("=" * 72)

    print()
    print(
        "RESEARCH ONLY — NO ENGINE / ORDER / DB CHANGES"
    )

    print()
    print(
        f"Symbols: {', '.join(args.symbols)}"
    )

    for symbol in args.symbols:

        try:

            cases, transitions, usable = (
                analyze_symbol(symbol)
            )

            all_cases.extend(cases)

            total_transitions += transitions
            total_usable += usable

        except Exception as exc:

            print()
            print(
                f"{symbol}: ERROR: {exc}"
            )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("V5.6.12 GOOD-vs-FALSE ANALYSIS SUMMARY")
    print("=" * 72)

    print(
        f"KNOWN DIRECTIONAL TRANSITIONS: "
        f"{total_transitions}"
    )

    print(
        f"USABLE COMPLETE WINDOWS: "
        f"{total_usable}"
    )

    print(
        f"WARNING EPISODES: "
        f"{len(all_cases)}"
    )

    # --------------------------------------------------------
    # OVERALL
    # --------------------------------------------------------

    print_outcome_summary(
        "ALL WARNING EPISODES",
        all_cases,
    )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    long_short = [
        c for c in all_cases
        if c.direction == "LONG"
    ]

    short_long = [
        c for c in all_cases
        if c.direction == "SHORT"
    ]

    print_outcome_summary(
        "LONG -> SHORT",
        long_short,
    )

    print_outcome_summary(
        "SHORT -> LONG",
        short_long,
    )

    # --------------------------------------------------------
    # FEATURE COMPARISON
    # --------------------------------------------------------

    print_feature_comparison(
        all_cases
    )

    print_boolean_comparison(
        all_cases
    )

    # --------------------------------------------------------
    # REASON
    # --------------------------------------------------------

    print_reason_analysis(
        all_cases
    )

    # --------------------------------------------------------
    # HEALTH
    # --------------------------------------------------------

    print_health_analysis(
        all_cases
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    print_score_analysis(
        all_cases
    )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    print_direction_analysis(
        all_cases
    )

    # --------------------------------------------------------
    # COMBINATIONS
    # --------------------------------------------------------

    print_combined_analysis(
        all_cases
    )

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    print_timing_buckets(
        all_cases
    )

    # --------------------------------------------------------
    # SYMBOL
    # --------------------------------------------------------

    print_symbol_analysis(
        all_cases
    )

    # --------------------------------------------------------
    # DIRECTION × REASON
    # --------------------------------------------------------

    print_direction_reason_matrix(
        all_cases
    )

    # --------------------------------------------------------
    # DIRECT DIFFERENCE
    # --------------------------------------------------------

    print_direct_difference(
        all_cases
    )

    # --------------------------------------------------------
    # REPRESENTATIVE CASES
    # --------------------------------------------------------

    print_representative_cases(
        all_cases,
        max_cases=12,
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    print_data_quality(
        all_cases,
        total_transitions,
        total_usable,
    )

    # --------------------------------------------------------
    # NOTES
    # --------------------------------------------------------

    print_research_notes(
        all_cases
    )

    print()
    print("=" * 72)
    print("V5.6.12 ANALYSIS COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()