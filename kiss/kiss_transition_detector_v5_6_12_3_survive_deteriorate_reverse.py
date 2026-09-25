# /kiss_transition_detector_v5_6_12_3_survive_deteriorate_reverse.py

#!/usr/bin/env python3
"""
V5.6.12.3 — SURVIVE → DETERIORATE → REVERSE

Research-only transition study.

Purpose
-------
Continue V5.6.12.2 by separating three different things after the
FIRST WARNING:

    SURVIVE
        The original trend comes under pressure but recovers.

    DETERIORATE
        The original trend remains damaged / continues against it.

    REVERSE
        The opposite market structure actually develops.

IMPORTANT
---------
DETERIORATE is NOT the same thing as REVERSE.

A trend can deteriorate and then recover.
A trend can deteriorate without producing a clean opposite trend.
A warning therefore is information, NOT automatically an EXIT.

This script is intentionally isolated from the live KISS engine.

It:
    - reads candles only
    - writes nothing
    - places no orders
    - does not modify KISS
    - uses completed 5m candles only
    - uses no RSI
    - uses no ML
    - uses no future data for the warning decision
    - assigns at most one warning episode to each known transition

Architecture
------------
    KISS transition
          |
          v
    FIRST WARNING
          |
          v
    +-------------------------+
    | 15 / 30 / 45 / 60 min  |
    | causal path observation |
    +-------------------------+
          |
          +----> SURVIVE
          |
          +----> DETERIORATE
          |
          +----> UNRESOLVED
          |
          v
    independent opposite-structure test
          |
          +----> REVERSE
          |
          +----> NO_REVERSE

The future after each checkpoint is used only to measure the outcome.

Run:
    python kiss_transition_detector_v5_6_12_3_survive_deteriorate_reverse.py \
        --symbols NVDA AAPL MSFT AMZN TSLA SPY QQQ

"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Dict, List, Optional, Sequence, Tuple

from db import get_db_connection


# ============================================================
# CONFIGURATION
# ============================================================

TREND_WINDOW = 20
TREND_BAND = 0.002

FIVE_MINUTES = 5

LOOKBACK_MINUTES = 480
POST_MINUTES = 120

CHECKPOINTS = (15, 30, 45, 60)

OUTCOME_MINUTES = 60

EPISODE_GAP_MINUTES = 15

# Minimum return used only to classify future outcome.
# This is NOT an entry/exit threshold.
OUTCOME_THRESHOLD_PCT = 0.10

# Structure settings.
STRUCTURE_LOOKBACK_BARS = 6
STRUCTURE_BREAK_PCT = 0.10

# Health settings.
SEVERE_ADVERSE_SHARE = 0.65
SEVERE_ADVERSE_MOVE = 0.40

# Recovery threshold.
RECOVERY_MIN_PCT = 0.10

# Deterioration threshold.
DETERIORATION_MIN_PCT = 0.20


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Transition:
    symbol: str
    old_state: str
    new_state: str
    timestamp: datetime
    price: float


@dataclass
class WarningObservation:
    symbol: str
    direction: str
    timestamp: datetime

    score: float
    adverse_count: int
    consecutive_adverse: int
    net_signed_move_pct: float

    structure_break: bool
    severe_balance: bool
    persistent_adverse: bool
    repeated_adverse: bool

    health: str


@dataclass
class WarningEpisode:
    symbol: str
    direction: str
    warning_time: datetime
    transition_time: datetime
    transition_new_state: str

    warning_score: float
    warning_health: str
    adverse_count: int
    consecutive_adverse: int
    net_signed_move_pct: float

    structure_break: bool
    severe_balance: bool
    persistent_adverse: bool
    repeated_adverse: bool


@dataclass
class CheckpointResult:
    episode: WarningEpisode
    minutes_after_warning: int

    state: str

    return_from_warning_pct: Optional[float]
    min_return_pct: Optional[float]
    max_return_pct: Optional[float]

    opposite_structure: bool
    opposite_structure_time: Optional[datetime]

    old_trend_recovered: bool
    old_trend_deteriorated: bool

    future_return_60_pct: Optional[float]
    future_mfe_60_pct: Optional[float]
    future_mae_60_pct: Optional[float]
    future_outcome: str


# ============================================================
# FORMATTING
# ============================================================

def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.3f}%"


def fmt_num(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


# ============================================================
# DATABASE
# ============================================================

def load_rows(symbol: str, timeframe: str) -> List[Candle]:
    """
    db.py returns:
        conn, cursor
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

        rows = cur.fetchall()

        result: List[Candle] = []

        for row in rows:
            ts = row["timestamp"]

            if not isinstance(ts, datetime):
                ts = datetime.fromisoformat(str(ts))

            result.append(
                Candle(
                    timestamp=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0.0),
                )
            )

        return result

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
# KISS 30M STATE
# ============================================================

