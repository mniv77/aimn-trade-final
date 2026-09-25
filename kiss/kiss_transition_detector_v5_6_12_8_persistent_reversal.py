# kiss_transition_detector_v5_6_12_8_persistent_reversal.py
"""
KISS V5.6.12.8 — PERSISTENT REVERSAL TEST
================================================

RESEARCH ONLY.

Purpose
-------
V5.6.12.6 showed that the FIRST causal OPPOSITE_TRANSITION
can be useful, but it is NOT universally safe to exit immediately.

V5.6.12.7 asks a narrower question:

    When an opposite transition is detected,
    how STRONG is the opposite evidence?

We classify the first causal opposite transition as:

    WEAK
    MEDIUM
    STRONG

using only information available at the decision point.

Strength evidence:
    - opposite structure break
    - consecutive opposite candles
    - opposite movement magnitude
    - acceleration / persistence
    - damage to the old direction
    - RSI context when available
    - MA context when available

Future candles are used ONLY for evaluation.

NO ORDERS.
NO DB WRITES.
NO ENGINE CHANGES.

IMPORTANT:
The V5.6.12.2 one-to-one assignment methodology is preserved.

Dependency chain:

    V5.6.12.7
          |
          v
    V5.6.12.5
          |
          v
    V5.6.12.2

The data loader and assignment functions belong to
V5.6.12.2 and are accessed through:

    v125.base.load_rows()
    v125.base.build_directional_transitions()
    v125.base.build_warning_observations()
    v125.base.cluster_warning_episodes()
    v125.base.assign_one_episode_per_transition()

This file does NOT call v125.load_rows().
"""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import kiss_transition_detector_v5_6_12_5_recovery_opposite_transition as v125


# ============================================================
# CONFIGURATION
# ============================================================

CHECKPOINT_MINUTES = (15, 30, 45, 60)

# Strength thresholds.
#
# These are RESEARCH thresholds only.
# They are deliberately transparent so the results can be
# reviewed and changed later.

STRONG_CONSECUTIVE = 4
MEDIUM_CONSECUTIVE = 3

STRONG_MOVE_PCT = 0.75
MEDIUM_MOVE_PCT = 0.35

STRONG_OLD_DAMAGE_PCT = 0.75
MEDIUM_OLD_DAMAGE_PCT = 0.35

STRONG_ACCELERATION_PCT = 0.20
MEDIUM_ACCELERATION_PCT = 0.05

RSI_LONG_WEAK_ZONE = 45.0
RSI_LONG_STRONG_ZONE = 35.0

RSI_SHORT_WEAK_ZONE = 55.0
RSI_SHORT_STRONG_ZONE = 65.0

MA_CONTEXT_PCT = 0.20

# Future evaluation.
# This comes from V5.6.12.2 and is used only for scoring.
HOLD_MINUTES = (15, 30, 45, 60)


# ============================================================
# BASIC HELPERS
# ============================================================

def pct_change(old: Optional[float], new: Optional[float]) -> Optional[float]:
    if old is None or new is None:
        return None
    if old == 0:
        return None
    return ((new - old) / old) * 100.0


def signed_return(
    start_price: Optional[float],
    end_price: Optional[float],
    direction: str,
) -> Optional[float]:
    raw = pct_change(start_price, end_price)
    if raw is None:
        return None

    return raw if direction == "LONG" else -raw


def opposite_direction(direction: str) -> str:
    return "SHORT" if direction == "LONG" else "LONG"


def row_close(row) -> Optional[float]:
    try:
        value = row.close
    except AttributeError:
        try:
            value = row["close"]
        except Exception:
            return None

    try:
        return float(value)
    except Exception:
        return None


def row_timestamp(row) -> Optional[datetime]:
    try:
        value = row.timestamp
    except AttributeError:
        try:
            value = row["timestamp"]
        except Exception:
            return None

    return value


def close_time(row) -> Optional[datetime]:
    return v125.base.candle_close_time(row)


def find_close_index(rows: Sequence, target: datetime) -> Optional[int]:
    """
    Use the exact close-time helper already used by the
    V5.6.12.5 / V5.6.12.2 research chain.
    """
    return v125.base.find_close_index(rows, target)


# ============================================================
# OPTIONAL FIELD HELPERS
# ============================================================

def numeric_field(row, names: Sequence[str]) -> Optional[float]:
    for name in names:
        try:
            value = getattr(row, name)
        except AttributeError:
            try:
                value = row[name]
            except Exception:
                continue

        if value is None:
            continue

        try:
            value = float(value)
        except Exception:
            continue

        if math.isnan(value):
            continue

        return value

    return None


def rsi_value(row) -> Optional[float]:
    return numeric_field(
        row,
        (
            "rsi",
            "RSI",
            "rsi14",
            "RSI14",
        ),
    )


def ma_value(row) -> Optional[float]:
    return numeric_field(
        row,
        (
            "ma20",
            "MA20",
            "moving_average",
            "moving_avg",
        ),
    )


# ============================================================
# LOCAL PRICE / PATH MEASUREMENTS
# ============================================================

@dataclass
class PathMetrics:
    signed_old: Optional[float]
    signed_opposite: Optional[float]

    minimum_old: float
    maximum_old: float

    favorable_old_bars: int
    adverse_old_bars: int

    max_opposite_consecutive: int
    opposite_acceleration: Optional[float]

    old_damage: float

    rsi: Optional[float]
    ma_distance: Optional[float]


