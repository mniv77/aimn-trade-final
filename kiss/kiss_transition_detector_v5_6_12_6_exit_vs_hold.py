#!/usr/bin/env python3
"""
KISS V5.6.12.6 — EXIT vs HOLD at First Causal Opposite Transition
=================================================================

RESEARCH ONLY.

This experiment does NOT:
- change the live trading engine
- place orders
- modify KISS execution
- modify RSI
- modify trailing
- modify stop loss
- write to the database
- make live trading decisions

QUESTION
--------
At the FIRST causal OPPOSITE_TRANSITION after THESIS_BROKEN:

    EXIT NOW
        vs
    HOLD 15m
    HOLD 30m
    HOLD 45m
    HOLD 60m

Which decision produces the better result?

METHODOLOGY
-----------
The V5.6.12.2 one-to-one assignment methodology is preserved:

    transition
        ->
    own pre-transition warning window
        ->
    one warning episode
        ->
    one transition assignment

V5.6.12.5 is then used to identify:

    WARNING
        ->
    THESIS_BROKEN
        ->
    FIRST CAUSAL OPPOSITE_TRANSITION

IMPORTANT
---------
The decision point uses ONLY information available at that checkpoint.

Future candles are used ONLY to evaluate what would have happened
after the decision.

The experiment is therefore:

    EXIT NOW = 0% incremental return after decision

versus:

    HOLD 15m = signed old-direction return over next 15m
    HOLD 30m = signed old-direction return over next 30m
    HOLD 45m = signed old-direction return over next 45m
    HOLD 60m = signed old-direction return over next 60m

Positive return = holding the ORIGINAL trade direction was better.

Negative return = exiting at the opposite-transition checkpoint
would have been better.

The accrued P&L before the decision is identical for all choices,
so the experiment compares only the decision made at that moment.

No engine behavior is changed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional, Sequence, Tuple

import kiss_transition_detector_v5_6_12_5_recovery_opposite_transition as v125


# ============================================================
# CONFIGURATION
# ============================================================

SYMBOLS = [
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "TSLA",
    "SPY",
    "QQQ",
]

HOLD_WINDOWS = (15, 30, 45, 60)

EXPECTED_MIN_OPPOSITE_CASES = 1


# ============================================================
# RESULT STRUCTURE
# ============================================================

@dataclass
class ExitHoldCase:
    symbol: str
    direction: str

    warning_time: object
    official_transition_time: object
    opposite_time: object

    warning_lead_minutes: float
    opposite_lead_minutes: float

    opposite_checkpoint_minutes: int

    opposite_structure: bool
    opposite_consecutive: int
    opposite_move_pct: Optional[float]

    decision_price: float

    exit_return: float

    hold15: Optional[float]
    hold30: Optional[float]
    hold45: Optional[float]
    hold60: Optional[float]

    mae15: Optional[float]
    mae30: Optional[float]
    mae45: Optional[float]
    mae60: Optional[float]

    mfe15: Optional[float]
    mfe30: Optional[float]
    mfe45: Optional[float]
    mfe60: Optional[float]


# ============================================================
# BASIC HELPERS
# ============================================================

def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.3f}%"


def signed_return(
    a: float,
    b: float,
    direction: str,
) -> Optional[float]:
    if a is None or b is None or a == 0:
        return None

    raw = (b - a) / a * 100.0

    if direction == "LONG":
        return raw

    if direction == "SHORT":
        return -raw

    return None


def close_time(row):
    return v125.close_time(row)


def find_close_index(
    rows: Sequence,
    target,
) -> Optional[int]:
    return v125.find_close_index(rows, target)


# ============================================================
# HOLD PATH
# ============================================================

def hold_path(
    rows: Sequence,
    decision_idx: int,
    direction: str,
    minutes: int,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Evaluate what happens after the opposite-transition decision.

    Returns:

        final signed return
        close-based MAE
        close-based MFE

    MAE/MFE are measured in the ORIGINAL trade direction.

    No candles before the decision are included.
    """

    if decision_idx is None:
        return None, None, None

    target = (
        close_time(rows[decision_idx])
        + timedelta(minutes=minutes)
    )

    end_idx = find_close_index(rows, target)

    if end_idx is None or end_idx <= decision_idx:
        return None, None, None

    start_price = rows[decision_idx].close

    final_return = signed_return(
        start_price,
        rows[end_idx].close,
        direction,
    )

    if final_return is None:
        return None, None, None

    minimum = 0.0
    maximum = 0.0

    for idx in range(decision_idx + 1, end_idx + 1):

        value = signed_return(
            start_price,
            rows[idx].close,
            direction,
        )

        if value is None:
            continue

        minimum = min(minimum, value)
        maximum = max(maximum, value)

    return (
        final_return,
        minimum,
        maximum,
    )