def get_market_state(
    closes: Sequence[float],
    idx: int,
) -> str:

    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    ma = sum(
        closes[idx - TREND_WINDOW:idx]
    ) / TREND_WINDOW

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def build_transitions(
    symbol: str,
    rows30: Sequence[Candle],
) -> List[Transition]:

    closes = [r.close for r in rows30]

    states: List[str] = []

    for i in range(len(rows30)):
        states.append(
            get_market_state(closes, i)
        )

    transitions: List[Transition] = []

    previous = states[0] if states else "FLAT"

    for i in range(1, len(rows30)):

        current = states[i]

        if current == previous:
            continue

        if previous in ("LONG", "SHORT") and current in ("LONG", "SHORT"):
            transitions.append(
                Transition(
                    symbol=symbol,
                    old_state=previous,
                    new_state=current,
                    timestamp=rows30[i].timestamp + timedelta(minutes=30),
                    price=rows30[i].close,
                )
            )

        elif previous in ("LONG", "SHORT") and current == "FLAT":
            transitions.append(
                Transition(
                    symbol=symbol,
                    old_state=previous,
                    new_state=current,
                    timestamp=rows30[i].timestamp + timedelta(minutes=30),
                    price=rows30[i].close,
                )
            )

        elif previous == "FLAT" and current in ("LONG", "SHORT"):
            transitions.append(
                Transition(
                    symbol=symbol,
                    old_state=previous,
                    new_state=current,
                    timestamp=rows30[i].timestamp + timedelta(minutes=30),
                    price=rows30[i].close,
                )
            )

        previous = current

    return [
        t
        for t in transitions
        if t.old_state in ("LONG", "SHORT")
        and t.new_state in ("LONG", "SHORT")
    ]


# ============================================================
# TIME INDEX HELPERS
# ============================================================

def exact_5m_close_index(
    rows5: Sequence[Candle],
    target: datetime,
) -> Optional[int]:

    for i, row in enumerate(rows5):

        close_at = row.timestamp + timedelta(minutes=5)

        if close_at == target:
            return i

    return None


def nearest_completed_5m_index(
    rows5: Sequence[Candle],
    target: datetime,
    tolerance_minutes: int = 0,
) -> Optional[int]:

    best = None
    best_delta = None

    for i, row in enumerate(rows5):

        close_at = row.timestamp + timedelta(minutes=5)

        delta = abs(
            (close_at - target).total_seconds()
        )

        if delta <= tolerance_minutes * 60:

            if best_delta is None or delta < best_delta:
                best = i
                best_delta = delta

    return best


def build_close_time_map(
    rows5: Sequence[Candle],
) -> Dict[datetime, int]:

    result: Dict[datetime, int] = {}

    for i, row in enumerate(rows5):
        close_at = row.timestamp + timedelta(minutes=5)
        result[close_at] = i

    return result


# ============================================================
# CAUSAL HEALTH FEATURES
# ============================================================

def signed_return_for_direction(
    direction: str,
    start: float,
    end: float,
) -> float:

    raw = pct_change(start, end)

    if direction == "LONG":
        return raw

    return -raw


def recent_adverse_statistics(
    rows5: Sequence[Candle],
    idx: int,
    direction: str,
    lookback_minutes: int = LOOKBACK_MINUTES,
) -> Tuple[int, int, float]:

    if idx < 0 or idx >= len(rows5):
        return 0, 0, 0.0

    bars = max(
        1,
        lookback_minutes // FIVE_MINUTES,
    )

    start = max(0, idx - bars + 1)

    adverse_count = 0
    consecutive = 0
    max_consecutive = 0

    net_signed = 0.0

    for j in range(start, idx + 1):

        row = rows5[j]

        move = pct_change(
            row.open,
            row.close,
        )

        signed = (
            move
            if direction == "LONG"
            else -move
        )

        net_signed += signed

        if signed < 0:
            adverse_count += 1
            consecutive += 1
            max_consecutive = max(
                max_consecutive,
                consecutive,
            )
        else:
            consecutive = 0

    return (
        adverse_count,
        max_consecutive,
        net_signed,
    )


def structural_break_for_direction(
    rows5: Sequence[Candle],
    idx: int,
    direction: str,
) -> bool:

    if idx < STRUCTURE_LOOKBACK_BARS:
        return False

    current = rows5[idx]

    previous = rows5[
        idx - STRUCTURE_LOOKBACK_BARS:idx
    ]

    if direction == "LONG":

        prior_low = min(
            r.low for r in previous
        )

        return (
            current.close
            < prior_low * (
                1.0 - STRUCTURE_BREAK_PCT / 100.0
            )
        )

    prior_high = max(
        r.high for r in previous
    )

    return (
        current.close
        > prior_high * (
            1.0 + STRUCTURE_BREAK_PCT / 100.0
        )
    )


def severe_balance_for_direction(
    rows5: Sequence[Candle],
    idx: int,
    direction: str,
) -> bool:

    bars = 6

    if idx < bars - 1:
        return False

    recent = rows5[
        idx - bars + 1:idx + 1
    ]

    adverse = 0
    adverse_magnitude = 0.0

    for row in recent:

        move = pct_change(
            row.open,
            row.close,
        )

        signed = (
            move
            if direction == "LONG"
            else -move
        )

        if signed < 0:
            adverse += 1
            adverse_magnitude += abs(signed)

    share = adverse / len(recent)

    return (
        share >= SEVERE_ADVERSE_SHARE
        and adverse_magnitude >= SEVERE_ADVERSE_MOVE
    )


def calculate_warning_features(
    rows5: Sequence[Candle],
    idx: int,
    direction: str,
) -> Tuple[
    int,
    int,
    float,
    bool,
    bool,
    bool,
    bool,
    float,
]:

    adverse_count, consecutive, net_signed = (
        recent_adverse_statistics(
            rows5,
            idx,
            direction,
        )
    )

    structure_break = structural_break_for_direction(
        rows5,
        idx,
        direction,
    )

    severe_balance = severe_balance_for_direction(
        rows5,
        idx,
        direction,
    )

    persistent_adverse = (
        consecutive >= 2
        or net_signed <= -0.20
    )

    repeated_adverse = (
        adverse_count >= 3
    )

    score = 0.0

    if structure_break:
        score += 3.0

    if persistent_adverse:
        score += 2.0

    if severe_balance:
        score += 1.0

    if repeated_adverse:
        score += 0.5

    # Cap the magnitude contribution.
    magnitude = min(
        1.0,
        abs(min(net_signed, 0.0)) / 1.0,
    )

    score += magnitude

    return (
        adverse_count,
        consecutive,
        net_signed,
        structure_break,
        severe_balance,
        persistent_adverse,
        repeated_adverse,
        score,
    )