def measure_path(
    rows: Sequence,
    broken_idx: int,
    checkpoint_idx: int,
    old_direction: str,
) -> PathMetrics:

    if checkpoint_idx <= broken_idx:
        return PathMetrics(
            signed_old=None,
            signed_opposite=None,
            minimum_old=0.0,
            maximum_old=0.0,
            favorable_old_bars=0,
            adverse_old_bars=0,
            max_opposite_consecutive=0,
            opposite_acceleration=None,
            old_damage=0.0,
            rsi=None,
            ma_distance=None,
        )

    start_price = row_close(rows[broken_idx])
    end_price = row_close(rows[checkpoint_idx])

    signed_old = signed_return(
        start_price,
        end_price,
        old_direction,
    )

    opposite = opposite_direction(old_direction)

    signed_opposite = signed_return(
        start_price,
        end_price,
        opposite,
    )

    minimum_old = 0.0
    maximum_old = 0.0

    favorable_old = 0
    adverse_old = 0

    consecutive_opposite = 0
    max_opposite_consecutive = 0

    opposite_moves: List[float] = []

    for idx in range(broken_idx + 1, checkpoint_idx + 1):
        prev_close = row_close(rows[idx - 1])
        curr_close = row_close(rows[idx])

        raw = pct_change(prev_close, curr_close)

        if raw is None:
            continue

        old_move = raw if old_direction == "LONG" else -raw
        opposite_move = -old_move

        if old_move >= 0:
            favorable_old += 1
            consecutive_opposite = 0
        else:
            adverse_old += 1

            consecutive_opposite += 1
            max_opposite_consecutive = max(
                max_opposite_consecutive,
                consecutive_opposite,
            )

        from_broken = signed_return(
            start_price,
            curr_close,
            old_direction,
        )

        if from_broken is not None:
            minimum_old = min(minimum_old, from_broken)
            maximum_old = max(maximum_old, from_broken)

        opposite_moves.append(opposite_move)

    opposite_acceleration = None

    if len(opposite_moves) >= 2:
        half = max(1, len(opposite_moves) // 2)

        first_half = opposite_moves[:half]
        second_half = opposite_moves[half:]

        if first_half and second_half:
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)

            opposite_acceleration = second_avg - first_avg

    old_damage = max(
        0.0,
        -(signed_old or 0.0),
    )

    rsi = rsi_value(rows[checkpoint_idx])

    ma = ma_value(rows[checkpoint_idx])
    price = end_price

    ma_distance = None

    if ma is not None and price is not None and ma != 0:
        ma_distance = ((price - ma) / ma) * 100.0

    return PathMetrics(
        signed_old=signed_old,
        signed_opposite=signed_opposite,
        minimum_old=minimum_old,
        maximum_old=maximum_old,
        favorable_old_bars=favorable_old,
        adverse_old_bars=adverse_old,
        max_opposite_consecutive=max_opposite_consecutive,
        opposite_acceleration=opposite_acceleration,
        old_damage=old_damage,
        rsi=rsi,
        ma_distance=ma_distance,
    )


# ============================================================
# STRENGTH SCORE
# ============================================================

@dataclass
class StrengthResult:
    label: str
    score: float

    structure: bool
    consecutive: int
    move_pct: Optional[float]

    old_damage_pct: float
    acceleration_pct: Optional[float]

    rsi: Optional[float]
    ma_distance_pct: Optional[float]

    reasons: List[str]


def opposite_structure(
    rows: Sequence,
    checkpoint_idx: int,
    old_direction: str,
) -> bool:

    new_direction = opposite_direction(old_direction)

    try:
        return bool(
            v125.base.structure_break_for_direction(
                rows,
                checkpoint_idx,
                new_direction,
                v125.base.CONTINUATION_STRUCTURE_BARS,
            )
        )
    except TypeError:
        try:
            return bool(
                v125.base.structure_break_for_direction(
                    rows,
                    checkpoint_idx,
                    new_direction,
                )
            )
        except Exception:
            return False
    except Exception:
        return False


