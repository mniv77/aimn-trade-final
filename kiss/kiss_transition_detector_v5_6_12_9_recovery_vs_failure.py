"""
KISS V5.6.12.9 — RECOVERY vs CONTINUED FAILURE
================================================

RESEARCH ONLY.

Purpose
-------
V5.6.12.8 tested whether opposite-transition strength could
distinguish real reversals from temporary counter-moves.

The result was NOT clean enough for a trading rule.

V5.6.12.9 asks the next question:

    After the first causal opposite transition appears,
    does the OLD trend recover or does it continue failing?

The research deliberately separates:

    RECOVERY
    CONTINUED FAILURE

at several post-decision checkpoints:

    +15m
    +30m
    +45m
    +60m

The decision point itself is inherited from V5.6.12.8:

    FIRST THESIS_BROKEN
            |
            v
    FIRST CAUSAL OPPOSITE_TRANSITION
            |
            v
    DECISION POINT

No future information is used to classify the decision point.

Future candles are used ONLY to evaluate what happened
after the decision.

IMPORTANT
---------
The V5.6.12.2 one-to-one assignment methodology is preserved.

This file imports the complete V5.6.12.8 research pipeline
rather than rebuilding or duplicating it.

NO ORDERS.
NO DB WRITES.
NO ENGINE CHANGES.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import kiss_transition_detector_v5_6_12_8_persistent_reversal as v128


# ============================================================
# CONFIGURATION
# ============================================================

CHECKPOINT_MINUTES = (15, 30, 45, 60)

# Minimum recovery in the OLD direction.
RECOVERY_MIN_MOVE_PCT = 0.10

# Minimum fraction of post-decision 5m candles moving
# favorably for the OLD direction.
RECOVERY_MIN_FAVORABLE_RATIO = 0.50

# Continued-failure test.
FAILURE_MIN_MOVE_PCT = 0.20
FAILURE_MIN_CONSECUTIVE = 3


# ============================================================
# RESULT STRUCTURE
# ============================================================

@dataclass
class RecoveryFailureCheckpoint:
    minutes: int

    old_direction_return: Optional[float]

    recovery: bool
    continued_failure: bool

    favorable_ratio: Optional[float]
    max_adverse_consecutive: int

    mae: Optional[float]
    mfe: Optional[float]


@dataclass
class RecoveryFailureCase:
    symbol: str
    direction: str

    warning_time: Optional[datetime]
    broken_time: Optional[datetime]
    opposite_time: Optional[datetime]
    official_time: Optional[datetime]

    opposite_lead: Optional[float]

    decision_price: Optional[float]

    checkpoints: Dict[
        int,
        RecoveryFailureCheckpoint,
    ]


# ============================================================
# BASIC HELPERS
# ============================================================

def row_close(row) -> Optional[float]:
    return v128.row_close(row)


def close_time(row) -> Optional[datetime]:
    return v128.close_time(row)


def find_close_index(
    rows: Sequence,
    target: datetime,
) -> Optional[int]:
    return v128.find_close_index(rows, target)


def signed_return(
    start_price: Optional[float],
    end_price: Optional[float],
    direction: str,
) -> Optional[float]:

    return v128.signed_return(
        start_price,
        end_price,
        direction,
    )


# ============================================================
# POST-DECISION PATH ANALYSIS
# ============================================================

def analyze_checkpoint(
    rows_5m: Sequence,
    decision_idx: int,
    direction: str,
    minutes: int,
) -> Optional[RecoveryFailureCheckpoint]:

    bars = minutes // 5

    target_idx = decision_idx + bars

    if target_idx >= len(rows_5m):
        return None

    start_price = row_close(
        rows_5m[decision_idx]
    )

    end_price = row_close(
        rows_5m[target_idx]
    )

    old_return = signed_return(
        start_price,
        end_price,
        direction,
    )

    favorable = 0
    total = 0

    consecutive_adverse = 0
    max_adverse_consecutive = 0

    minimum = 0.0
    maximum = 0.0

    if start_price is None:
        return None

    for idx in range(
        decision_idx + 1,
        target_idx + 1,
    ):

        previous = row_close(
            rows_5m[idx - 1]
        )

        current = row_close(
            rows_5m[idx]
        )

        if previous is None or current is None:
            continue

        move = signed_return(
            previous,
            current,
            direction,
        )

        if move is None:
            continue

        total += 1

        if move >= 0:
            favorable += 1
            consecutive_adverse = 0
        else:
            consecutive_adverse += 1

            max_adverse_consecutive = max(
                max_adverse_consecutive,
                consecutive_adverse,
            )

        from_decision = signed_return(
            start_price,
            current,
            direction,
        )

        if from_decision is not None:
            minimum = min(
                minimum,
                from_decision,
            )

            maximum = max(
                maximum,
                from_decision,
            )

    favorable_ratio = (
        favorable / total
        if total
        else None
    )

    recovery = bool(
        old_return is not None
        and old_return >= RECOVERY_MIN_MOVE_PCT
        and favorable_ratio is not None
        and favorable_ratio >= RECOVERY_MIN_FAVORABLE_RATIO
    )

    continued_failure = bool(
        (
            old_return is not None
            and old_return <= -FAILURE_MIN_MOVE_PCT
        )
        or
        max_adverse_consecutive >= FAILURE_MIN_CONSECUTIVE
    )

    return RecoveryFailureCheckpoint(
        minutes=minutes,
        old_direction_return=old_return,
        recovery=recovery,
        continued_failure=continued_failure,
        favorable_ratio=favorable_ratio,
        max_adverse_consecutive=max_adverse_consecutive,
        mae=minimum,
        mfe=maximum,
    )


# ============================================================
# CONVERT V5.6.12.8 CASE
# ============================================================

def build_case(
    rows_5m: Sequence,
    case: v128.OppositeCase,
) -> Optional[RecoveryFailureCase]:

    if case.opposite_time is None:
        return None

    decision_idx = find_close_index(
        rows_5m,
        case.opposite_time,
    )

    if decision_idx is None:
        return None

    checkpoints: Dict[
        int,
        RecoveryFailureCheckpoint,
    ] = {}

    for minutes in CHECKPOINT_MINUTES:

        result = analyze_checkpoint(
            rows_5m,
            decision_idx,
            case.direction,
            minutes,
        )

        if result is not None:
            checkpoints[minutes] = result

    if not checkpoints:
        return None

    return RecoveryFailureCase(
        symbol=case.symbol,
        direction=case.direction,
        warning_time=case.warning_time,
        broken_time=case.broken_time,
        opposite_time=case.opposite_time,
        official_time=case.official_time,
        opposite_lead=case.opposite_lead,
        decision_price=case.decision_price,
        checkpoints=checkpoints,
    )


# ============================================================
# SUMMARY
# ============================================================

def pct_text(
    value: Optional[float],
) -> str:

    if value is None:
        return "NA"

    return f"{value:+.3f}%"


def average(
    values: Sequence[float],
) -> Optional[float]:

    if not values:
        return None

    return sum(values) / len(values)


def median(
    values: Sequence[float],
) -> Optional[float]:

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


def print_checkpoint_summary(
    cases: Sequence[RecoveryFailureCase],
) -> None:

    print()
    print("=" * 90)
    print(
        "V5.6.12.9 — RECOVERY vs CONTINUED FAILURE"
    )
    print("=" * 90)

    print(
        f"CASES={len(cases)}"
    )

    for minutes in CHECKPOINT_MINUTES:

        group = [
            case.checkpoints[minutes]
            for case in cases
            if minutes in case.checkpoints
        ]

        recovery = [
            x for x in group
            if x.recovery
        ]

        failure = [
            x for x in group
            if x.continued_failure
        ]

        returns = [
            x.old_direction_return
            for x in group
            if x.old_direction_return is not None
        ]

        print(
            f"{minutes:>2}m "
            f"N={len(group):>2} "
            f"RECOVERY={len(recovery):>2} "
            f"FAILURE={len(failure):>2} "
            f"AVG_OLD_RETURN={pct_text(average(returns))} "
            f"MEDIAN={pct_text(median(returns))}"
        )


# ============================================================
# DIRECTION SUMMARY
# ============================================================

def print_direction_summary(
    cases: Sequence[RecoveryFailureCase],
) -> None:

    print()
    print("=" * 90)
    print(
        "V5.6.12.9 — DIRECTION SUMMARY"
    )
    print("=" * 90)

    for direction in (
        "LONG",
        "SHORT",
    ):

        group = [
            case
            for case in cases
            if case.direction == direction
        ]

        print()
        print(
            f"{direction} N={len(group)}"
        )

        for minutes in CHECKPOINT_MINUTES:

            points = [
                case.checkpoints[minutes]
                for case in group
                if minutes in case.checkpoints
            ]

            recovery = sum(
                x.recovery
                for x in points
            )

            failure = sum(
                x.continued_failure
                for x in points
            )

            returns = [
                x.old_direction_return
                for x in points
                if x.old_direction_return is not None
            ]

            print(
                f"  {minutes:>2}m "
                f"RECOVERY={recovery:>2} "
                f"FAILURE={failure:>2} "
                f"AVG={pct_text(average(returns))}"
            )


# ============================================================
# RECOVERY / FAILURE EXCLUSIVITY
# ============================================================

def print_state_summary(
    cases: Sequence[RecoveryFailureCase],
) -> None:

    print()
    print("=" * 90)
    print(
        "V5.6.12.9 — STATE SEPARATION"
    )
    print("=" * 90)

    for minutes in CHECKPOINT_MINUTES:

        points = [
            case.checkpoints[minutes]
            for case in cases
            if minutes in case.checkpoints
        ]

        recovery_only = sum(
            x.recovery
            and not x.continued_failure
            for x in points
        )

        failure_only = sum(
            x.continued_failure
            and not x.recovery
            for x in points
        )

        both = sum(
            x.recovery
            and x.continued_failure
            for x in points
        )

        neither = sum(
            not x.recovery
            and not x.continued_failure
            for x in points
        )

        print(
            f"{minutes:>2}m "
            f"RECOVERY_ONLY={recovery_only:>2} "
            f"FAILURE_ONLY={failure_only:>2} "
            f"BOTH={both:>2} "
            f"NEITHER={neither:>2}"
        )


# ============================================================
# CASE REPORT
# ============================================================

def print_case(
    case: RecoveryFailureCase,
) -> None:

    print("-" * 90)

    print(
        f"{case.symbol:5s} "
        f"{case.direction:5s} "
        f"OPPOSITE={case.opposite_time}"
    )

    print(
        f"  OFFICIAL: "
        f"{case.official_time}"
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

    for minutes in CHECKPOINT_MINUTES:

        point = case.checkpoints.get(
            minutes
        )

        if point is None:
            continue

        ratio = (
            f"{point.favorable_ratio:.2f}"
            if point.favorable_ratio is not None
            else "NA"
        )

        print(
            f"  +{minutes:>2}m "
            f"RETURN={pct_text(point.old_direction_return):>9} "
            f"RECOVERY={str(point.recovery):5s} "
            f"FAILURE={str(point.continued_failure):5s} "
            f"FAV_RATIO={ratio:>4} "
            f"MAX_ADV_CONSEC={point.max_adverse_consecutive:>2} "
            f"MAE={pct_text(point.mae):>9} "
            f"MFE={pct_text(point.mfe):>9}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser()

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

    all_cases: List[
        RecoveryFailureCase
    ] = []

    total_known = 0
    total_assignments = 0
    total_opposite = 0

    print("=" * 90)
    print(
        "KISS V5.6.12.9 — RECOVERY vs CONTINUED FAILURE"
    )
    print("=" * 90)

    print(
        "RESEARCH ONLY"
    )

    print(
        "NO ORDERS / NO DB WRITES / NO ENGINE CHANGES"
    )

    for symbol in args.symbols:

        rows_5m = v128.v125.base.load_rows(
            symbol,
            "5m",
        )

        rows_30m = v128.v125.base.load_rows(
            symbol,
            "30m",
        )

        if not rows_5m or not rows_30m:
            print(
                f"{symbol}: NO DATA"
            )
            continue

        transitions = (
            v128.v125.base
            .build_directional_transitions(
                symbol,
                rows_30m,
            )
        )

        observations = (
            v128.v125.base
            .build_warning_observations(
                symbol,
                rows_5m,
            )
        )

        episodes = (
            v128.v125.base
            .cluster_warning_episodes(
                observations,
            )
        )

        assignments = (
            v128.v125.base
            .assign_one_episode_per_transition(
                transitions,
                episodes,
            )
        )

        total_known += len(transitions)
        total_assignments += len(assignments)

        symbol_cases = 0

        for transition, episode in assignments:

            assignment = (
                v128.v125.base.Assignment(
                    transition,
                    episode,
                    (
                        transition.timestamp
                        - episode.first_timestamp
                    ).total_seconds()
                    / 60.0,
                )
            )

            case = v128.evaluate_assignment(
                rows_5m,
                assignment,
            )

            if case is None:
                continue

            total_opposite += 1

            new_case = build_case(
                rows_5m,
                case,
            )

            if new_case is None:
                continue

            all_cases.append(
                new_case
            )

            symbol_cases += 1

        print(
            f"{symbol}: "
            f"transitions={len(transitions)} "
            f"assignments={len(assignments)} "
            f"opposite_cases={symbol_cases}"
        )

    print()
    print("=" * 90)
    print("AUDIT")
    print("=" * 90)

    print(
        f"KNOWN DIRECTIONAL TRANSITIONS: "
        f"{total_known}"
    )

    print(
        f"ONE-TO-ONE ASSIGNMENTS: "
        f"{total_assignments}"
    )

    print(
        f"OPPOSITE CASES: "
        f"{len(all_cases)}"
    )

    unique_keys = {
        (
            case.symbol,
            case.direction,
            case.opposite_time,
        )
        for case in all_cases
    }

    duplicate_count = (
        len(all_cases)
        - len(unique_keys)
    )

    print(
        f"DUPLICATE CASES: "
        f"{duplicate_count}"
    )

    if duplicate_count != 0:
        raise RuntimeError(
            "AUDIT FAILED: duplicate opposite cases"
        )

    print(
        "AUDIT STATUS: PASSED"
    )

    print_checkpoint_summary(
        all_cases
    )

    print_direction_summary(
        all_cases
    )

    print_state_summary(
        all_cases
    )

    print()
    print("=" * 90)
    print(
        "V5.6.12.9 — DETAILED CASES"
    )
    print("=" * 90)

    for case in all_cases:
        print_case(case)

    print()
    print("=" * 90)
    print(
        "V5.6.12.9 — INTERPRETATION"
    )
    print("=" * 90)

    print(
        """