def classify_health(
    score: float,
    net_signed: float,
    severe_balance: bool,
    structure_break: bool,
) -> str:

    if (
        severe_balance
        and structure_break
        and score >= 5.0
    ):
        return "CRITICAL"

    if (
        score >= 3.0
        or net_signed <= -0.20
    ):
        return "DETERIORATING"

    if (
        score >= 1.0
        or net_signed < -0.05
    ):
        return "STRESSED"

    return "HEALTHY"


def build_warning_observations(
    rows5: Sequence[Candle],
    direction: str,
) -> List[WarningObservation]:

    observations: List[WarningObservation] = []

    for i in range(len(rows5)):

        (
            adverse_count,
            consecutive,
            net_signed,
            structure_break,
            severe_balance,
            persistent_adverse,
            repeated_adverse,
            score,
        ) = calculate_warning_features(
            rows5,
            i,
            direction,
        )

        health = classify_health(
            score,
            net_signed,
            severe_balance,
            structure_break,
        )

        # Only actual warning states.
        if health not in (
            "STRESSED",
            "DETERIORATING",
            "CRITICAL",
        ):
            continue

        observations.append(
            WarningObservation(
                symbol="",
                direction=direction,
                timestamp=(
                    rows5[i].timestamp
                    + timedelta(minutes=5)
                ),
                score=score,
                adverse_count=adverse_count,
                consecutive_adverse=consecutive,
                net_signed_move_pct=net_signed,
                structure_break=structure_break,
                severe_balance=severe_balance,
                persistent_adverse=persistent_adverse,
                repeated_adverse=repeated_adverse,
                health=health,
            )
        )

    return observations


# ============================================================
# WARNING EPISODES
# ============================================================

def cluster_warning_observations(
    observations: Sequence[WarningObservation],
) -> List[WarningObservation]:

    if not observations:
        return []

    ordered = sorted(
        observations,
        key=lambda x: x.timestamp,
    )

    episodes: List[WarningObservation] = []

    current = ordered[0]

    for obs in ordered[1:]:

        gap = (
            obs.timestamp
            - current.timestamp
        ).total_seconds() / 60.0

        if gap <= EPISODE_GAP_MINUTES:

            # Keep the earliest warning.
            # We deliberately do NOT replace it with
            # the strongest warning.
            continue

        episodes.append(current)
        current = obs

    episodes.append(current)

    return episodes


def assign_one_warning_per_transition(
    transitions: Sequence[Transition],
    warning_episodes: Sequence[WarningObservation],
) -> Tuple[
    List[WarningEpisode],
    int,
]:

    candidates: List[
        Tuple[float, Transition, WarningObservation]
    ] = []

    for transition in transitions:

        for warning in warning_episodes:

            if warning.direction != transition.old_state:
                continue

            if warning.timestamp >= transition.timestamp:
                continue

            lead = (
                transition.timestamp
                - warning.timestamp
            ).total_seconds() / 60.0

            if lead > LOOKBACK_MINUTES:
                continue

            if lead <= 0:
                continue

            candidates.append(
                (
                    lead,
                    transition,
                    warning,
                )
            )

    # Closest warning to each transition first.
    candidates.sort(
        key=lambda x: (
            x[1].symbol,
            x[1].timestamp,
            x[0],
        )
    )

    used_transition_keys = set()
    used_warning_keys = set()

    assignments: List[WarningEpisode] = []

    for lead, transition, warning in candidates:

        transition_key = (
            transition.symbol,
            transition.timestamp,
            transition.old_state,
            transition.new_state,
        )

        warning_key = (
            warning.symbol,
            warning.timestamp,
            warning.direction,
        )

        if transition_key in used_transition_keys:
            continue

        if warning_key in used_warning_keys:
            continue

        used_transition_keys.add(
            transition_key
        )

        used_warning_keys.add(
            warning_key
        )

        assignments.append(
            WarningEpisode(
                symbol=transition.symbol,
                direction=transition.old_state,
                warning_time=warning.timestamp,
                transition_time=transition.timestamp,
                transition_new_state=transition.new_state,
                warning_score=warning.score,
                warning_health=warning.health,
                adverse_count=warning.adverse_count,
                consecutive_adverse=warning.consecutive_adverse,
                net_signed_move_pct=warning.net_signed_move_pct,
                structure_break=warning.structure_break,
                severe_balance=warning.severe_balance,
                persistent_adverse=warning.persistent_adverse,
                repeated_adverse=warning.repeated_adverse,
            )
        )

    assignments.sort(
        key=lambda x: (
            x.symbol,
            x.warning_time,
        )
    )

    return assignments, len(used_transition_keys)


# ============================================================
# POST-WARNING PATH
# ============================================================

def get_rows_after_time(
    rows5: Sequence[Candle],
    start_time: datetime,
    end_time: datetime,
) -> List[Candle]:

    result = []

    for row in rows5:

        close_at = row.timestamp + timedelta(
            minutes=5
        )

        if (
            close_at > start_time
            and close_at <= end_time
        ):
            result.append(row)

    return result


