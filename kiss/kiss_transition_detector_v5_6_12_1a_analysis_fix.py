#!/usr/bin/env python3
"""
V5.6.12.1-A — First Warning / Transition Assignment Fix
=========================================================

PURPOSE
-------
Research-only analysis.

This version fixes the methodological problem discovered in V5.6.12
GOOD-vs-FALSE analysis:

    ONE transition
        ->
    ONE first warning episode
        ->
    ONE outcome

A warning episode is NOT allowed to be reused by multiple transition
windows.

IMPORTANT
---------
This file does NOT:
- change the trading engine
- place orders
- modify KISS execution
- modify RSI rules
- modify stop loss
- modify trailing
- write to the database
- use ML
- make trading decisions

It only studies whether the FIRST causal deterioration warning before
an actual 30m KISS state transition was useful or false.

TIMING
------
30m candle timestamp = candle START.
30m state becomes known at candle CLOSE (+30m).

5m candle timestamp = candle START.
5m features become known at candle CLOSE (+5m).

All warning calculations use only completed 5m candles available
at that time.

OUTCOME
-------
After the warning decision, we look forward 60 minutes.

For the old trend:
    GOOD    = holding the old direction became worse
    FALSE   = holding the old direction became better
    NEUTRAL = neither clearly dominated

The analysis is deliberately conservative.

TRANSITION
----------
The reference transition remains the existing KISS 30m state:

    20-bar moving average
    +/- 0.20% band

    LONG
    SHORT
    FLAT

Only directional transitions are studied:

    LONG -> SHORT
    SHORT -> LONG

WARNING
-------
The warning detector uses the V5.6.12 persistence-style health model:

    HEALTHY
        ->
    STRESSED
        ->
    DETERIORATING
        ->
    CRITICAL

The detector is causal and uses completed 5m candles.

IMPORTANT METHODOLOGICAL CHANGE
-------------------------------
V5.6.12 analysis could reuse the same warning for more than one
transition because transition windows overlapped.

Example of the bad behavior:

    warning A -----> T0 #1
           \--------> T0 #2

V5.6.12.1-A prevents this.

Assignment rule:

    1. Build ALL warning episodes globally.
    2. Cluster nearby warnings into one episode.
    3. Find directional 30m transitions.
    4. For every transition, choose ONE first warning episode
       inside its allowed pre-transition window.
    5. A warning episode can be assigned to ONLY ONE transition.
    6. Once assigned, it is unavailable to every other transition.
    7. If two transitions compete for the same warning, the warning
       is assigned to the nearest eligible transition in time.
    8. Recalculate GOOD/FALSE/NEUTRAL from these unique assignments.

This makes the population much closer to:

    transition -> first warning -> outcome

rather than:

    warning -> many transitions

USAGE
-----
    python kiss_transition_detector_v5_6_12_1a_analysis_fix.py

or:

    python kiss_transition_detector_v5_6_12_1a_analysis_fix.py \
        --symbols NVDA AAPL MSFT AMZN TSLA SPY QQQ

"""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from db import get_db_connection


# ============================================================
# CONFIGURATION
# ============================================================

TREND_WINDOW = 20
TREND_BAND = 0.002

RSI_PERIOD = 14

LOOKBACK_MINUTES = 480
POST_MINUTES = 120
OUTCOME_MINUTES = 60

# Warning episodes closer than this are considered the same episode.
EPISODE_GAP_MINUTES = 15

# A warning must occur before the official transition.
MIN_WARNING_LEAD_MINUTES = 0

# Maximum amount of time before the official transition in which
# a warning can be assigned to that transition.
MAX_WARNING_LEAD_MINUTES = 480

# Deterioration thresholds.
NET_MOVE_STRESSED = -0.05
NET_MOVE_DETERIORATING = -0.20

# A causal structure break uses recent 5m structure.
STRUCTURE_LOOKBACK_BARS = 3

# Outcome threshold.
# Returns smaller than this are treated as neutral.
OUTCOME_THRESHOLD_PCT = 0.10


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Transition:
    symbol: str
    timestamp: datetime
    old_state: str
    new_state: str
    direction: str
    index_30m: int


@dataclass
class WarningObservation:
    symbol: str
    timestamp: datetime
    old_direction: str
    health: str
    score: float
    adverse_count: int
    consecutive_adverse: int
    net_signed_move_pct: float
    structure_break: bool
    severe_balance: bool
    persistent_adverse: bool
    repeated_adverse: bool
    reason: str


@dataclass
class WarningEpisode:
    symbol: str
    first_timestamp: datetime
    last_timestamp: datetime
    observations: List[WarningObservation]

    @property
    def first(self) -> WarningObservation:
        return self.observations[0]