# ============================================================
# FIRST CAUSAL OPPOSITE TRANSITION
# ============================================================

def first_opposite_checkpoint(
    rows_5m,
    assignment,
):
    """
    Run the existing V5.6.12.5 causal analysis and locate
    the FIRST checkpoint where:

        path_opposite_transition == True

    Only checkpoints AFTER the first THESIS_BROKEN point
    are eligible.

    The V5.6.12.5 classifier itself is not changed.
    """

    checkpoints = v125.evaluate_assignment(
        rows_5m,
        assignment,
    )

    broken_minutes = None

    for result in checkpoints:

        if result.state == "THESIS_BROKEN":
            broken_minutes = result.checkpoint_minutes
            break

    if broken_minutes is None:
        return None, checkpoints

    for result in checkpoints:

        if result.checkpoint_minutes <= broken_minutes:
            continue

        if not getattr(
            result,
            "path_opposite_transition",
            False,
        ):
            continue

        target_time = (
            assignment.episode.first_timestamp
            + timedelta(
                minutes=result.checkpoint_minutes
            )
        )

        decision_idx = find_close_index(
            rows_5m,
            target_time,
        )

        if decision_idx is None:
            continue

        return (
            result,
            checkpoints,
        )

    return None, checkpoints


# ============================================================
# BUILD ONE CASE
# ============================================================

def build_case(
    rows_5m,
    assignment,
) -> Optional[ExitHoldCase]:

    result, checkpoints = first_opposite_checkpoint(
        rows_5m,
        assignment,
    )

    if result is None:
        return None

    decision_time = (
        assignment.episode.first_timestamp
        + timedelta(
            minutes=result.checkpoint_minutes
        )
    )

    decision_idx = find_close_index(
        rows_5m,
        decision_time,
    )

    if decision_idx is None:
        return None

    decision_price = rows_5m[decision_idx].close

    direction = assignment.transition.direction

    hold15, mae15, mfe15 = hold_path(
        rows_5m,
        decision_idx,
        direction,
        15,
    )

    hold30, mae30, mfe30 = hold_path(
        rows_5m,
        decision_idx,
        direction,
        30,
    )

    hold45, mae45, mfe45 = hold_path(
        rows_5m,
        decision_idx,
        direction,
        45,
    )

    hold60, mae60, mfe60 = hold_path(
        rows_5m,
        decision_idx,
        direction,
        60,
    )

    opposite_lead = (
        assignment.transition.timestamp
        - decision_time
    ).total_seconds() / 60.0

    return ExitHoldCase(
        symbol=assignment.transition.symbol,
        direction=direction,

        warning_time=assignment.episode.first_timestamp,
        official_transition_time=assignment.transition.timestamp,
        opposite_time=decision_time,

        warning_lead_minutes=assignment.lead_minutes,
        opposite_lead_minutes=opposite_lead,

        opposite_checkpoint_minutes=result.checkpoint_minutes,

        opposite_structure=getattr(
            result,
            "path_opposite_structure",
            False,
        ),

        opposite_consecutive=getattr(
            result,
            "path_opposite_consecutive",
            0,
        ),

        opposite_move_pct=getattr(
            result,
            "path_opposite_move_pct",
            None,
        ),

        decision_price=decision_price,

        exit_return=0.0,

        hold15=hold15,
        hold30=hold30,
        hold45=hold45,
        hold60=hold60,

        mae15=mae15,
        mae30=mae30,
        mae45=mae45,
        mae60=mae60,

        mfe15=mfe15,
        mfe30=mfe30,
        mfe45=mfe45,
        mfe60=mfe60,
    )


# ============================================================
# LOAD / ASSIGN
# ============================================================