def path_returns(
    rows5: Sequence[Candle],
    warning_time: datetime,
    checkpoint_time: datetime,
    direction: str,
) -> Tuple[
    Optional[float],
    Optional[float],
    Optional[float],
]:

    warning_idx = exact_5m_close_index(
        rows5,
        warning_time,
    )

    checkpoint_idx = exact_5m_close_index(
        rows5,
        checkpoint_time,
    )

    if warning_idx is None:
        return None, None, None

    if checkpoint_idx is None:
        return None, None, None

    if checkpoint_idx <= warning_idx:
        return None, None, None

    base = rows5[warning_idx].close

    returns = []

    for i in range(
        warning_idx + 1,
        checkpoint_idx + 1,
    ):

        r = signed_return_for_direction(
            direction,
            base,
            rows5[i].close,
        )

        returns.append(r)

    if not returns:
        return None, None, None

    return (
        returns[-1],
        min(returns),
        max(returns),
    )


# ============================================================
# RECOVERY / DETERIORATION CLASSIFICATION
# ============================================================

def classify_path_state(
    return_from_warning: Optional[float],
    min_return: Optional[float],
    max_return: Optional[float],
    direction: str,
) -> str:

    if return_from_warning is None:
        return "UNRESOLVED"

    if min_return is None or max_return is None:
        return "UNRESOLVED"

    # Strong recovery:
    # price has recovered positively from warning.
    if (
        return_from_warning >= RECOVERY_MIN_PCT
        and max_return >= RECOVERY_MIN_PCT
    ):
        return "SURVIVE"

    # Clear continued damage:
    # old direction has suffered meaningful adverse move.
    if (
        min_return <= -DETERIORATION_MIN_PCT
        and return_from_warning <= -RECOVERY_MIN_PCT
    ):
        return "DETERIORATE"

    # If price is still below the warning but not
    # sufficiently damaged, keep it unresolved.
    return "UNRESOLVED"


# ============================================================
# OPPOSITE STRUCTURE
# ============================================================

def detect_opposite_structure(
    rows5: Sequence[Candle],
    warning_time: datetime,
    checkpoint_time: datetime,
    old_direction: str,
) -> Tuple[
    bool,
    Optional[datetime],
]:

    start_idx = exact_5m_close_index(
        rows5,
        warning_time,
    )

    end_idx = exact_5m_close_index(
        rows5,
        checkpoint_time,
    )

    if start_idx is None or end_idx is None:
        return False, None

    if end_idx <= start_idx + 2:
        return False, None

    # We require a causal sequence:
    #
    # OLD LONG:
    #   adverse break
    #   followed by a lower close
    #
    # OLD SHORT:
    #   adverse break
    #   followed by a higher close
    #
    # This is intentionally simple.
    # V5.6.12.3 is measuring the concept rather than
    # pretending this is already the final transition model.

    for i in range(
        start_idx + 2,
        end_idx + 1,
    ):

        current = rows5[i]

        prior = rows5[
            max(start_idx, i - 3):i
        ]

        if len(prior) < 2:
            continue

        if old_direction == "LONG":

            prior_low = min(
                r.low for r in prior
            )

            previous_close = rows5[i - 1].close

            if (
                current.close < prior_low
                and current.close < previous_close
            ):
                return True, (
                    current.timestamp
                    + timedelta(minutes=5)
                )

        else:

            prior_high = max(
                r.high for r in prior
            )

            previous_close = rows5[i - 1].close

            if (
                current.close > prior_high
                and current.close > previous_close
            ):
                return True, (
                    current.timestamp
                    + timedelta(minutes=5)
                )

    return False, None


# ============================================================
# FUTURE OUTCOME
# ============================================================

def future_outcome(
    rows5: Sequence[Candle],
    checkpoint_time: datetime,
    direction: str,
) -> Tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    str,
]:

    start_idx = exact_5m_close_index(
        rows5,
        checkpoint_time,
    )

    if start_idx is None:
        return None, None, None, "UNKNOWN"

    end_time = (
        checkpoint_time
        + timedelta(minutes=OUTCOME_MINUTES)
    )

    end_idx = exact_5m_close_index(
        rows5,
        end_time,
    )

    if end_idx is None:
        return None, None, None, "UNKNOWN"

    if end_idx <= start_idx:
        return None, None, None, "UNKNOWN"

    base = rows5[start_idx].close

    returns: List[float] = []

    for i in range(
        start_idx + 1,
        end_idx + 1,
    ):

        signed = signed_return_for_direction(
            direction,
            base,
            rows5[i].close,
        )

        returns.append(signed)

    if not returns:
        return None, None, None, "UNKNOWN"

    final_return = returns[-1]

    mfe = max(returns)
    mae = min(returns)

    if final_return <= -OUTCOME_THRESHOLD_PCT:
        outcome = "GOOD"

    elif final_return >= OUTCOME_THRESHOLD_PCT:
        outcome = "FALSE"

    else:
        outcome = "NEUTRAL"

    return (
        final_return,
        mfe,
        mae,
        outcome,
    )


# ============================================================
# BUILD CHECKPOINT RESULTS
# ============================================================