def score_opposite_strength(
    rows: Sequence,
    broken_idx: int,
    checkpoint_idx: int,
    old_direction: str,
    opposite_structure_flag: bool,
    opposite_consecutive: int,
    opposite_move_pct: Optional[float],
) -> StrengthResult:

    metrics = measure_path(
        rows,
        broken_idx,
        checkpoint_idx,
        old_direction,
    )

    score = 0.0
    reasons: List[str] = []

    # --------------------------------------------------------
    # 1. STRUCTURE
    # --------------------------------------------------------

    if opposite_structure_flag:
        score += 3.0
        reasons.append("opposite_structure")

    # --------------------------------------------------------
    # 2. CONSECUTIVE OPPOSITE CANDLES
    # --------------------------------------------------------

    if opposite_consecutive >= STRONG_CONSECUTIVE:
        score += 3.0
        reasons.append(
            f"opposite_consecutive>={STRONG_CONSECUTIVE}"
        )
    elif opposite_consecutive >= MEDIUM_CONSECUTIVE:
        score += 2.0
        reasons.append(
            f"opposite_consecutive>={MEDIUM_CONSECUTIVE}"
        )
    elif opposite_consecutive >= 2:
        score += 1.0
        reasons.append("opposite_consecutive>=2")

    # --------------------------------------------------------
    # 3. OPPOSITE MOVEMENT
    # --------------------------------------------------------

    move_abs = abs(opposite_move_pct or 0.0)

    if move_abs >= STRONG_MOVE_PCT:
        score += 3.0
        reasons.append(
            f"opposite_move>={STRONG_MOVE_PCT:.2f}%"
        )
    elif move_abs >= MEDIUM_MOVE_PCT:
        score += 2.0
        reasons.append(
            f"opposite_move>={MEDIUM_MOVE_PCT:.2f}%"
        )
    elif move_abs >= 0.20:
        score += 1.0
        reasons.append("opposite_move>=0.20%")

    # --------------------------------------------------------
    # 4. DAMAGE TO OLD DIRECTION
    # --------------------------------------------------------

    old_damage = metrics.old_damage

    if old_damage >= STRONG_OLD_DAMAGE_PCT:
        score += 2.0
        reasons.append(
            f"old_damage>={STRONG_OLD_DAMAGE_PCT:.2f}%"
        )
    elif old_damage >= MEDIUM_OLD_DAMAGE_PCT:
        score += 1.0
        reasons.append(
            f"old_damage>={MEDIUM_OLD_DAMAGE_PCT:.2f}%"
        )

    # --------------------------------------------------------
    # 5. ACCELERATION
    # --------------------------------------------------------

    acceleration = metrics.opposite_acceleration

    if acceleration is not None:
        if acceleration >= STRONG_ACCELERATION_PCT:
            score += 2.0
            reasons.append(
                f"opposite_acceleration>={STRONG_ACCELERATION_PCT:.2f}%"
            )
        elif acceleration >= MEDIUM_ACCELERATION_PCT:
            score += 1.0
            reasons.append(
                f"opposite_acceleration>={MEDIUM_ACCELERATION_PCT:.2f}%"
            )

    # --------------------------------------------------------
    # 6. RSI CONTEXT
    #
    # RSI is context only.
    # It is NOT treated as a conventional buy/sell trigger.
    # --------------------------------------------------------

    rsi = metrics.rsi

    if rsi is not None:

        if old_direction == "LONG":

            # Falling / low RSI supports the idea that the
            # old LONG is losing strength.
            if rsi <= RSI_LONG_STRONG_ZONE:
                score += 2.0
                reasons.append("RSI_supports_short_context")
            elif rsi <= RSI_LONG_WEAK_ZONE:
                score += 1.0
                reasons.append("RSI_weakens_long")

        else:

            # Rising / high RSI supports the idea that the
            # old SHORT is losing strength.
            if rsi >= RSI_SHORT_STRONG_ZONE:
                score += 2.0
                reasons.append("RSI_supports_long_context")
            elif rsi >= RSI_SHORT_WEAK_ZONE:
                score += 1.0
                reasons.append("RSI_weakens_short")

    # --------------------------------------------------------
    # 7. MA CONTEXT
    # --------------------------------------------------------

    ma_distance = metrics.ma_distance

    if ma_distance is not None:

        if old_direction == "LONG":

            if ma_distance < -MA_CONTEXT_PCT:
                score += 1.0
                reasons.append("price_below_MA_context")

        else:

            if ma_distance > MA_CONTEXT_PCT:
                score += 1.0
                reasons.append("price_above_MA_context")

    # --------------------------------------------------------
    # FINAL LABEL
    # --------------------------------------------------------

    if score >= 9.0:
        label = "STRONG"
    elif score >= 5.0:
        label = "MEDIUM"
    else:
        label = "WEAK"

    return StrengthResult(
        label=label,
        score=score,
        structure=opposite_structure_flag,
        consecutive=opposite_consecutive,
        move_pct=opposite_move_pct,
        old_damage_pct=old_damage,
        acceleration_pct=acceleration,
        rsi=rsi,
        ma_distance_pct=ma_distance,
        reasons=reasons,
    )


# ============================================================
# FUTURE-ONLY EVALUATION
# ============================================================

def future_return(
    rows: Sequence,
    checkpoint_idx: int,
    direction: str,
    minutes: int,
) -> Optional[float]:

    close_at = close_time(rows[checkpoint_idx])

    if close_at is None:
        return None

    target = close_at + timedelta(minutes=minutes)

    end_idx = find_close_index(
        rows,
        target,
    )

    if end_idx is None or end_idx <= checkpoint_idx:
        return None

    start_price = row_close(rows[checkpoint_idx])
    end_price = row_close(rows[end_idx])

    return signed_return(
        start_price,
        end_price,
        direction,
    )


def future_mae_mfe(
    rows: Sequence,
    checkpoint_idx: int,
    direction: str,
    minutes: int,
) -> Tuple[Optional[float], Optional[float]]:

    close_at = close_time(rows[checkpoint_idx])

    if close_at is None:
        return None, None

    target = close_at + timedelta(minutes=minutes)

    end_idx = find_close_index(
        rows,
        target,
    )

    if end_idx is None or end_idx <= checkpoint_idx:
        return None, None

    start_price = row_close(rows[checkpoint_idx])

    if start_price is None:
        return None, None

    minimum = 0.0
    maximum = 0.0

    for idx in range(
        checkpoint_idx + 1,
        end_idx + 1,
    ):
        price = row_close(rows[idx])

        if price is None:
            continue

        move = signed_return(
            start_price,
            price,
            direction,
        )

        if move is None:
            continue

        minimum = min(minimum, move)
        maximum = max(maximum, move)

    return minimum, maximum


def outcome_label(
    ret: Optional[float],
) -> str:

    if ret is None:
        return "UNKNOWN"

    threshold = v125.base.OUTCOME_THRESHOLD_PCT

    if ret <= -threshold:
        return "GOOD"

    if ret >= threshold:
        return "FALSE"

    return "NEUTRAL"


# ============================================================
# OPPOSITE CASE
# ============================================================

@dataclass
class OppositeCase:
    symbol: str
    direction: str

    warning_time: Optional[datetime]
    broken_time: Optional[datetime]
    opposite_time: Optional[datetime]
    official_time: Optional[datetime]

    warning_lead: Optional[float]
    opposite_lead: Optional[float]

    checkpoint_minutes: int

    decision_price: Optional[float]

    strength: StrengthResult

    hold_returns: Dict[int, Optional[float]]
    hold_labels: Dict[int, str]

    hold_mae: Dict[int, Optional[float]]
    hold_mfe: Dict[int, Optional[float]]


# ============================================================
# ASSIGNMENT HELPERS
# ============================================================

def assignment_symbol(assignment) -> str:
    for name in ("symbol",):
        try:
            value = getattr(assignment, name)
            if value:
                return str(value)
        except Exception:
            pass

    try:
        value = assignment["symbol"]
        if value:
            return str(value)
    except Exception:
        pass

    return "UNKNOWN"