def analyze_symbol(symbol: str):

    rows_30m = v125.base.load_rows(
        symbol,
        "30m",
    )

    rows_5m = v125.base.load_rows(
        symbol,
        "5m",
    )

    transitions = v125.base.build_directional_transitions(
        symbol,
        rows_30m,
    )

    observations = v125.base.build_warning_observations(
        symbol,
        rows_5m,
    )

    episodes = v125.base.cluster_warning_episodes(
        observations,
    )

    raw_assignments = (
        v125.base.assign_one_episode_per_transition(
            transitions,
            episodes,
        )
    )

    assignments = []

    for transition, episode in raw_assignments:

        lead = (
            transition.timestamp
            - episode.first_timestamp
        ).total_seconds() / 60.0

        assignment = v125.base.Assignment(
            transition,
            episode,
            lead,
        )

        assignments.append(
            assignment
        )

    cases = []

    for assignment in assignments:

        try:
            case = build_case(
                rows_5m,
                assignment,
            )

            if case is not None:
                cases.append(case)

        except Exception as exc:
            print(
                f"[{symbol}] case error: {exc}"
            )

    print(
        f"[{symbol}] "
        f"30m={len(rows_30m):,} "
        f"5m={len(rows_5m):,} "
        f"transitions={len(transitions):3d} "
        f"episodes={len(episodes):3d} "
        f"assignments={len(assignments):3d} "
        f"opposite_cases={len(cases):3d}"
    )

    return (
        transitions,
        episodes,
        assignments,
        cases,
    )


# ============================================================
# ASSIGNMENT AUDIT
# ============================================================

def report_assignment_audit(
    assignments,
):

    print("\n" + "=" * 90)
    print(
        "V5.6.12.6 — ONE-TO-ONE ASSIGNMENT AUDIT"
    )
    print("=" * 90)

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

    duplicate_transitions = sum(
        value > 1
        for value in transition_counts.values()
    )

    duplicate_episodes = sum(
        value > 1
        for value in episode_counts.values()
    )

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
        f"{duplicate_transitions}"
    )

    print(
        f"DUPLICATE EPISODES:      "
        f"{duplicate_episodes}"
    )

    if (
        duplicate_transitions == 0
        and duplicate_episodes == 0
    ):
        print(
            "OK: strict one-transition <-> "
            "one-warning assignment."
        )
    else:
        print(
            "ERROR: one-to-one assignment "
            "violation."
        )


# ============================================================
# DECISION SUMMARY
# ============================================================

def decision_stats(
    cases: Sequence[ExitHoldCase],
    window: int,
):

    values = []

    for case in cases:

        value = getattr(
            case,
            f"hold{window}",
        )

        if value is not None:
            values.append(value)

    if not values:
        return None

    exit_better = sum(
        value < 0
        for value in values
    )

    hold_better = sum(
        value > 0
        for value in values
    )

    ties = sum(
        value == 0
        for value in values
    )

    avg = (
        sum(values) / len(values)
    )

    sorted_values = sorted(values)

    middle = len(sorted_values) // 2

    if len(sorted_values) % 2:
        median = sorted_values[middle]
    else:
        median = (
            sorted_values[middle - 1]
            + sorted_values[middle]
        ) / 2.0

    return {
        "n": len(values),
        "exit_better": exit_better,
        "hold_better": hold_better,
        "ties": ties,
        "avg": avg,
        "median": median,
        "min": min(values),
        "max": max(values),
    }


# ============================================================
# GLOBAL EXIT vs HOLD
# ============================================================

def report_exit_vs_hold(
    cases: Sequence[ExitHoldCase],
):

    print("\n" + "=" * 90)
    print(
        "V5.6.12.6 — EXIT NOW vs HOLD"
    )
    print("=" * 90)

    print(
        "Decision point = FIRST causal "
        "OPPOSITE_TRANSITION."
    )

    print(
        "EXIT NOW = 0% incremental return."
    )

    print(
        "Negative HOLD return = EXIT NOW "
        "would have been better."
    )

    print(
        "Positive HOLD return = HOLDING "
        "would have been better."
    )

    print()

    for window in HOLD_WINDOWS:

        stats = decision_stats(
            cases,
            window,
        )

        if stats is None:
            print(
                f"HOLD {window:2d}m: N=0"
            )
            continue

        print(
            f"HOLD {window:2d}m "
            f"N={stats['n']:2d} "
            f"EXIT_BETTER={stats['exit_better']:2d} "
            f"HOLD_BETTER={stats['hold_better']:2d} "
            f"TIE={stats['ties']:2d} "
            f"AVG={fmt_pct(stats['avg'])} "
            f"MEDIAN={fmt_pct(stats['median'])} "
            f"MIN={fmt_pct(stats['min'])} "
            f"MAX={fmt_pct(stats['max'])}"
        )


# ============================================================
# DIRECTIONAL SPLIT
# ============================================================