def evaluate_episode(
    episode: WarningEpisode,
    rows5: Sequence[Candle],
) -> List[CheckpointResult]:

    results: List[CheckpointResult] = []

    for minutes in CHECKPOINTS:

        checkpoint_time = (
            episode.warning_time
            + timedelta(minutes=minutes)
        )

        (
            ret,
            min_ret,
            max_ret,
        ) = path_returns(
            rows5,
            episode.warning_time,
            checkpoint_time,
            episode.direction,
        )

        state = classify_path_state(
            ret,
            min_ret,
            max_ret,
            episode.direction,
        )

        (
            opposite,
            opposite_time,
        ) = detect_opposite_structure(
            rows5,
            episode.warning_time,
            checkpoint_time,
            episode.direction,
        )

        (
            future_ret,
            future_mfe,
            future_mae,
            future_state,
        ) = future_outcome(
            rows5,
            checkpoint_time,
            episode.direction,
        )

        results.append(
            CheckpointResult(
                episode=episode,
                minutes_after_warning=minutes,
                state=state,
                return_from_warning_pct=ret,
                min_return_pct=min_ret,
                max_return_pct=max_ret,
                opposite_structure=opposite,
                opposite_structure_time=opposite_time,
                old_trend_recovered=(
                    state == "SURVIVE"
                ),
                old_trend_deteriorated=(
                    state == "DETERIORATE"
                ),
                future_return_60_pct=future_ret,
                future_mfe_60_pct=future_mfe,
                future_mae_60_pct=future_mae,
                future_outcome=future_state,
            )
        )

    return results


# ============================================================
# SUMMARY HELPERS
# ============================================================

def outcome_counts(
    results: Sequence[CheckpointResult],
) -> Tuple[int, int, int, int]:

    good = sum(
        1
        for r in results
        if r.future_outcome == "GOOD"
    )

    false = sum(
        1
        for r in results
        if r.future_outcome == "FALSE"
    )

    neutral = sum(
        1
        for r in results
        if r.future_outcome == "NEUTRAL"
    )

    unknown = sum(
        1
        for r in results
        if r.future_outcome == "UNKNOWN"
    )

    return good, false, neutral, unknown


def avg_future_return(
    results: Sequence[CheckpointResult],
) -> Optional[float]:

    values = [
        r.future_return_60_pct
        for r in results
        if r.future_return_60_pct is not None
    ]

    if not values:
        return None

    return mean(values)


def print_checkpoint_summary(
    all_results: Sequence[CheckpointResult],
) -> None:

    print()
    print("=" * 78)
    print("V5.6.12.3 CHECKPOINT SUMMARY")
    print("=" * 78)

    for minutes in CHECKPOINTS:

        group = [
            r
            for r in all_results
            if r.minutes_after_warning == minutes
        ]

        states = {
            "SURVIVE": sum(
                1 for r in group
                if r.state == "SURVIVE"
            ),
            "DETERIORATE": sum(
                1 for r in group
                if r.state == "DETERIORATE"
            ),
            "UNRESOLVED": sum(
                1 for r in group
                if r.state == "UNRESOLVED"
            ),
        }

        reverse = sum(
            1
            for r in group
            if r.opposite_structure
        )

        good, false, neutral, unknown = (
            outcome_counts(group)
        )

        valid = (
            good
            + false
            + neutral
        )

        avg = avg_future_return(group)

        print()
        print(f"+{minutes} MINUTES")
        print("-" * 78)
        print(
            f"N={len(group)} "
            f"VALID={valid} "
            f"UNKNOWN={unknown}"
        )

        print(
            f"SURVIVE={states['SURVIVE']} "
            f"DETERIORATE={states['DETERIORATE']} "
            f"UNRESOLVED={states['UNRESOLVED']}"
        )

        print(
            f"REVERSE STRUCTURE={reverse}"
        )

        if valid:
            print(
                f"GOOD={good} "
                f"({good / valid * 100:.1f}%) "
                f"FALSE={false} "
                f"({false / valid * 100:.1f}%) "
                f"NEUTRAL={neutral} "
                f"({neutral / valid * 100:.1f}%)"
            )
        else:
            print(
                "GOOD=0 FALSE=0 NEUTRAL=0"
            )

        print(
            f"AVG NEXT60={fmt_pct(avg)}"
        )


def print_state_outcomes(
    all_results: Sequence[CheckpointResult],
) -> None:

    print()
    print("=" * 78)
    print("STATE → FUTURE OUTCOME")
    print("=" * 78)

    for minutes in CHECKPOINTS:

        print()
        print(
            f"+{minutes} MINUTES"
        )
        print("-" * 78)

        group = [
            r
            for r in all_results
            if r.minutes_after_warning == minutes
        ]

        for state in (
            "SURVIVE",
            "DETERIORATE",
            "UNRESOLVED",
        ):

            subset = [
                r
                for r in group
                if r.state == state
            ]

            good, false, neutral, unknown = (
                outcome_counts(subset)
            )

            valid = (
                good
                + false
                + neutral
            )

            avg = avg_future_return(
                subset
            )

            if valid:
                good_pct = (
                    good / valid * 100.0
                )
                false_pct = (
                    false / valid * 100.0
                )
            else:
                good_pct = 0.0
                false_pct = 0.0

            print(
                f"{state:<12} "
                f"N={len(subset):<3} "
                f"GOOD={good:<3} "
                f"({good_pct:5.1f}%) "
                f"FALSE={false:<3} "
                f"({false_pct:5.1f}%) "
                f"NEUT={neutral:<3} "
                f"AVG60={fmt_pct(avg)}"
            )