def assignment_direction(assignment) -> str:
    for name in ("direction",):
        try:
            value = getattr(assignment, name)
            if value:
                return str(value)
        except Exception:
            pass

    try:
        value = assignment["direction"]
        if value:
            return str(value)
    except Exception:
        pass

    return "UNKNOWN"


def assignment_transition_time(assignment) -> Optional[datetime]:
    for name in (
        "transition_time",
        "event_time",
        "official_time",
        "t0",
    ):
        try:
            value = getattr(assignment, name)
            if isinstance(value, datetime):
                return value
        except Exception:
            pass

    for name in (
        "transition_time",
        "event_time",
        "official_time",
        "t0",
    ):
        try:
            value = assignment[name]
            if isinstance(value, datetime):
                return value
        except Exception:
            pass

    return None


def assignment_warning_time(assignment) -> Optional[datetime]:
    for name in (
        "warning_time",
        "first_warning_time",
    ):
        try:
            value = getattr(assignment, name)
            if isinstance(value, datetime):
                return value
        except Exception:
            pass

    for name in (
        "warning_time",
        "first_warning_time",
    ):
        try:
            value = assignment[name]
            if isinstance(value, datetime):
                return value
        except Exception:
            pass

    return None


# ============================================================
# EVALUATE ONE ASSIGNMENT
# ============================================================

def evaluate_assignment(
    rows_5m,
    assignment,
) -> Optional[OppositeCase]:
    """
    V5.6.12.7 research wrapper.

    V5.6.12.5 returns a LIST of ReverseCheckpoint objects.
    We find:

        FIRST THESIS_BROKEN checkpoint
                    |
                    v
        FIRST causal OPPOSITE_TRANSITION checkpoint

    No future information is used to make the decision.

    Research only.
    No orders.
    No DB writes.
    """

    checkpoints = v125.evaluate_assignment(
        rows_5m,
        assignment,
    )

    if not checkpoints:
        return None

    direction = assignment.transition.direction
    symbol = assignment.transition.symbol

    official_time = assignment.transition.timestamp
    warning_time = assignment.episode.first_timestamp

    # --------------------------------------------------------
    # FIRST THESIS_BROKEN CHECKPOINT
    # --------------------------------------------------------

    broken_checkpoint = None

    for checkpoint in checkpoints:
        if checkpoint.state == "THESIS_BROKEN":
            broken_checkpoint = checkpoint
            break

    if broken_checkpoint is None:
        return None

    # --------------------------------------------------------
    # FIRST CAUSAL OPPOSITE TRANSITION
    # --------------------------------------------------------

    opposite_checkpoint = None

    for checkpoint in checkpoints:

        if (
            checkpoint.checkpoint_minutes
            <= broken_checkpoint.checkpoint_minutes
        ):
            continue

        if getattr(
            checkpoint,
            "path_opposite_transition",
            False,
        ):
            opposite_checkpoint = checkpoint
            break

    if opposite_checkpoint is None:
        return None

    # --------------------------------------------------------
    # CONVERT CHECKPOINT TIMES TO ACTUAL 5m INDICES
    # --------------------------------------------------------

    broken_time = (
        warning_time
        + timedelta(
            minutes=broken_checkpoint.checkpoint_minutes
        )
    )

    opposite_time = (
        warning_time
        + timedelta(
            minutes=opposite_checkpoint.checkpoint_minutes
        )
    )

    broken_idx = find_close_index(
        rows_5m,
        broken_time,
    )

    opposite_idx = find_close_index(
        rows_5m,
        opposite_time,
    )

    if broken_idx is None or opposite_idx is None:
        return None

    if opposite_idx <= broken_idx:
        return None

    # --------------------------------------------------------
    # OPPOSITE EVIDENCE AT THE DECISION POINT
    # --------------------------------------------------------

    structure = bool(
        getattr(
            opposite_checkpoint,
            "path_opposite_structure",
            False,
        )
    )

    consecutive = int(
        getattr(
            opposite_checkpoint,
            "path_opposite_consecutive",
            0,
        )
        or 0
    )

    move_pct = getattr(
        opposite_checkpoint,
        "path_opposite_move_pct",
        None,
    )

    # --------------------------------------------------------
    # STRENGTH
    # --------------------------------------------------------

    strength = score_opposite_strength(
        rows_5m,
        broken_idx,
        opposite_idx,
        direction,
        structure,
        consecutive,
        move_pct,
    )

    # --------------------------------------------------------
    # FUTURE EVALUATION
    # --------------------------------------------------------

    hold_returns: Dict[int, Optional[float]] = {}
    hold_labels: Dict[int, str] = {}

    hold_mae: Dict[int, Optional[float]] = {}
    hold_mfe: Dict[int, Optional[float]] = {}

    for minutes in HOLD_MINUTES:

        ret = future_return(
            rows_5m,
            opposite_idx,
            direction,
            minutes,
        )

        mae, mfe = future_mae_mfe(
            rows_5m,
            opposite_idx,
            direction,
            minutes,
        )

        hold_returns[minutes] = ret
        hold_labels[minutes] = outcome_label(ret)

        hold_mae[minutes] = mae
        hold_mfe[minutes] = mfe

    # --------------------------------------------------------
    # LEADS
    # --------------------------------------------------------

    warning_lead = None
    opposite_lead = None

    if (
        warning_time is not None
        and official_time is not None
    ):
        warning_lead = (
            official_time - warning_time
        ).total_seconds() / 60.0

    if (
        opposite_time is not None
        and official_time is not None
    ):
        opposite_lead = (
            official_time - opposite_time
        ).total_seconds() / 60.0

    decision_price = row_close(
        rows_5m[opposite_idx]
    )

    checkpoint_minutes = int(
        (
            opposite_time - broken_time
        ).total_seconds() / 60.0
    )

    return OppositeCase(
        symbol=symbol,
        direction=direction,
        warning_time=warning_time,
        broken_time=broken_time,
        opposite_time=opposite_time,
        official_time=official_time,
        warning_lead=warning_lead,
        opposite_lead=opposite_lead,
        checkpoint_minutes=checkpoint_minutes,
        decision_price=decision_price,
        strength=strength,
        hold_returns=hold_returns,
        hold_labels=hold_labels,
        hold_mae=hold_mae,
        hold_mfe=hold_mfe,
    )