def report_directional(
    cases: Sequence[ExitHoldCase],
):

    print("\n" + "=" * 90)
    print(
        "V5.6.12.6 — DIRECTIONAL EXIT vs HOLD"
    )
    print("=" * 90)

    for direction in (
        "LONG",
        "SHORT",
    ):

        subset = [
            c
            for c in cases
            if c.direction == direction
        ]

        print()
        print(
            f"{direction} "
            f"N={len(subset)}"
        )

        for window in HOLD_WINDOWS:

            stats = decision_stats(
                subset,
                window,
            )

            if stats is None:
                print(
                    f"  HOLD {window:2d}m N=0"
                )
                continue

            print(
                f"  HOLD {window:2d}m "
                f"N={stats['n']:2d} "
                f"EXIT={stats['exit_better']:2d} "
                f"HOLD={stats['hold_better']:2d} "
                f"TIE={stats['ties']:2d} "
                f"AVG={fmt_pct(stats['avg'])}"
            )


# ============================================================
# EVIDENCE TYPE SPLIT
# ============================================================

def evidence_type(case: ExitHoldCase) -> str:

    structure = bool(
        case.opposite_structure
    )

    candle = (
        case.opposite_consecutive >=
        v125.OPPOSITE_MIN_CONSECUTIVE
        and
        case.opposite_move_pct is not None
        and
        case.opposite_move_pct >=
        v125.OPPOSITE_MIN_MOVE_PCT
    )

    if structure and candle:
        return "BOTH"

    if structure:
        return "STRUCTURE_ONLY"

    if candle:
        return "CANDLE_CONFIRMED"

    return "OTHER"


def report_evidence_split(
    cases: Sequence[ExitHoldCase],
):

    print("\n" + "=" * 90)
    print(
        "V5.6.12.6 — OPPOSITE EVIDENCE TYPE"
    )
    print("=" * 90)

    groups = {
        "STRUCTURE_ONLY": [],
        "CANDLE_CONFIRMED": [],
        "BOTH": [],
        "OTHER": [],
    }

    for case in cases:
        groups[
            evidence_type(case)
        ].append(case)

    for name in (
        "STRUCTURE_ONLY",
        "CANDLE_CONFIRMED",
        "BOTH",
        "OTHER",
    ):

        subset = groups[name]

        print()
        print(
            f"{name:18s} "
            f"N={len(subset)}"
        )

        for window in HOLD_WINDOWS:

            stats = decision_stats(
                subset,
                window,
            )

            if stats is None:
                continue

            print(
                f"  HOLD {window:2d}m "
                f"EXIT={stats['exit_better']:2d} "
                f"HOLD={stats['hold_better']:2d} "
                f"AVG={fmt_pct(stats['avg'])}"
            )


# ============================================================
# EXCURSION SUMMARY
# ============================================================

def report_excursions(
    cases: Sequence[ExitHoldCase],
):

    print("\n" + "=" * 90)
    print(
        "V5.6.12.6 — MAE / MFE AFTER DECISION"
    )
    print("=" * 90)

    for window in HOLD_WINDOWS:

        maes = []
        mfes = []

        for case in cases:

            mae = getattr(
                case,
                f"mae{window}",
            )

            mfe = getattr(
                case,
                f"mfe{window}",
            )

            if mae is not None:
                maes.append(mae)

            if mfe is not None:
                mfes.append(mfe)

        if not maes:
            continue

        print()
        print(
            f"HOLD {window:2d}m "
            f"N={len(maes):2d}"
        )

        print(
            f"  AVG MAE: "
            f"{fmt_pct(sum(maes) / len(maes))}"
        )

        print(
            f"  AVG MFE: "
            f"{fmt_pct(sum(mfes) / len(mfes))}"
        )

        print(
            f"  WORST MAE: "
            f"{fmt_pct(min(maes))}"
        )

        print(
            f"  BEST MFE: "
            f"{fmt_pct(max(mfes))}"
        )


# ============================================================
# CASE DETAIL
# ============================================================