This is a research experiment, not a trading rule.

The V5.6.12.2 one-to-one assignment methodology is preserved.

The decision point is inherited from V5.6.12.8:

    FIRST THESIS_BROKEN
            |
            v
    FIRST CAUSAL OPPOSITE_TRANSITION
            |
            v
    DECISION

V5.6.12.9 does NOT ask whether the opposite transition
is "strong."

Instead it asks what happens AFTER that decision point.

RECOVERY means:

    old-direction return >= recovery threshold
    AND
    at least half of the post-decision candles
    moved favorably for the old direction.

CONTINUED FAILURE means:

    old-direction return <= failure threshold
    OR
    at least the configured number of consecutive
    adverse candles occurred.

These classifications intentionally may overlap.

Future behavior is used ONLY for evaluation.

The research question is:

    Can recovery separate temporary counter-moves
    from genuine continuation of the reversal?

If recovery cases consistently recover while failure cases
continue producing materially negative old-direction returns,
that may justify a future decision layer.

If they overlap heavily, recovery/failure is not sufficient
and we should continue researching the causal transition
itself.

DO NOT change the live KISS engine from this experiment alone.
"""
    )

    print()
    print("=" * 90)
    print(
        "V5.6.12.9 — ANALYSIS COMPLETE"
    )
    print("=" * 90)


if __name__ == "__main__":
    main()