def print_reverse_summary(
    all_results: Sequence[CheckpointResult],
) -> None:

    print()
    print("=" * 78)
    print("REVERSE STRUCTURE → FUTURE OUTCOME")
    print("=" * 78)

    for minutes in CHECKPOINTS:

        group = [
            r
            for r in all_results
            if r.minutes_after_warning == minutes
        ]

        print()
        print(
            f"+{minutes} MINUTES"
        )
        print("-" * 78)

        for label, subset in (
            (
                "REVERSE",
                [
                    r
                    for r in group
                    if r.opposite_structure
                ],
            ),
            (
                "NO_REVERSE",
                [
                    r
                    for r in group
                    if not r.opposite_structure
                ],
            ),
        ):

            good, false, neutral, unknown = (
                outcome_counts(subset)
            )

            valid = (
                good
                + false
                + neutral
            )

            avg = avg_future_return(
                subset
            )

            if valid:
                good_pct = (
                    good / valid * 100.0
                )
                false_pct = (
                    false / valid * 100.0
                )
            else:
                good_pct = 0.0
                false_pct = 0.0

            print(
                f"{label:<10} "
                f"N={len(subset):<3} "
                f"GOOD={good:<3} "
                f"({good_pct:5.1f}%) "
                f"FALSE={false:<3} "
                f"({false_pct:5.1f}%) "
                f"NEUT={neutral:<3} "
                f"AVG60={fmt_pct(avg)}"
            )


def print_direction_summary(
    all_results: Sequence[CheckpointResult],
) -> None:

    print()
    print("=" * 78)
    print("DIRECTION SUMMARY")
    print("=" * 78)

    for direction in (
        "LONG",
        "SHORT",
    ):

        group = [
            r
            for r in all_results
            if r.episode.direction == direction
            and r.minutes_after_warning == 30
        ]

        good, false, neutral, unknown = (
            outcome_counts(group)
        )

        valid = (
            good
            + false
            + neutral
        )

        avg = avg_future_return(group)

        print()

        if valid:
            print(
                f"{direction:<6} "
                f"N={len(group):<3} "
                f"GOOD={good} "
                f"({good / valid * 100:.1f}%) "
                f"FALSE={false} "
                f"({false / valid * 100:.1f}%) "
                f"NEUTRAL={neutral} "
                f"AVG60={fmt_pct(avg)}"
            )
        else:
            print(
                f"{direction:<6} N={len(group)} "
                f"NO VALID OUTCOMES"
            )


def print_feature_comparison(
    results: Sequence[CheckpointResult],
) -> None:

    print()
    print("=" * 78)
    print("WARNING FEATURE COMPARISON")
    print("=" * 78)

    for label, subset in (
        (
            "GOOD",
            [
                r for r in results
                if r.future_outcome == "GOOD"
            ],
        ),
        (
            "FALSE",
            [
                r for r in results
                if r.future_outcome == "FALSE"
            ],
        ),
        (
            "NEUTRAL",
            [
                r for r in results
                if r.future_outcome == "NEUTRAL"
            ],
        ),
    ):

        if not subset:
            print(
                f"{label:<8} N=0"
            )
            continue

        print(
            f"{label:<8} "
            f"N={len(subset):<3} "
            f"SCORE={mean(r.episode.warning_score for r in subset):.3f} "
            f"ADVERSE={mean(r.episode.adverse_count for r in subset):.3f} "
            f"CONSEC={mean(r.episode.consecutive_adverse for r in subset):.3f} "
            f"NET={mean(r.episode.net_signed_move_pct for r in subset):+.3f}% "
            f"LEAD={mean((r.episode.transition_time - r.episode.warning_time).total_seconds() / 60.0 for r in subset):.1f}m"
        )


def print_representative_cases(
    all_results: Sequence[CheckpointResult],
) -> None:

    print()
    print("=" * 78)
    print("REPRESENTATIVE CASES")
    print("=" * 78)

    # Use +30m because it is the central checkpoint.
    group = [
        r
        for r in all_results
        if r.minutes_after_warning == 30
        and r.future_outcome != "UNKNOWN"
    ]

    if not group:
        print("No representative cases available.")
        return

    categories = [
        (
            "SURVIVE + GOOD",
            lambda r:
                r.state == "SURVIVE"
                and r.future_outcome == "GOOD",
        ),
        (
            "SURVIVE + FALSE",
            lambda r:
                r.state == "SURVIVE"
                and r.future_outcome == "FALSE",
        ),
        (
            "DETERIORATE + GOOD",
            lambda r:
                r.state == "DETERIORATE"
                and r.future_outcome == "GOOD",
        ),
        (
            "DETERIORATE + FALSE",
            lambda r:
                r.state == "DETERIORATE"
                and r.future_outcome == "FALSE",
        ),
        (
            "REVERSE",
            lambda r:
                r.opposite_structure,
        ),
    ]

    printed = 0

    for label, predicate in categories:

        matches = [
            r
            for r in group
            if predicate(r)
        ]

        if not matches:
            continue

        # Prefer larger absolute future result.
        matches.sort(
            key=lambda r:
                abs(
                    r.future_return_60_pct
                    or 0.0
                ),
            reverse=True,
        )

        r = matches[0]
        e = r.episode

        print()
        print(label)
        print(
            f"  {e.symbol} "
            f"{e.direction} "
            f"warning={e.warning_time} "
            f"T0={e.transition_time}"
        )
        print(
            f"  health={e.warning_health} "
            f"score={e.warning_score:.2f} "
            f"lead="
            f"{(e.transition_time - e.warning_time).total_seconds() / 60.0:.1f}m"
        )
        print(
            f"  +30 state={r.state} "
            f"ret={fmt_pct(r.return_from_warning_pct)} "
            f"min={fmt_pct(r.min_return_pct)} "
            f"max={fmt_pct(r.max_return_pct)}"
        )
        print(
            f"  opposite_structure="
            f"{r.opposite_structure} "
            f"time={r.opposite_structure_time}"
        )
        print(
            f"  next60={fmt_pct(r.future_return_60_pct)} "
            f"MFE={fmt_pct(r.future_mfe_60_pct)} "
            f"MAE={fmt_pct(r.future_mae_60_pct)} "
            f"outcome={r.future_outcome}"
        )

        printed += 1

        if printed >= 12:
            break