def report_cases(
    cases: Sequence[ExitHoldCase],
):

    print("\n" + "=" * 90)
    print(
        "V5.6.12.6 — FIRST OPPOSITE TRANSITION CASES"
    )
    print("=" * 90)

    ordered = sorted(
        cases,
        key=lambda c: (
            c.symbol,
            c.official_transition_time,
            c.direction,
        ),
    )

    for case in ordered:

        print("-" * 90)

        print(
            f"{case.symbol:5s} "
            f"{case.direction:5s} "
            f"OPPOSITE +"
            f"{case.opposite_checkpoint_minutes}m"
        )

        print(
            f"  WARNING:   "
            f"{case.warning_time}"
        )

        print(
            f"  OPPOSITE:  "
            f"{case.opposite_time}"
        )

        print(
            f"  OFFICIAL:  "
            f"{case.official_transition_time}"
        )

        print(
            f"  LEAD:      "
            f"{case.opposite_lead_minutes:.1f}m"
        )

        print(
            f"  DECISION PRICE: "
            f"{case.decision_price:.4f}"
        )

        print(
            f"  EVIDENCE: "
            f"{evidence_type(case)}"
        )

        print(
            f"  OPP STR:   "
            f"{case.opposite_structure}"
        )

        print(
            f"  OPP CON:   "
            f"{case.opposite_consecutive}"
        )

        print(
            f"  OPP MOVE:  "
            f"{fmt_pct(case.opposite_move_pct)}"
        )

        print(
            f"  EXIT NOW:  "
            f"{fmt_pct(case.exit_return)}"
        )

        print(
            f"  HOLD 15m:  "
            f"{fmt_pct(case.hold15)} "
            f"MAE={fmt_pct(case.mae15)} "
            f"MFE={fmt_pct(case.mfe15)}"
        )

        print(
            f"  HOLD 30m:  "
            f"{fmt_pct(case.hold30)} "
            f"MAE={fmt_pct(case.mae30)} "
            f"MFE={fmt_pct(case.mfe30)}"
        )

        print(
            f"  HOLD 45m:  "
            f"{fmt_pct(case.hold45)} "
            f"MAE={fmt_pct(case.mae45)} "
            f"MFE={fmt_pct(case.mfe45)}"
        )

        print(
            f"  HOLD 60m:  "
            f"{fmt_pct(case.hold60)} "
            f"MAE={fmt_pct(case.mae60)} "
            f"MFE={fmt_pct(case.mfe60)}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "KISS V5.6.12.6 "
            "EXIT vs HOLD research"
        )
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=SYMBOLS,
    )

    args = parser.parse_args()

    all_transitions = []
    all_episodes = []
    all_assignments = []
    all_cases = []

    print("\n" + "#" * 90)
    print(
        "KISS V5.6.12.6 — EXIT vs HOLD "
        "AT FIRST CAUSAL OPPOSITE TRANSITION"
    )
    print("#" * 90)

    print()
    print(
        "RESEARCH ONLY — NO ENGINE CHANGES"
    )

    print(
        "NO ORDERS / NO DB WRITES / "
        "NO RSI CHANGES / NO TRAILING CHANGES"
    )

    print()
    print(
        "METHODOLOGY:"
    )

    print(
        "  V5.6.12.2 one-to-one "
        "transition -> warning assignment"
    )

    print(
        "  V5.6.12.5 first THESIS_BROKEN"
    )

    print(
        "  first causal OPPOSITE_TRANSITION"
    )

    print(
        "  EXIT NOW vs HOLD 15/30/45/60"
    )

    print()

    for symbol in args.symbols:

        try:

            (
                transitions,
                episodes,
                assignments,
                cases,
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

            all_cases.extend(
                cases
            )

        except Exception as exc:

            print(
                f"[{symbol}] ERROR: {exc}"
            )

    print("\n" + "#" * 90)
    print("GLOBAL RESULTS")
    print("#" * 90)

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

    print(
        f"FIRST OPPOSITE CASES:            "
        f"{len(all_cases)}"
    )

    report_assignment_audit(
        all_assignments
    )

    report_exit_vs_hold(
        all_cases
    )

    report_directional(
        all_cases
    )

    report_evidence_split(
        all_cases
    )

    report_excursions(
        all_cases
    )

    report_cases(
        all_cases
    )

    # --------------------------------------------------------
    # FINAL INTERPRETATION
    # --------------------------------------------------------

    print("\n" + "#" * 90)
    print(
        "V5.6.12.6 — INTERPRETATION"
    )
    print("#" * 90)

    print(
        "This is a research experiment, "
        "not a trading rule."
    )

    print(
        "The V5.6.12.2 one-to-one "
        "assignment methodology is preserved."
    )

    print(
        "The decision point is the FIRST "
        "causal OPPOSITE_TRANSITION."
    )

    print(
        "State classification uses only "
        "information available at the decision."
    )

    print(
        "Future candles are used only "
        "for EXIT-vs-HOLD evaluation."
    )

    print(
        "EXIT NOW means no additional "
        "return after the decision."
    )

    print(
        "Negative HOLD return means "
        "EXIT NOW would have saved value."
    )

    print(
        "Positive HOLD return means "
        "holding would have captured more."
    )

    print(
        "The small opposite-transition "
        "sample must be treated as exploratory."
    )

    print(
        "DO NOT change the live KISS engine "
        "from this experiment alone."
    )

    print("#" * 90)


if __name__ == "__main__":
    main()