# ============================================================
# SUMMARY HELPERS
# ============================================================

def pct_text(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{value:+.3f}%"


def avg(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None

    ordered = sorted(values)
    n = len(ordered)

    if n % 2:
        return ordered[n // 2]

    return (
        ordered[n // 2 - 1]
        + ordered[n // 2]
    ) / 2.0


def summarize_group(
    cases: Sequence[OppositeCase],
    title: str,
) -> None:

    print()
    print("=" * 90)
    print(title)
    print("=" * 90)

    print(f"N={len(cases)}")

    if not cases:
        return

    for minutes in HOLD_MINUTES:

        returns = [
            c.hold_returns[minutes]
            for c in cases
            if c.hold_returns[minutes] is not None
        ]

        if not returns:
            print(
                f"HOLD {minutes:>2}m  N=0"
            )
            continue

        exit_better = sum(
            1 for x in returns
            if x < 0
        )

        hold_better = sum(
            1 for x in returns
            if x > 0
        )

        ties = sum(
            1 for x in returns
            if x == 0
        )

        print(
            f"HOLD {minutes:>2}m "
            f"N={len(returns):>2} "
            f"EXIT_BETTER={exit_better:>2} "
            f"HOLD_BETTER={hold_better:>2} "
            f"TIE={ties:>2} "
            f"AVG={pct_text(avg(returns))} "
            f"MEDIAN={pct_text(median(returns))}"
        )


def strength_summary(
    cases: Sequence[OppositeCase],
) -> None:

    print()
    print("=" * 90)
    print("V5.6.12.8 — PERSISTENT REVERSAL SUMMARY")
    print("=" * 90)

    groups: Dict[str, List[OppositeCase]] = defaultdict(list)

    for case in cases:
        groups[
            case.strength.label
        ].append(case)

    for label in (
        "WEAK",
        "MEDIUM",
        "STRONG",
    ):

        group = groups.get(label, [])

        print()
        print(
            f"{label:8s} N={len(group)}"
        )

        for minutes in HOLD_MINUTES:

            returns = [
                c.hold_returns[minutes]
                for c in group
                if c.hold_returns[minutes] is not None
            ]

            if not returns:
                continue

            exit_better = sum(
                1 for x in returns if x < 0
            )

            hold_better = sum(
                1 for x in returns if x > 0
            )

            print(
                f"  HOLD {minutes:>2}m "
                f"N={len(returns):>2} "
                f"EXIT={exit_better:>2} "
                f"HOLD={hold_better:>2} "
                f"AVG={pct_text(avg(returns))}"
            )


def direction_summary(
    cases: Sequence[OppositeCase],
) -> None:

    print()
    print("=" * 90)
    print("V5.6.12.8 — DIRECTION SUMMARY")
    print("=" * 90)

    for direction in (
        "LONG",
        "SHORT",
    ):

        group = [
            c
            for c in cases
            if c.direction == direction
        ]

        print()
        print(
            f"{direction} N={len(group)}"
        )

        for minutes in HOLD_MINUTES:

            returns = [
                c.hold_returns[minutes]
                for c in group
                if c.hold_returns[minutes] is not None
            ]

            if not returns:
                continue

            exit_better = sum(
                1 for x in returns if x < 0
            )

            hold_better = sum(
                1 for x in returns if x > 0
            )

            print(
                f"  HOLD {minutes:>2}m "
                f"EXIT={exit_better:>2} "
                f"HOLD={hold_better:>2} "
                f"AVG={pct_text(avg(returns))}"
            )


def evidence_summary(
    cases: Sequence[OppositeCase],
) -> None:

    print()
    print("=" * 90)
    print("V5.6.12.8 — EVIDENCE COMPONENT SUMMARY")
    print("=" * 90)

    groups = {
        "STRUCTURE_ONLY": [
            c for c in cases
            if c.strength.structure
            and c.strength.consecutive < MEDIUM_CONSECUTIVE
        ],
        "CANDLE_CONFIRMED": [
            c for c in cases
            if not c.strength.structure
            and c.strength.consecutive >= MEDIUM_CONSECUTIVE
        ],
        "BOTH": [
            c for c in cases
            if c.strength.structure
            and c.strength.consecutive >= MEDIUM_CONSECUTIVE
        ],
    }

    for name, group in groups.items():

        print()
        print(
            f"{name:18s} N={len(group)}"
        )

        for minutes in HOLD_MINUTES:

            returns = [
                c.hold_returns[minutes]
                for c in group
                if c.hold_returns[minutes] is not None
            ]

            if not returns:
                continue

            print(
                f"  HOLD {minutes:>2}m "
                f"AVG={pct_text(avg(returns))}"
            )


# ============================================================
# DETAILED CASE REPORT
# ============================================================

def print_case(case: OppositeCase) -> None:

    print("-" * 90)

    print(
        f"{case.symbol:5s} "
        f"{case.direction:5s} "
        f"OPPOSITE +{case.checkpoint_minutes}m"
    )

    print(
        f"  WARNING:       "
        f"{case.warning_time}"
    )

    print(
        f"  THESIS BROKEN: "
        f"{case.broken_time}"
    )

    print(
        f"  OPPOSITE:      "
        f"{case.opposite_time}"
    )

    print(
        f"  OFFICIAL:      "
        f"{case.official_time}"
    )

    print(
        f"  WARNING LEAD:  "
        f"{case.warning_lead:.1f}m"
        if case.warning_lead is not None
        else "  WARNING LEAD:  NA"
    )

    print(
        f"  OPPOSITE LEAD: "
        f"{case.opposite_lead:.1f}m"
        if case.opposite_lead is not None
        else "  OPPOSITE LEAD: NA"
    )

    print(
        f"  DECISION PRICE: "
        f"{case.decision_price:.4f}"
        if case.decision_price is not None
        else "  DECISION PRICE: NA"
    )

    print()

    print(
        f"  STRENGTH:       "
        f"{case.strength.label}"
    )

    print(
        f"  SCORE:          "
        f"{case.strength.score:.2f}"
    )

    print(
        f"  OPP STRUCTURE:  "
        f"{case.strength.structure}"
    )

    print(
        f"  OPP CONSECUTIVE:"
        f" {case.strength.consecutive}"
    )

    print(
        f"  OPP MOVE:       "
        f"{pct_text(case.strength.move_pct)}"
    )

    print(
        f"  OLD DAMAGE:     "
        f"{pct_text(case.strength.old_damage_pct)}"
    )

    print(
        f"  ACCELERATION:   "
        f"{pct_text(case.strength.acceleration_pct)}"
    )

    print(
        f"  RSI:            "
        f"{case.strength.rsi:.2f}"
        if case.strength.rsi is not None
        else "  RSI:            NA"
    )

    print(
        f"  MA DISTANCE:    "
        f"{pct_text(case.strength.ma_distance_pct)}"
    )

    print(
        f"  REASONS:        "
        f"{', '.join(case.strength.reasons)}"
    )

    print()

    for minutes in HOLD_MINUTES:

        ret = case.hold_returns[minutes]
        label = case.hold_labels[minutes]
        mae = case.hold_mae[minutes]
        mfe = case.hold_mfe[minutes]

        print(
            f"  HOLD {minutes:>2}m: "
            f"{pct_text(ret):>10} "
            f"{label:7s} "
            f"MAE={pct_text(mae):>10} "
            f"MFE={pct_text(mfe):>10}"
        )



# ============================================================
# V5.6.12.8 — PERSISTENCE / DAMAGE RESEARCH
# ============================================================

def persistent_reversal_profile(
    case: OppositeCase,
) -> Dict[str, bool]:
    """
    V5.6.12.8 research classification.

    This deliberately avoids the composite V5.6.12.7
    strength score.

    We ask whether the OLD trend is being persistently
    damaged by the opposite move.

    All inputs are known at the decision point.

    Future returns are NOT used here.
    """

    structure = bool(case.strength.structure)

    consecutive = case.strength.consecutive
    move = abs(case.strength.move_pct or 0.0)
    damage = case.strength.old_damage_pct
    acceleration = case.strength.acceleration_pct or 0.0

    return {
        "STRUCTURE": structure,

        "PERSISTENT_3":
            consecutive >= 3,

        "PERSISTENT_4":
            consecutive >= 4,

        "MOVE_035":
            move >= 0.35,

        "MOVE_050":
            move >= 0.50,

        "DAMAGE_035":
            damage >= 0.35,

        "DAMAGE_050":
            damage >= 0.50,

        "DAMAGE_075":
            damage >= 0.75,

        "ACCELERATION":
            acceleration >= 0.20,

        # ----------------------------------------------------
        # Candidate reversal conditions
        # ----------------------------------------------------

        "CANDIDATE_A":
            structure
            and consecutive >= 3
            and damage >= 0.35,

        "CANDIDATE_B":
            consecutive >= 3
            and move >= 0.35
            and damage >= 0.35,

        "CANDIDATE_C":
            structure
            and consecutive >= 3
            and move >= 0.35
            and damage >= 0.35,

        "CANDIDATE_D":
            consecutive >= 4
            and move >= 0.50
            and damage >= 0.50,

        "CANDIDATE_E":
            structure
            and damage >= 0.50
            and acceleration >= 0.20,
    }


def persistent_reversal_summary(
    cases: Sequence[OppositeCase],
) -> None:
    """
    Evaluate V5.6.12.8 candidate conditions.

    Negative old-direction return means:
        EXIT at the decision point was better.

    Positive old-direction return means:
        HOLD was better.
    """

    print()
    print("=" * 90)
    print("V5.6.12.8 — PERSISTENCE / DAMAGE SUMMARY")
    print("=" * 90)

    candidates = [
        "CANDIDATE_A",
        "CANDIDATE_B",
        "CANDIDATE_C",
        "CANDIDATE_D",
        "CANDIDATE_E",
    ]

    for candidate in candidates:

        group = [
            case
            for case in cases
            if persistent_reversal_profile(case).get(
                candidate,
                False,
            )
        ]

        print()
        print(
            f"{candidate:12s} N={len(group)}"
        )

        if not group:
            continue

        for minutes in HOLD_MINUTES:

            returns = [
                case.hold_returns[minutes]
                for case in group
                if case.hold_returns[minutes] is not None
            ]

            if not returns:
                continue

            exit_better = sum(
                1
                for value in returns
                if value < 0
            )

            hold_better = sum(
                1
                for value in returns
                if value > 0
            )

            print(
                f"  HOLD {minutes:>2}m "
                f"N={len(returns):>2} "
                f"EXIT={exit_better:>2} "
                f"HOLD={hold_better:>2} "
                f"AVG={pct_text(avg(returns))} "
                f"MEDIAN={pct_text(median(returns))}"
            )


def component_summary_12_8(
    cases: Sequence[OppositeCase],
) -> None:

    print()
    print("=" * 90)
    print("V5.6.12.8 — INDIVIDUAL COMPONENTS")
    print("=" * 90)

    components = [
        "STRUCTURE",
        "PERSISTENT_3",
        "PERSISTENT_4",
        "MOVE_035",
        "MOVE_050",
        "DAMAGE_035",
        "DAMAGE_050",
        "DAMAGE_075",
        "ACCELERATION",
    ]

    for component in components:

        group = [
            case
            for case in cases
            if persistent_reversal_profile(case).get(
                component,
                False,
            )
        ]

        print()
        print(
            f"{component:18s} N={len(group)}"
        )

        for minutes in HOLD_MINUTES:

            returns = [
                case.hold_returns[minutes]
                for case in group
                if case.hold_returns[minutes] is not None
            ]

            if not returns:
                continue

            exit_better = sum(
                1
                for value in returns
                if value < 0
            )

            hold_better = sum(
                1
                for value in returns
                if value > 0
            )

            print(
                f"  {minutes:>2}m "
                f"EXIT={exit_better:>2} "
                f"HOLD={hold_better:>2} "
                f"AVG={pct_text(avg(returns))}"
            )


def profile_case_summary(
    cases: Sequence[OppositeCase],
) -> None:

    print()
    print("=" * 90)
    print("V5.6.12.8 — REVERSAL PROFILES")
    print("=" * 90)

    for case in cases:

        profile = persistent_reversal_profile(case)

        active = [
            name
            for name in (
                "STRUCTURE",
                "PERSISTENT_3",
                "PERSISTENT_4",
                "MOVE_035",
                "MOVE_050",
                "DAMAGE_035",
                "DAMAGE_050",
                "DAMAGE_075",
                "ACCELERATION",
                "CANDIDATE_A",
                "CANDIDATE_B",
                "CANDIDATE_C",
                "CANDIDATE_D",
                "CANDIDATE_E",
            )
            if profile.get(name, False)
        ]

        print(
            f"{case.symbol:5s} "
            f"{case.direction:5s} "
            f"score={case.strength.score:>4.1f} "
            f"15m={pct_text(case.hold_returns[15]):>9} "
            f"30m={pct_text(case.hold_returns[30]):>9} "
            f"45m={pct_text(case.hold_returns[45]):>9} "
            f"60m={pct_text(case.hold_returns[60]):>9}"
        )

        print(
            "  PROFILE: "
            + (
                ", ".join(active)
                if active
                else "NONE"
            )
        )


# ============================================================
# MAIN DATA PIPELINE
# ============================================================

def process_symbol(
    symbol: str,
) -> Tuple[
    int,
    int,
    int,
    List[OppositeCase],
]:

    # --------------------------------------------------------
    # Load the exact V5.6.12.2 research data.
    # --------------------------------------------------------

    rows_30m = v125.base.load_rows(
        symbol,
        "30m",
    )

    rows_5m = v125.base.load_rows(
        symbol,
        "5m",
    )

    transitions = (
        v125.base.build_directional_transitions(
            symbol,
            rows_30m,
        )
    )

    observations = (
        v125.base.build_warning_observations(
            symbol,
            rows_5m,
        )
    )

    episodes = (
        v125.base.cluster_warning_episodes(
            observations,
        )
    )

    # --------------------------------------------------------
    # V5.6.12.2 returns:
    #
    #     (transition, episode)
    #
    # Convert each pair into the Assignment object expected
    # by V5.6.12.5.
    # --------------------------------------------------------

    raw_assignments = (
        v125.base.assign_one_episode_per_transition(
            transitions,
            episodes,
        )
    )

    assignments = []

    for item in raw_assignments:

        if item is None:
            continue

        transition, episode = item

        lead = (
            transition.timestamp
            - episode.first_timestamp
        ).total_seconds() / 60.0

        assignment = v125.base.Assignment(
            transition,
            episode,
            lead,
        )

        assignments.append(assignment)

    # --------------------------------------------------------
    # Evaluate the assignments.
    # --------------------------------------------------------

    cases: List[OppositeCase] = []

    for assignment in assignments:

        case = evaluate_assignment(
            rows_5m,
            assignment,
        )

        if case is None:
            continue

        if case.opposite_time is None:
            continue

        cases.append(case)

    return (
        len(transitions),
        len(episodes),
        len(assignments),
        cases,
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "KISS V5.6.12.7 opposite-transition "
            "strength research"
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

    print()
    print("#" * 90)
    print(
        "KISS V5.6.12.8 — PERSISTENT REVERSAL TEST"
    )
    print("#" * 90)
    print()
    print(
        "RESEARCH ONLY — NO ENGINE CHANGES"
    )
    print(
        "NO ORDERS / NO DB WRITES"
    )
    print(
        "V5.6.12.2 ONE-TO-ONE ASSIGNMENT PRESERVED"
    )
    print(
        "FIRST CAUSAL OPPOSITE TRANSITION"
    )
    print(
        "STRENGTH = STRUCTURE + PERSISTENCE + MOVE "
        "+ DAMAGE + ACCELERATION + CONTEXT"
    )
    print()

    total_transitions = 0
    total_episodes = 0
    total_assignments = 0

    all_cases: List[OppositeCase] = []

    per_symbol = {}

    # --------------------------------------------------------
    # SYMBOL LOOP
    # --------------------------------------------------------

    for symbol in args.symbols:

        try:

            (
                transitions_count,
                episodes_count,
                assignments_count,
                cases,
            ) = process_symbol(symbol)

            total_transitions += transitions_count
            total_episodes += episodes_count
            total_assignments += assignments_count

            all_cases.extend(cases)

            per_symbol[symbol] = {
                "transitions": transitions_count,
                "episodes": episodes_count,
                "assignments": assignments_count,
                "opposite": len(cases),
            }

            print(
                f"[{symbol}] "
                f"transitions={transitions_count} "
                f"episodes={episodes_count} "
                f"assignments={assignments_count} "
                f"opposite_cases={len(cases)}"
            )

        except Exception as exc:

            print()
            print(
                f"[{symbol}] LOAD / PROCESS ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

    # --------------------------------------------------------
    # GLOBAL AUDIT
    # --------------------------------------------------------

    print()
    print("#" * 90)
    print("GLOBAL RESULTS")
    print("#" * 90)

    print(
        f"KNOWN DIRECTIONAL TRANSITIONS: "
        f"{total_transitions}"
    )

    print(
        f"WARNING EPISODES:               "
        f"{total_episodes}"
    )

    print(
        f"UNIQUELY ASSIGNED TRANSITIONS:  "
        f"{total_assignments}"
    )

    print(
        f"FIRST OPPOSITE CASES:            "
        f"{len(all_cases)}"
    )

    # --------------------------------------------------------
    # ONE-TO-ONE AUDIT
    # --------------------------------------------------------

    transition_keys = []
    warning_keys = []

    for case in all_cases:

        transition_keys.append(
            (
                case.symbol,
                case.direction,
                case.official_time,
            )
        )

        warning_keys.append(
            (
                case.symbol,
                case.direction,
                case.warning_time,
            )
        )

    transition_duplicates = (
        len(transition_keys)
        - len(set(transition_keys))
    )

    warning_duplicates = (
        len(warning_keys)
        - len(set(warning_keys))
    )

    print()
    print("#" * 90)
    print(
        "V5.6.12.7 — OPPOSITE CASE AUDIT"
    )
    print("#" * 90)

    print(
        f"OPPOSITE CASES:       "
        f"{len(all_cases)}"
    )

    print(
        f"UNIQUE TRANSITIONS:   "
        f"{len(set(transition_keys))}"
    )

    print(
        f"UNIQUE WARNINGS:      "
        f"{len(set(warning_keys))}"
    )

    print(
        f"DUPLICATE TRANSITIONS:"
        f" {transition_duplicates}"
    )

    print(
        f"DUPLICATE WARNINGS:   "
        f"{warning_duplicates}"
    )

    if (
        transition_duplicates == 0
        and warning_duplicates == 0
    ):
        print(
            "OK: strict one-transition <-> "
            "one-warning assignment preserved."
        )
    else:
        print(
            "WARNING: duplicate assignment detected."
        )

    # --------------------------------------------------------
    # STRENGTH
    # --------------------------------------------------------

    strength_summary(
        all_cases,
    )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    direction_summary(
        all_cases,
    )

    # --------------------------------------------------------
    # EVIDENCE
    # --------------------------------------------------------

    evidence_summary(
        all_cases,
    )

    # --------------------------------------------------------
    # LEAD SUMMARY
    # --------------------------------------------------------

    print()
    print("#" * 90)
    print(
        "V5.6.12.8 — OPPOSITE LEAD"
    )
    print("#" * 90)

    leads = [
        c.opposite_lead
        for c in all_cases
        if c.opposite_lead is not None
    ]

    early = [
        x
        for x in leads
        if x > 0
    ]

    at_official = [
        x
        for x in leads
        if x == 0
    ]

    after = [
        x
        for x in leads
        if x < 0
    ]

    print(
        f"OPPOSITE CASES:        "
        f"{len(leads)}"
    )

    print(
        f"BEFORE OFFICIAL:       "
        f"{len(early)}"
    )

    print(
        f"AT OFFICIAL:           "
        f"{len(at_official)}"
    )

    print(
        f"AFTER OFFICIAL:        "
        f"{len(after)}"
    )

    if early:
        print(
            f"EARLY AVG LEAD:        "
            f"{avg(early):.1f}m"
        )

        print(
            f"EARLY MEDIAN LEAD:     "
            f"{median(early):.1f}m"
        )

    # --------------------------------------------------------
    # DETAILED CASES
    # --------------------------------------------------------

    print()
    print("#" * 90)
    print(
        "V5.6.12.8 — FIRST OPPOSITE CASES"
    )
    print("#" * 90)

    for case in all_cases:
        print_case(case)

    # --------------------------------------------------------
    # V5.6.12.8 — PERSISTENCE / DAMAGE RESEARCH
    # --------------------------------------------------------

    persistent_reversal_summary(
        all_cases,
    )

    component_summary_12_8(
        all_cases,
    )

    profile_case_summary(
        all_cases,
    )

    # --------------------------------------------------------
    # INTERPRETATION
    # --------------------------------------------------------

    print()
    print("#" * 90)
    print(
        "V5.6.12.7 — INTERPRETATION"
    )
    print("#" * 90)

    print(
        """
This is a research experiment, not a trading rule.

The V5.6.12.2 one-to-one assignment methodology is preserved.

The decision point is the FIRST causal
OPPOSITE_TRANSITION detected by V5.6.12.5.

V5.6.12.7 adds a transparent strength classification:

    WEAK
    MEDIUM
    STRONG

Strength is based only on information available at the
opposite-transition decision point.

The future HOLD returns are evaluation labels only.

Negative HOLD return:
    exiting at the decision point would have been better.

Positive HOLD return:
    holding would have been better.

The important research question is NOT:

    "Can we predict every reversal?"

It is:

    "Does stronger opposite evidence correspond to a
     higher probability that continuing to hold the old
     direction is harmful?"

If STRONG cases consistently show worse subsequent
old-direction returns than WEAK cases, strength may be useful
as a future decision layer.

If the groups do not separate, the strength model should not
be used as an exit rule.

DO NOT change the live KISS engine from this experiment alone.
"""
    )

    print()
    print("#" * 90)
    print(
        "V5.6.12.8 — ANALYSIS COMPLETE"
    )
    print("#" * 90)


if __name__ == "__main__":
    main()