@dataclass
class Assignment:
    transition: Transition
    episode: WarningEpisode
    lead_minutes: float
    outcome: str
    hold_return_pct: Optional[float]
    min_return_pct: Optional[float]
    max_return_pct: Optional[float]


# ============================================================
# BASIC HELPERS
# ============================================================

def pct_change(start: float, end: float) -> Optional[float]:
    if start is None or end is None:
        return None
    if start == 0:
        return None
    return (end / start - 1.0) * 100.0


def safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def direction_sign(direction: str) -> int:
    if direction == "LONG":
        return 1
    if direction == "SHORT":
        return -1
    return 0


# ============================================================
# DATABASE
# ============================================================

def load_rows(symbol: str, timeframe: str) -> List[Candle]:
    """
    Correctly handles db.py where get_db_connection() returns:

        (connection, cursor)
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
                continue

            result.append(
                Candle(
                    timestamp=ts,
                    open=safe_float(row.get("open")),
                    high=safe_float(row.get("high")),
                    low=safe_float(row.get("low")),
                    close=safe_float(row.get("close")),
                    volume=safe_float(row.get("volume")),
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
# RSI
# ============================================================

def rsi_values(closes: Sequence[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(closes)

    if len(closes) <= period:
        return result

    gains: List[float] = []
    losses: List[float] = []

    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]

        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-delta)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]

        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)

        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


# ============================================================
# KISS 30M STATE
# ============================================================

def get_market_state(closes: Sequence[float], idx: int) -> str:
    """
    Existing KISS state definition.

    The state at idx is based on the previous 20 completed 30m closes.
    """

    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    window = closes[idx - TREND_WINDOW:idx]

    if not window:
        return "FLAT"

    ma = sum(window) / len(window)

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def build_directional_transitions(
    symbol: str,
    rows_30m: Sequence[Candle],
) -> List[Transition]:

    if len(rows_30m) <= TREND_WINDOW:
        return []

    closes = [r.close for r in rows_30m]

    states = [
        get_market_state(closes, i)
        for i in range(len(rows_30m))
    ]

    transitions: List[Transition] = []

    for i in range(1, len(states)):
        old_state = states[i - 1]
        new_state = states[i]

        if old_state == "LONG" and new_state == "SHORT":
            transitions.append(
                Transition(
                    symbol=symbol,
                    timestamp=rows_30m[i].timestamp + timedelta(minutes=30),
                    old_state=old_state,
                    new_state=new_state,
                    direction="LONG",
                    index_30m=i,
                )
            )

        elif old_state == "SHORT" and new_state == "LONG":
            transitions.append(
                Transition(
                    symbol=symbol,
                    timestamp=rows_30m[i].timestamp + timedelta(minutes=30),
                    old_state=old_state,
                    new_state=new_state,
                    direction="SHORT",
                    index_30m=i,
                )
            )

    return transitions


# ============================================================
# 5M TIMING
# ============================================================

def candle_close_time(row: Candle) -> datetime:
    return row.timestamp + timedelta(minutes=5)


def build_close_map(rows: Sequence[Candle]) -> Dict[datetime, int]:
    result: Dict[datetime, int] = {}

    for i, row in enumerate(rows):
        result[candle_close_time(row)] = i

    return result


# ============================================================
# CAUSAL STRUCTURE
# ============================================================

def structure_break_for_direction(
    rows: Sequence[Candle],
    idx: int,
    direction: str,
) -> bool:

    if idx < STRUCTURE_LOOKBACK_BARS:
        return False

    current = rows[idx]

    previous = rows[
        idx - STRUCTURE_LOOKBACK_BARS:idx
    ]

    if len(previous) < STRUCTURE_LOOKBACK_BARS:
        return False

    if direction == "LONG":
        previous_low = min(r.low for r in previous)
        return current.close < previous_low

    if direction == "SHORT":
        previous_high = max(r.high for r in previous)
        return current.close > previous_high

    return False


def adverse_move_percent(
    rows: Sequence[Candle],
    idx: int,
    direction: str,
) -> float:

    if idx <= 0:
        return 0.0

    lookback = min(
        idx,
        max(1, LOOKBACK_MINUTES // 5),
    )

    start_idx = idx - lookback

    start_price = rows[start_idx].close
    current_price = rows[idx].close

    raw = pct_change(start_price, current_price)

    if raw is None:
        return 0.0

    if direction == "LONG":
        return raw

    if direction == "SHORT":
        return -raw

    return 0.0


def recent_adverse_statistics(
    rows: Sequence[Candle],
    idx: int,
    direction: str,
) -> Tuple[int, int, float]:

    if idx <= 0:
        return 0, 0, 0.0

    lookback_bars = min(
        idx,
        LOOKBACK_MINUTES // 5,
    )

    start = max(1, idx - lookback_bars)

    adverse_count = 0
    consecutive = 0
    max_consecutive = 0

    signed_moves: List[float] = []

    for j in range(start, idx + 1):
        previous_close = rows[j - 1].close
        current_close = rows[j].close

        raw = pct_change(previous_close, current_close)

        if raw is None:
            continue

        signed = raw if direction == "LONG" else -raw

        signed_moves.append(signed)

        if signed < 0:
            adverse_count += 1
            consecutive += 1
            max_consecutive = max(
                max_consecutive,
                consecutive,
            )
        else:
            consecutive = 0

    if signed_moves:
        net_move = sum(signed_moves)
    else:
        net_move = 0.0

    return (
        adverse_count,
        max_consecutive,
        net_move,
    )


def severe_balance_for_direction(
    rows: Sequence[Candle],
    idx: int,
    direction: str,
) -> bool:

    if idx < 6:
        return False

    start = max(0, idx - 6)

    favorable = 0.0
    adverse = 0.0

    for j in range(start + 1, idx + 1):
        raw = pct_change(
            rows[j - 1].close,
            rows[j].close,
        )

        if raw is None:
            continue

        signed = raw if direction == "LONG" else -raw

        if signed >= 0:
            favorable += signed
        else:
            adverse += abs(signed)

    total = favorable + adverse

    if total <= 0:
        return False

    adverse_share = adverse / total

    return adverse_share >= 0.65 and adverse >= 0.40


# ============================================================
# HEALTH MODEL
# ============================================================

def classify_health(
    adverse_count: int,
    consecutive_adverse: int,
    net_signed_move_pct: float,
    structure_break: bool,
    severe_balance: bool,
) -> Tuple[str, float, str]:

    score = 0.0
    reasons: List[str] = []

    # Structural break is strongest causal evidence.
    if structure_break:
        score += 3.0
        reasons.append("structure_break")

    # Persistent adverse movement.
    if consecutive_adverse >= 2:
        score += 2.0
        reasons.append("persistent_adverse")

    # Severe balance.
    if severe_balance:
        score += 2.0
        reasons.append("severe_balance")

    # Repeated adverse candles.
    if adverse_count >= 3:
        score += 1.0
        reasons.append("repeated_adverse")

    # Net adverse movement.
    if net_signed_move_pct <= -0.20:
        score += 1.0

    elif net_signed_move_pct <= -0.05:
        score += 0.5

    # Health state.
    #
    # IMPORTANT:
    # The thresholds are deliberately not allowed to make a single
    # adverse candle immediately become CRITICAL.
    if (
        severe_balance
        and structure_break
        and score >= 5.0
    ):
        health = "CRITICAL"

    elif (
        score >= 3.0
        or net_signed_move_pct <= NET_MOVE_DETERIORATING
    ):
        health = "DETERIORATING"

    elif (
        adverse_count >= 1
        or net_signed_move_pct < NET_MOVE_STRESSED
    ):
        health = "STRESSED"

    else:
        health = "HEALTHY"

    if not reasons:
        reasons.append("health_change")

    return health, score, "+".join(reasons)


# ============================================================
# WARNING OBSERVATIONS
# ============================================================

def build_warning_observations(
    symbol: str,
    rows_5m: Sequence[Candle],
) -> List[WarningObservation]:

    if len(rows_5m) < 10:
        return []

    closes = [r.close for r in rows_5m]

    _ = rsi_values(closes)

    observations: List[WarningObservation] = []

    # We do not know the "old direction" globally yet.
    #
    # Instead build observations for both possible directions.
    #
    # Later, when assigning an episode to a transition, the matching
    # direction is selected.
    for direction in ("LONG", "SHORT"):

        previous_health = "HEALTHY"

        for idx in range(
            max(TREND_WINDOW, 10),
            len(rows_5m),
        ):

            (
                adverse_count,
                consecutive_adverse,
                net_signed_move,
            ) = recent_adverse_statistics(
                rows_5m,
                idx,
                direction,
            )

            structure_break = structure_break_for_direction(
                rows_5m,
                idx,
                direction,
            )

            severe_balance = severe_balance_for_direction(
                rows_5m,
                idx,
                direction,
            )

            health, score, reason = classify_health(
                adverse_count=adverse_count,
                consecutive_adverse=consecutive_adverse,
                net_signed_move_pct=net_signed_move,
                structure_break=structure_break,
                severe_balance=severe_balance,
            )

            # We only want actual deterioration warnings.
            if health not in (
                "STRESSED",
                "DETERIORATING",
                "CRITICAL",
            ):
                previous_health = health
                continue

            # A warning is especially useful when health changes
            # from healthy/stressed into deterioration.
            #
            # But we also preserve continuing deterioration because
            # an episode can contain several observations.
            if (
                health != previous_health
                or score >= 2.0
                or structure_break
                or consecutive_adverse >= 2
            ):

                observations.append(
                    WarningObservation(
                        symbol=symbol,
                        timestamp=candle_close_time(rows_5m[idx]),
                        old_direction=direction,
                        health=health,
                        score=score,
                        adverse_count=adverse_count,
                        consecutive_adverse=consecutive_adverse,
                        net_signed_move_pct=net_signed_move,
                        structure_break=structure_break,
                        severe_balance=severe_balance,
                        persistent_adverse=consecutive_adverse >= 2,
                        repeated_adverse=adverse_count >= 3,
                        reason=reason,
                    )
                )

            previous_health = health

    observations.sort(
        key=lambda x: (
            x.timestamp,
            x.old_direction,
        )
    )

    return observations


# ============================================================
# WARNING EPISODES
# ============================================================

def cluster_warning_episodes(
    observations: Sequence[WarningObservation],
) -> List[WarningEpisode]:

    by_direction: Dict[
        Tuple[str, str],
        List[WarningObservation]
    ] = defaultdict(list)

    for obs in observations:
        by_direction[
            (obs.symbol, obs.old_direction)
        ].append(obs)

    episodes: List[WarningEpisode] = []

    for (_symbol, _direction), items in by_direction.items():

        items = sorted(
            items,
            key=lambda x: x.timestamp,
        )

        current: Optional[WarningEpisode] = None

        for obs in items:

            if current is None:
                current = WarningEpisode(
                    symbol=obs.symbol,
                    first_timestamp=obs.timestamp,
                    last_timestamp=obs.timestamp,
                    observations=[obs],
                )
                continue

            gap = (
                obs.timestamp - current.last_timestamp
            ).total_seconds() / 60.0

            if gap <= EPISODE_GAP_MINUTES:

                current.observations.append(obs)
                current.last_timestamp = obs.timestamp

            else:

                episodes.append(current)

                current = WarningEpisode(
                    symbol=obs.symbol,
                    first_timestamp=obs.timestamp,
                    last_timestamp=obs.timestamp,
                    observations=[obs],
                )

        if current is not None:
            episodes.append(current)

    episodes.sort(
        key=lambda e: (
            e.symbol,
            e.first_timestamp,
        )
    )

    return episodes


# ============================================================
# OUTCOME
# ============================================================

def find_5m_close_index(
    rows: Sequence[Candle],
    target: datetime,
) -> Optional[int]:

    for i, row in enumerate(rows):
        if candle_close_time(row) == target:
            return i

    return None


def outcome_after_warning(
    rows_5m: Sequence[Candle],
    warning_time: datetime,
    direction: str,
) -> Tuple[
    Optional[str],
    Optional[float],
    Optional[float],
    Optional[float],
]:

    start_idx = find_5m_close_index(
        rows_5m,
        warning_time,
    )

    if start_idx is None:
        return None, None, None, None

    start_price = rows_5m[start_idx].close

    target_time = warning_time + timedelta(
        minutes=OUTCOME_MINUTES
    )

    end_idx = find_5m_close_index(
        rows_5m,
        target_time,
    )

    if end_idx is None or end_idx <= start_idx:
        return None, None, None, None

    end_price = rows_5m[end_idx].close

    raw_return = pct_change(
        start_price,
        end_price,
    )

    if raw_return is None:
        return None, None, None, None

    signed_hold_return = (
        raw_return
        if direction == "LONG"
        else -raw_return
    )

    min_signed = 0.0
    max_signed = 0.0

    for j in range(
        start_idx + 1,
        end_idx + 1,
    ):

        close_return = pct_change(
            start_price,
            rows_5m[j].close,
        )

        if close_return is None:
            continue

        signed = (
            close_return
            if direction == "LONG"
            else -close_return
        )

        min_signed = min(
            min_signed,
            signed,
        )

        max_signed = max(
            max_signed,
            signed,
        )

    if signed_hold_return <= -OUTCOME_THRESHOLD_PCT:
        outcome = "GOOD"

    elif signed_hold_return >= OUTCOME_THRESHOLD_PCT:
        outcome = "FALSE"

    else:
        outcome = "NEUTRAL"

    return (
        outcome,
        signed_hold_return,
        min_signed,
        max_signed,
    )


# ============================================================
# UNIQUE TRANSITION ASSIGNMENT
# ============================================================

def eligible_episode_for_transition(
    episode: WarningEpisode,
    transition: Transition,
) -> bool:

    if episode.symbol != transition.symbol:
        return False

    if episode.first.old_direction != transition.direction:
        return False

    delta = (
        transition.timestamp
        - episode.first_timestamp
    ).total_seconds() / 60.0

    # Warning must be before or at the transition.
    if delta < MIN_WARNING_LEAD_MINUTES:
        return False

    if delta > MAX_WARNING_LEAD_MINUTES:
        return False

    return True


def assign_one_episode_per_transition(
    transitions: Sequence[Transition],
    episodes: Sequence[WarningEpisode],
) -> List[Tuple[Transition, WarningEpisode]]:

    """
    CRITICAL FIX.

    Each transition receives at most ONE episode.

    Each episode can be used at most ONCE.

    When multiple transitions are eligible for the same episode,
    nearest transition wins.

    When a transition has multiple eligible episodes, the FIRST
    warning episode is selected.

    The assignment is deterministic.
    """

    transitions_sorted = sorted(
        transitions,
        key=lambda t: (
            t.symbol,
            t.timestamp,
        ),
    )

    episodes_sorted = sorted(
        episodes,
        key=lambda e: (
            e.symbol,
            e.first.old_direction,
            e.first_timestamp,
        ),
    )

    # Build all possible relationships.
    candidates: List[
        Tuple[
            float,
            datetime,
            datetime,
            int,
            int,
        ]
    ] = []

    for ti, transition in enumerate(
        transitions_sorted
    ):

        for ei, episode in enumerate(
            episodes_sorted
        ):

            if not eligible_episode_for_transition(
                episode,
                transition,
            ):
                continue

            lead = (
                transition.timestamp
                - episode.first_timestamp
            ).total_seconds() / 60.0

            candidates.append(
                (
                    lead,
                    episode.first_timestamp,
                    transition.timestamp,
                    ti,
                    ei,
                )
            )

    # We want the closest transition for each warning episode.
    candidates.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[2],
        )
    )

    used_transitions = set()
    used_episodes = set()

    assignments: List[
        Tuple[Transition, WarningEpisode]
    ] = []

    for (
        lead,
        episode_time,
        transition_time,
        ti,
        ei,
    ) in candidates:

        if ti in used_transitions:
            continue

        if ei in used_episodes:
            continue

        transition = transitions_sorted[ti]
        episode = episodes_sorted[ei]

        used_transitions.add(ti)
        used_episodes.add(ei)

        assignments.append(
            (transition, episode)
        )

    # Sort final result chronologically.
    assignments.sort(
        key=lambda pair: (
            pair[0].symbol,
            pair[0].timestamp,
        )
    )

    return assignments


# ============================================================
# ANALYSIS
# ============================================================

def analyze_symbol(
    symbol: str,
) -> Tuple[
    List[Transition],
    List[WarningEpisode],
    List[Assignment],
]:

    rows_30m = load_rows(
        symbol,
        "30m",
    )

    rows_5m = load_rows(
        symbol,
        "5m",
    )

    print(
        f"\n[{symbol}] "
        f"30m={len(rows_30m):,} "
        f"5m={len(rows_5m):,}"
    )

    transitions = build_directional_transitions(
        symbol,
        rows_30m,
    )

    observations = build_warning_observations(
        symbol,
        rows_5m,
    )

    episodes = cluster_warning_episodes(
        observations
    )

    assignments_raw = assign_one_episode_per_transition(
        transitions,
        episodes,
    )

    assignments: List[Assignment] = []

    for transition, episode in assignments_raw:

        warning = episode.first

        lead_minutes = (
            transition.timestamp
            - warning.timestamp
        ).total_seconds() / 60.0

        (
            outcome,
            hold_return,
            min_return,
            max_return,
        ) = outcome_after_warning(
            rows_5m,
            warning.timestamp,
            transition.direction,
        )

        if outcome is None:
            continue

        assignments.append(
            Assignment(
                transition=transition,
                episode=episode,
                lead_minutes=lead_minutes,
                outcome=outcome,
                hold_return_pct=hold_return,
                min_return_pct=min_return,
                max_return_pct=max_return,
            )
        )

    return (
        transitions,
        episodes,
        assignments,
    )


# ============================================================
# FORMATTING
# ============================================================

def fmt_num(
    value: Optional[float],
    digits: int = 3,
) -> str:

    if value is None:
        return "N/A"

    return f"{value:.{digits}f}"


def fmt_pct(
    value: Optional[float],
    digits: int = 3,
) -> str:

    if value is None:
        return "N/A"

    return f"{value:.{digits}f}%"


def mean(values: Iterable[float]) -> Optional[float]:

    vals = [
        v for v in values
        if v is not None
        and math.isfinite(v)
    ]

    if not vals:
        return None

    return sum(vals) / len(vals)


def median(values: Iterable[float]) -> Optional[float]:

    vals = sorted(
        v for v in values
        if v is not None
        and math.isfinite(v)
    )

    if not vals:
        return None

    n = len(vals)

    if n % 2:
        return vals[n // 2]

    return (
        vals[n // 2 - 1]
        + vals[n // 2]
    ) / 2.0


# ============================================================
# REPORTING
# ============================================================

def summarize_group(
    title: str,
    assignments: Sequence[Assignment],
) -> None:

    total = len(assignments)

    counts = Counter(
        a.outcome
        for a in assignments
    )

    good = counts.get("GOOD", 0)
    false = counts.get("FALSE", 0)
    neutral = counts.get("NEUTRAL", 0)

    valid = good + false + neutral

    good_rate = (
        good / valid * 100.0
        if valid
        else None
    )

    false_rate = (
        false / valid * 100.0
        if valid
        else None
    )

    hold_values = [
        a.hold_return_pct
        for a in assignments
        if a.hold_return_pct is not None
    ]

    lead_values = [
        a.lead_minutes
        for a in assignments
        if a.lead_minutes is not None
    ]

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)

    print(f"N ASSIGNED:       {total}")
    print(f"GOOD:             {good}")
    print(f"FALSE:            {false}")
    print(f"NEUTRAL:          {neutral}")
    print(f"GOOD %:           {fmt_num(good_rate, 1)}%")
    print(f"FALSE %:          {fmt_num(false_rate, 1)}%")
    print(
        f"AVG HOLD60:       "
        f"{fmt_pct(mean(hold_values))}"
    )
    print(
        f"MEDIAN HOLD60:    "
        f"{fmt_pct(median(hold_values))}"
    )
    print(
        f"AVG WARNING LEAD: "
        f"{fmt_num(mean(lead_values), 1)}m"
    )
    print(
        f"MEDIAN WARNING LEAD:"
        f" {fmt_num(median(lead_values), 1)}m"
    )


def feature_summary(
    assignments: Sequence[Assignment],
) -> None:

    print()
    print("=" * 78)
    print("FIRST WARNING FEATURE COMPARISON")
    print("=" * 78)

    for outcome_name in (
        "GOOD",
        "FALSE",
        "NEUTRAL",
    ):

        group = [
            a
            for a in assignments
            if a.outcome == outcome_name
        ]

        if not group:
            continue

        print()
        print(f"[{outcome_name}] N={len(group)}")

        print(
            "score:",
            fmt_num(
                mean(
                    a.episode.first.score
                    for a in group
                )
            ),
        )

        print(
            "adverse_count:",
            fmt_num(
                mean(
                    a.episode.first.adverse_count
                    for a in group
                )
            ),
        )

        print(
            "consecutive_adverse:",
            fmt_num(
                mean(
                    a.episode.first.consecutive_adverse
                    for a in group
                )
            ),
        )

        print(
            "net_signed_move:",
            fmt_pct(
                mean(
                    a.episode.first.net_signed_move_pct
                    for a in group
                )
            ),
        )

        print(
            "lead_to_T0:",
            fmt_num(
                mean(
                    a.lead_minutes
                    for a in group
                ),
                1,
            ),
            "m",
        )


def reason_summary(
    assignments: Sequence[Assignment],
) -> None:

    print()
    print("=" * 78)
    print("WARNING REASONS")
    print("=" * 78)

    reasons = (
        "structure_break",
        "persistent_adverse",
        "repeated_adverse",
        "severe_balance",
        "health_change",
    )

    for reason_name in reasons:
        group = [
            a
            for a in assignments
            if reason_name in a.episode.first.reason.split("+")
        ]

        if not group:
            continue

        counts = Counter(a.outcome for a in group)
        valid = len(group)
        good = counts.get("GOOD", 0)
        false = counts.get("FALSE", 0)
        neutral = counts.get("NEUTRAL", 0)
        avg60 = mean(a.hold_return_pct for a in group)

        print(
            f"{reason_name:22s} "
            f"N={valid:4d} "
            f"GOOD={good:4d} "
            f"({good / valid * 100:5.1f}%) "
            f"FALSE={false:4d} "
            f"({false / valid * 100:5.1f}%) "
            f"NEUTRAL={neutral:4d} "
            f"AVG60={fmt_pct(avg60)}"
        )


def health_summary(
    assignments: Sequence[Assignment],
) -> None:

    print()
    print("=" * 78)
    print("FIRST WARNING HEALTH")
    print("=" * 78)

    for health in (
        "STRESSED",
        "DETERIORATING",
        "CRITICAL",
    ):

        group = [
            a
            for a in assignments
            if a.episode.first.health == health
        ]

        if not group:
            continue

        counts = Counter(
            a.outcome
            for a in group
        )

        neutral = counts.get("NEUTRAL", 0)

        total = len(group)

        good = counts.get("GOOD", 0)
        false = counts.get("FALSE", 0)

        avg60 = mean(a.hold_return_pct for a in group)

        print(
            f"{health:16s} "
            f"N={total:4d} "
            f"GOOD={good:4d} "
            f"({good / total * 100:5.1f}%) "
            f"FALSE={false:4d} "
            f"({false / total * 100:5.1f}%) "
            f"NEUTRAL={neutral:4d} "
            f"AVG60={fmt_pct(avg60)}"
        )


def score_bucket_summary(
    assignments: Sequence[Assignment],
) -> None:

    print()
    print("=" * 78)
    print("SCORE BUCKETS")
    print("=" * 78)

    buckets = [
        ("<1", lambda x: x < 1.0),
        ("1-<2", lambda x: 1.0 <= x < 2.0),
        ("2-<3", lambda x: 2.0 <= x < 3.0),
        ("3-<4", lambda x: 3.0 <= x < 4.0),
        ("4+", lambda x: x >= 4.0),
    ]

    for name, predicate in buckets:
        group = [
            a
            for a in assignments
            if predicate(a.episode.first.score)
        ]

        if not group:
            continue

        counts = Counter(a.outcome for a in group)
        total = len(group)
        good = counts.get("GOOD", 0)
        false = counts.get("FALSE", 0)
        neutral = counts.get("NEUTRAL", 0)
        avg60 = mean(a.hold_return_pct for a in group)

        print(
            f"{name:22s} "
            f"N={total:4d} "
            f"GOOD={good:4d} "
            f"({good / total * 100:5.1f}%) "
            f"FALSE={false:4d} "
            f"({false / total * 100:5.1f}%) "
            f"NEUTRAL={neutral:4d} "
            f"AVG60={fmt_pct(avg60)}"
        )


def direction_summary(
    assignments: Sequence[Assignment],
) -> None:

    print()
    print("=" * 78)
    print("DIRECTION")
    print("=" * 78)

    for direction in (
        "LONG",
        "SHORT",
    ):

        group = [
            a
            for a in assignments
            if a.transition.direction == direction
        ]

        summarize_group(
            direction,
            group,
        )


# ============================================================
# UNIQUENESS AUDIT
# ============================================================

def uniqueness_audit(
    assignments: Sequence[Assignment],
) -> None:

    print()
    print("=" * 78)
    print("UNIQUENESS AUDIT — THE IMPORTANT FIX")
    print("=" * 78)

    transition_keys = [
        (
            a.transition.symbol,
            a.transition.timestamp,
            a.transition.direction,
        )
        for a in assignments
    ]

    episode_keys = [
        (
            a.episode.symbol,
            a.episode.first.old_direction,
            a.episode.first_timestamp,
        )
        for a in assignments
    ]

    transition_counts = Counter(
        transition_keys
    )

    episode_counts = Counter(
        episode_keys
    )

    duplicate_transitions = [
        k
        for k, v in transition_counts.items()
        if v > 1
    ]

    duplicate_episodes = [
        k
        for k, v in episode_counts.items()
        if v > 1
    ]

    print(
        f"ASSIGNMENTS:             {len(assignments)}"
    )

    print(
        f"UNIQUE TRANSITIONS:      "
        f"{len(set(transition_keys))}"
    )

    print(
        f"UNIQUE WARNING EPISODES: "
        f"{len(set(episode_keys))}"
    )

    print(
        f"DUPLICATE TRANSITIONS:   "
        f"{len(duplicate_transitions)}"
    )

    print(
        f"DUPLICATE EPISODES:      "
        f"{len(duplicate_episodes)}"
    )

    if duplicate_transitions:
        print(
            "WARNING: duplicate transition assignment detected."
        )
    else:
        print(
            "OK: every transition has at most one assigned episode."
        )

    if duplicate_episodes:
        print(
            "WARNING: a warning episode was reused."
        )
    else:
        print(
            "OK: every warning episode is used at most once."
        )


# ============================================================
# REPRESENTATIVE CASES
# ============================================================

def print_representative_cases(
    assignments: Sequence[Assignment],
    limit: int = 20,
) -> None:

    print()
    print("=" * 78)
    print("REPRESENTATIVE UNIQUE CASES")
    print("=" * 78)

    ordered = sorted(
        assignments,
        key=lambda a: (
            a.outcome,
            a.transition.symbol,
            a.transition.timestamp,
        )
    )

    for a in ordered[:limit]:

        w = a.episode.first
        t = a.transition

        print()
        print(
            f"{t.symbol:5s} "
            f"{t.direction:5s} "
            f"{a.outcome:7s}"
        )

        print(
            f"  WARNING:    {w.timestamp}"
        )

        print(
            f"  T0:         {t.timestamp}"
        )

        print(
            f"  LEAD:       {a.lead_minutes:.1f}m"
        )

        print(
            f"  HEALTH:     {w.health}"
        )

        print(
            f"  SCORE:      {w.score:.2f}"
        )

        print(
            f"  ADVERSE:    {w.adverse_count}"
        )

        print(
            f"  CONSEC:     {w.consecutive_adverse}"
        )

        print(
            f"  NET MOVE:   {w.net_signed_move_pct:.3f}%"
        )

        print(
            f"  REASON:     {w.reason}"
        )

        print(
            f"  HOLD60:     "
            f"{fmt_pct(a.hold_return_pct)}"
        )

        print(
            f"  MIN60:      "
            f"{fmt_pct(a.min_return_pct)}"
        )

        print(
            f"  MAX60:      "
            f"{fmt_pct(a.max_return_pct)}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "V5.6.12.1-A unique first-warning "
            "transition analysis"
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
    )

    args = parser.parse_args()

    all_transitions: List[Transition] = []
    all_episodes: List[WarningEpisode] = []
    all_assignments: List[Assignment] = []

    print()
    print("=" * 78)
    print("V5.6.12.1-A — UNIQUE FIRST WARNING ANALYSIS")
    print("=" * 78)

    print(
        "Research only — no DB writes / no orders / no engine changes."
    )

    print()
    print(
        "RULE:"
    )
    print(
        "ONE transition -> ONE first warning episode -> ONE outcome"
    )

    print()
    print(
        f"WARNING LOOKBACK: {MAX_WARNING_LEAD_MINUTES}m"
    )

    print(
        f"WARNING EPISODE GAP: {EPISODE_GAP_MINUTES}m"
    )

    print(
        f"OUTCOME HORIZON: {OUTCOME_MINUTES}m"
    )

    for symbol in args.symbols:

        try:

            (
                transitions,
                episodes,
                assignments,
            ) = analyze_symbol(symbol)

            all_transitions.extend(
                transitions
            )

            all_episodes.extend(
                episodes
            )

            all_assignments.extend(
                assignments
            )

            print(
                f"  transitions={len(transitions):4d} "
                f"episodes={len(episodes):4d} "
                f"assigned={len(assignments):4d}"
            )

        except Exception as exc:

            print()
            print(
                f"[{symbol}] ERROR: {exc}"
            )

    # --------------------------------------------------------
    # GLOBAL REPORT
    # --------------------------------------------------------

    print()
    print()
    print("#" * 78)
    print("GLOBAL RESULTS")
    print("#" * 78)

    print()
    print(
        f"KNOWN DIRECTIONAL TRANSITIONS: "
        f"{len(all_transitions)}"
    )

    print(
        f"WARNING EPISODES:               "
        f"{len(all_episodes)}"
    )

    print(
        f"UNIQUELY ASSIGNED TRANSITIONS:  "
        f"{len(all_assignments)}"
    )

    unmatched = (
        len(all_transitions)
        - len(all_assignments)
    )

    print(
        f"TRANSITIONS WITHOUT WARNING:    "
        f"{unmatched}"
    )

    summarize_group(
        "ALL UNIQUE ASSIGNMENTS",
        all_assignments,
    )

    direction_summary(
        all_assignments
    )

    feature_summary(
        all_assignments
    )

    reason_summary(
        all_assignments
    )

    health_summary(
        all_assignments
    )

    score_bucket_summary(
        all_assignments
    )

    uniqueness_audit(
        all_assignments
    )

    print_representative_cases(
        all_assignments,
        limit=30,
    )

    # --------------------------------------------------------
    # FINAL INTERPRETATION
    # --------------------------------------------------------

    print()
    print("#" * 78)
    print("V5.6.12.1-A INTERPRETATION")
    print("#" * 78)

    print()
    print(
        "This run is a methodology test, not a trading-rule test."
    )

    print()
    print(
        "The critical question is whether the GOOD/FALSE separation "
        "still exists after removing warning reuse."
    )

    print()
    print(
        "If GOOD/FALSE separation becomes weaker, the previous "
        "V5.6.12 statistics were partly caused by overlapping "
        "transition windows."
    )

    print()
    print(
        "If the separation survives, the first-warning concept "
        "deserves deeper research."
    )

    print()
    print(
        "Do NOT change the live KISS engine based on this run."
    )

    print()
    print(
        "NEXT QUESTION:"
    )

    print(
        "Can the unique first-warning episode be distinguished "
        "as SURVIVE versus TRUE DETERIORATION using only information "
        "available at the warning time?"
    )

    print()


if __name__ == "__main__":
    main()