def print_transition_uniqueness(
    assignments: Sequence[WarningEpisode],
) -> None:

    transition_keys = [
        (
            e.symbol,
            e.transition_time,
            e.direction,
            e.transition_new_state,
        )
        for e in assignments
    ]

    warning_keys = [
        (
            e.symbol,
            e.warning_time,
            e.direction,
        )
        for e in assignments
    ]

    duplicate_transitions = (
        len(transition_keys)
        - len(set(transition_keys))
    )

    duplicate_warnings = (
        len(warning_keys)
        - len(set(warning_keys))
    )

    print()
    print("=" * 78)
    print("UNIQUENESS AUDIT")
    print("=" * 78)

    print(
        f"ASSIGNMENTS={len(assignments)}"
    )

    print(
        f"UNIQUE TRANSITIONS="
        f"{len(set(transition_keys))}"
    )

    print(
        f"UNIQUE WARNING EPISODES="
        f"{len(set(warning_keys))}"
    )

    print(
        f"DUPLICATE TRANSITIONS="
        f"{duplicate_transitions}"
    )

    print(
        f"DUPLICATE EPISODES="
        f"{duplicate_warnings}"
    )


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_symbol(
    symbol: str,
) -> Tuple[
    List[Transition],
    List[WarningObservation],
    List[WarningEpisode],
    List[CheckpointResult],
]:

    print()
    print(
        f"Loading {symbol}..."
    )

    rows30 = load_rows(
        symbol,
        "30m",
    )

    rows5 = load_rows(
        symbol,
        "5m",
    )

    print(
        f"{symbol}: "
        f"30m={len(rows30)} "
        f"5m={len(rows5)}"
    )

    if len(rows30) < TREND_WINDOW + 2:
        return [], [], [], []

    if len(rows5) < 100:
        return [], [], [], []

    transitions = build_transitions(
        symbol,
        rows30,
    )

    warnings: List[WarningObservation] = []

    for direction in (
        "LONG",
        "SHORT",
    ):

        direction_warnings = (
            build_warning_observations(
                rows5,
                direction,
            )
        )

        for warning in direction_warnings:
            warning.symbol = symbol

        warnings.extend(
            direction_warnings
        )

    warnings.sort(
        key=lambda x: x.timestamp
    )

    warning_episodes = (
        cluster_warning_observations(
            warnings
        )
    )

    assignments, assigned_count = (
        assign_one_warning_per_transition(
            transitions,
            warning_episodes,
        )
    )

    all_results: List[CheckpointResult] = []

    for episode in assignments:

        results = evaluate_episode(
            episode,
            rows5,
        )

        all_results.extend(
            results
        )

    print(
        f"{symbol}: "
        f"transitions={len(transitions)} "
        f"warning_episodes={len(warning_episodes)} "
        f"assigned={assigned_count} "
        f"checkpoints={len(all_results)}"
    )

    return (
        transitions,
        warnings,
        assignments,
        all_results,
    )


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "V5.6.12.3 "
            "SURVIVE → DETERIORATE → REVERSE"
        )
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=[
            "NVDA",
            "AAPL",
            "MSFT",
            "AMZN",
            "TSLA",
            "SPY",
            "QQQ",
        ],
        help="Symbols to analyze",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    args = parse_args()

    print()
    print("=" * 78)
    print("V5.6.12.3 — SURVIVE → DETERIORATE → REVERSE")
    print("=" * 78)
    print()
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO DB WRITES")
    print("NO KISS ENGINE CHANGES")
    print("NO RSI")
    print("NO ML")
    print()
    print(
        "Architecture:"
    )
    print(
        "FIRST WARNING → SURVIVE / DETERIORATE / UNRESOLVED"
    )
    print(
        "                    ↓"
    )
    print(
        "              OPPOSITE STRUCTURE"
    )
    print(
        "                    ↓"
    )
    print(
        "                 REVERSE"
    )
    print()

    all_transitions: List[Transition] = []
    all_warnings: List[WarningObservation] = []
    all_assignments: List[WarningEpisode] = []
    all_results: List[CheckpointResult] = []

    per_symbol = {}

    for symbol in args.symbols:

        (
            transitions,
            warnings,
            assignments,
            results,
        ) = analyze_symbol(symbol)

        all_transitions.extend(
            transitions
        )

        all_warnings.extend(
            warnings
        )

        all_assignments.extend(
            assignments
        )

        all_results.extend(
            results
        )

        per_symbol[symbol] = {
            "transitions": len(transitions),
            "warnings": len(warnings),
            "episodes": len(
                cluster_warning_observations(
                    warnings
                )
            ),
            "assigned": len(assignments),
            "checkpoints": len(results),
        }

    # --------------------------------------------------------
    # GLOBAL
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("GLOBAL")
    print("=" * 78)

    print(
        f"KNOWN DIRECTIONAL TRANSITIONS: "
        f"{len(all_transitions)}"
    )

    all_warning_episodes = (
        cluster_warning_observations(
            all_warnings
        )
    )

    print(
        f"WARNING EPISODES: "
        f"{len(all_warning_episodes)}"
    )

    print(
        f"UNIQUELY ASSIGNED TRANSITIONS: "
        f"{len(all_assignments)}"
    )

    print(
        f"TRANSITIONS WITHOUT WARNING: "
        f"{max(0, len(all_transitions) - len(all_assignments))}"
    )

    print(
        f"CHECKPOINT OBSERVATIONS: "
        f"{len(all_results)}"
    )

    print_transition_uniqueness(
        all_assignments
    )

    # --------------------------------------------------------
    # CHECKPOINTS
    # --------------------------------------------------------

    print_checkpoint_summary(
        all_results
    )

    # --------------------------------------------------------
    # STATE OUTCOMES
    # --------------------------------------------------------

    print_state_outcomes(
        all_results
    )

    # --------------------------------------------------------
    # REVERSE
    # --------------------------------------------------------

    print_reverse_summary(
        all_results
    )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    print_direction_summary(
        all_results
    )

    # --------------------------------------------------------
    # FEATURE COMPARISON
    #
    # Use +30m as the main decision checkpoint.
    # --------------------------------------------------------

    thirty_results = [
        r
        for r in all_results
        if r.minutes_after_warning == 30
        and r.future_outcome != "UNKNOWN"
    ]

    print_feature_comparison(
        thirty_results
    )

    # --------------------------------------------------------
    # TRANSITION-LEVEL OUTCOME
    #
    # Count each assigned transition only once using +30m.
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("UNIQUE TRANSITION — +30m DECISION VIEW")
    print("=" * 78)

    good, false, neutral, unknown = (
        outcome_counts(thirty_results)
    )

    valid = (
        good
        + false
        + neutral
    )

    avg = avg_future_return(
        thirty_results
    )

    print(
        f"N={len(thirty_results)} "
        f"VALID={valid} "
        f"UNKNOWN={unknown}"
    )

    if valid:

        print(
            f"GOOD={good} "
            f"({good / valid * 100:.1f}%) "
            f"FALSE={false} "
            f"({false / valid * 100:.1f}%) "
            f"NEUTRAL={neutral} "
            f"({neutral / valid * 100:.1f}%)"
        )

    print(
        f"AVG NEXT60={fmt_pct(avg)}"
    )

    # --------------------------------------------------------
    # HOW OFTEN DETERIORATION BECOMES REVERSE
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("DETERIORATE → REVERSE")
    print("=" * 78)

    for minutes in CHECKPOINTS:

        group = [
            r
            for r in all_results
            if r.minutes_after_warning == minutes
            and r.state == "DETERIORATE"
        ]

        reverse_count = sum(
            1
            for r in group
            if r.opposite_structure
        )

        if group:

            print(
                f"+{minutes}m "
                f"DETERIORATE={len(group)} "
                f"REVERSE={reverse_count} "
                f"({reverse_count / len(group) * 100:.1f}%)"
            )

        else:

            print(
                f"+{minutes}m "
                f"DETERIORATE=0 "
                f"REVERSE=0"
            )

    # --------------------------------------------------------
    # SURVIVE → REVERSE
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("SURVIVE → REVERSE")
    print("=" * 78)

    for minutes in CHECKPOINTS:

        group = [
            r
            for r in all_results
            if r.minutes_after_warning == minutes
            and r.state == "SURVIVE"
        ]

        reverse_count = sum(
            1
            for r in group
            if r.opposite_structure
        )

        if group:

            print(
                f"+{minutes}m "
                f"SURVIVE={len(group)} "
                f"REVERSE={reverse_count} "
                f"({reverse_count / len(group) * 100:.1f}%)"
            )

        else:

            print(
                f"+{minutes}m "
                f"SURVIVE=0 "
                f"REVERSE=0"
            )

    # --------------------------------------------------------
    # REPRESENTATIVE CASES
    # --------------------------------------------------------

    print_representative_cases(
        all_results
    )

    # --------------------------------------------------------
    # SYMBOL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("SYMBOL SUMMARY")
    print("=" * 78)

    for symbol in args.symbols:

        data = per_symbol.get(
            symbol,
            {},
        )

        print(
            f"{symbol:<6} "
            f"30m={data.get('transitions', 0):<3} "
            f"warnings={data.get('warnings', 0):<4} "
            f"episodes={data.get('episodes', 0):<4} "
            f"assigned={data.get('assigned', 0):<3} "
            f"checkpoints={data.get('checkpoints', 0):<4}"
        )

    # --------------------------------------------------------
    # FINAL RESEARCH INTERPRETATION
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("V5.6.12.3 RESEARCH INTERPRETATION")
    print("=" * 78)

    print(
        "1. A WARNING is not automatically an EXIT."
    )

    print(
        "2. SURVIVE means the original trend recovered "
        "after the warning."
    )

    print(
        "3. DETERIORATE means the original trend remained "
        "meaningfully damaged."
    )

    print(
        "4. REVERSE requires separate opposite-direction "
        "structure evidence."
    )

    print(
        "5. DETERIORATE without REVERSE is an important "
        "case: the trade may be damaged without a confirmed "
        "trend reversal."
    )

    print(
        "6. SURVIVE without REVERSE shows why an aggressive "
        "warning-based exit can throw away a good trend."
    )

    print(
        "7. The important future architecture remains:"
    )

    print(
        "   WARNING → EVALUATE → SURVIVE / DETERIORATE"
    )

    print(
        "                       ↓"
    )

    print(
        "                  REVERSE?"
    )

    print(
        "                       ↓"
    )

    print(
        "                     EXIT"
    )

    print()
    print(
        "V5.6.12.3 COMPLETE."
    )
    print()


if __name__ == "__main__":
    main()