 # kiss_transition_detector_v5_6_12_3_1_survive_deteriorate_reverse.py <<'PY'
"""
KISS V5.6.12.3.1
SURVIVE / UNDER_PRESSURE / THESIS_BROKEN

Research only.
No DB writes.
No orders.
No live-engine changes.

IMPORTANT:
The front half deliberately reuses the exact V5.6.12.2 methodology:

    5m causal warning observations
        ->
    15m warning episodes
        ->
    one-to-one transition/episode assignment

This version adds only a post-warning research layer.

Question:
After the first assigned warning appears, can we distinguish:

    SURVIVE       = original trend recovers
    DETERIORATE   = original trend remains under pressure
    REVERSE       = opposite trend structure is developing

using only information available by +15/+30/+45/+60 minutes?

The future NEXT60 outcome is measured separately and is never used
to determine the state at the checkpoint.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import kiss_transition_detector_v5_6_12_2_survival_vs_true_deterioration as base


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

CHECKPOINTS = (15, 30, 45, 60)

# Research thresholds only.
# These are deliberately simple and transparent.
REVERSE_MIN_CONSECUTIVE = 2
REVERSE_MIN_MOVE_PCT = 0.20
DETERIORATE_MIN_MOVE_PCT = 0.20


# ============================================================
# RESULT STRUCTURES
# ============================================================

@dataclass
class ReverseCheckpoint:
    checkpoint_minutes: int
    state: str

    # Evidence available by checkpoint.
    signed_return_from_warning: Optional[float]
    min_signed_from_warning: Optional[float]
    max_signed_from_warning: Optional[float]

    favorable_bars: int
    adverse_bars: int
    consecutive_adverse: int
    structure_break: bool

    opposite_structure: bool
    opposite_consecutive: int
    opposite_move_pct: Optional[float]

    # Strictly future outcome after checkpoint.
    next60_outcome: Optional[str]
    next60_return: Optional[float]


# ============================================================
# BASIC HELPERS
# ============================================================

def pct_change(a: float, b: float) -> Optional[float]:
    if a is None or b is None or a == 0:
        return None
    return (b - a) / a * 100.0


def signed_return(a: float, b: float, direction: str) -> Optional[float]:
    raw = pct_change(a, b)
    if raw is None:
        return None
    return raw if direction == "LONG" else -raw


def close_time(row) -> datetime:
    return base.candle_close_time(row)


def find_close_index(rows: Sequence, target: datetime) -> Optional[int]:
    return base.find_close_index(rows, target)


# ============================================================
# PATH / STRUCTURE EVIDENCE
# ============================================================

def path_evidence(
    rows: Sequence,
    start_idx: int,
    end_idx: int,
    direction: str,
) -> Tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    int,
    int,
    int,
]:
    """
    Measure only the path available between warning and checkpoint.
    """

    if end_idx <= start_idx:
        return None, None, None, 0, 0, 0

    start_price = rows[start_idx].close

    signed = signed_return(
        start_price,
        rows[end_idx].close,
        direction,
    )

    minimum = 0.0
    maximum = 0.0

    favorable = 0
    adverse = 0
    consecutive = 0
    max_consecutive = 0

    for idx in range(start_idx + 1, end_idx + 1):
        raw = pct_change(
            rows[idx - 1].close,
            rows[idx].close,
        )

        if raw is None:
            continue

        move = raw if direction == "LONG" else -raw

        from_warning = signed_return(
            start_price,
            rows[idx].close,
            direction,
        )

        if from_warning is not None:
            minimum = min(minimum, from_warning)
            maximum = max(maximum, from_warning)

        if move >= 0:
            favorable += 1
            consecutive = 0
        else:
            adverse += 1
            consecutive += 1
            max_consecutive = max(
                max_consecutive,
                consecutive,
            )

    return (
        signed,
        minimum,
        maximum,
        favorable,
        adverse,
        max_consecutive,
    )


def opposite_direction(direction: str) -> str:
    return "SHORT" if direction == "LONG" else "LONG"


def opposite_evidence(
    rows: Sequence,
    start_idx: int,
    end_idx: int,
    old_direction: str,
) -> Tuple[bool, int, Optional[float]]:
    """
    Determine whether opposite-direction evidence has developed
    by the checkpoint.

    This uses ONLY candles from warning through checkpoint.

    Reverse evidence requires:
      1. at least two consecutive candles moving against the
         original direction, AND
      2. total adverse movement from the warning of at least
         REVERSE_MIN_MOVE_PCT,

    OR an explicit opposite structure break.

    The purpose is NOT to predict the future perfectly.
    The purpose is to determine whether a genuine reversal
    candidate is already visible.
    """

    if end_idx <= start_idx:
        return False, 0, None

    direction = opposite_direction(old_direction)

    consecutive = 0
    max_consecutive = 0

    for idx in range(start_idx + 1, end_idx + 1):
        raw = pct_change(
            rows[idx - 1].close,
            rows[idx].close,
        )

        if raw is None:
            continue

        move = raw if direction == "LONG" else -raw

        if move > 0:
            consecutive += 1
            max_consecutive = max(
                max_consecutive,
                consecutive,
            )
        else:
            consecutive = 0

    total_move = signed_return(
        rows[start_idx].close,
        rows[end_idx].close,
        direction,
    )

    # Use the same structural machinery already used by V5.6.12.2.
    try:
        structure = base.structure_break_for_direction(
            rows,
            end_idx,
            direction,
            base.CONTINUATION_STRUCTURE_BARS,
        )
    except TypeError:
        try:
            structure = base.structure_break_for_direction(
                rows,
                end_idx,
                direction,
            )
        except Exception:
            structure = False
    except Exception:
        structure = False

    reverse = (
        structure
        or (
            max_consecutive >= REVERSE_MIN_CONSECUTIVE
            and total_move is not None
            and total_move >= REVERSE_MIN_MOVE_PCT
        )
    )

    return reverse, max_consecutive, total_move


# ============================================================
# STATE CLASSIFICATION
# ============================================================

def classify_state(
    old_direction: str,
    signed_from_warning: Optional[float],
    min_signed: Optional[float],
    favorable_bars: int,
    adverse_bars: int,
    consecutive_adverse: int,
    old_structure_break: bool,
    opposite_structure: bool,
    opposite_consecutive: int,
    opposite_move_pct: Optional[float],
) -> str:
    """
    V5.6.12.4 — THESIS BROKEN experiment.

    Three-way state:

        SURVIVE
        UNDER_PRESSURE
        THESIS_BROKEN

    IMPORTANT:
        Opposite-direction evidence is NOT sufficient by itself
        to declare the original trade thesis broken.

    The question is:

        "Has the original trend thesis itself failed?"

    For the original direction to be THESIS_BROKEN we require
    meaningful adverse movement together with persistent adverse
    behavior and a break of the original structure.

    This is research only.
    """

    # --------------------------------------------------------
    # THESIS BROKEN
    # --------------------------------------------------------
    #
    # A thesis break requires ALL THREE:
    #
    #   1. meaningful adverse displacement
    #   2. persistent adverse behavior
    #   3. original structure broken
    #
    # This deliberately does NOT use opposite_structure,
    # opposite_consecutive, or opposite_move_pct.
    #
    meaningful_adverse = (
        signed_from_warning is not None
        and signed_from_warning <= -0.20
    )

    persistent_adverse = (
        adverse_bars > favorable_bars
        or consecutive_adverse >= 3
    )

    thesis_broken = (
        meaningful_adverse
        and persistent_adverse
        and old_structure_break
    )

    if thesis_broken:
        return "THESIS_BROKEN"

    # --------------------------------------------------------
    # SURVIVE
    # --------------------------------------------------------
    #
    # The original trend is recovering or holding together.
    #
    recovery = (
        signed_from_warning is not None
        and signed_from_warning >= 0.10
        and favorable_bars >= adverse_bars
        and (
            min_signed is None
            or min_signed > -0.75
        )
    )

    if recovery:
        return "SURVIVE"

    # --------------------------------------------------------
    # UNDER PRESSURE
    # --------------------------------------------------------
    #
    # Something is wrong, but the original thesis has NOT yet
    # met the full broken-thesis requirement.
    #
    return "UNDER_PRESSURE"


# ============================================================
# FUTURE OUTCOME
# ============================================================

def future_outcome(
    rows: Sequence,
    checkpoint_idx: int,
    direction: str,
) -> Tuple[Optional[str], Optional[float]]:
    """
    Future-only evaluation.

    Nothing after the checkpoint is used by state classification.
    """

    target = (
        close_time(rows[checkpoint_idx])
        + timedelta(
            minutes=base.OUTCOME_MINUTES
        )
    )

    end_idx = find_close_index(
        rows,
        target,
    )

    if end_idx is None or end_idx <= checkpoint_idx:
        return None, None

    ret = signed_return(
        rows[checkpoint_idx].close,
        rows[end_idx].close,
        direction,
    )

    if ret is None:
        return None, None

    threshold = base.OUTCOME_THRESHOLD_PCT

    if ret <= -threshold:
        return "GOOD", ret

    if ret >= threshold:
        return "FALSE", ret

    return "NEUTRAL", ret


# ============================================================
# ASSIGNMENT EVALUATION
# ============================================================

def evaluate_assignment(
    rows_5m: Sequence,
    assignment,
) -> List[ReverseCheckpoint]:

    warning = assignment.episode.first

    warning_idx = find_close_index(
        rows_5m,
        warning.timestamp,
    )

    if warning_idx is None:
        return []

    results: List[ReverseCheckpoint] = []

    for minutes in CHECKPOINTS:

        target_time = (
            warning.timestamp
            + timedelta(minutes=minutes)
        )

        checkpoint_idx = find_close_index(
            rows_5m,
            target_time,
        )

        if (
            checkpoint_idx is None
            or checkpoint_idx <= warning_idx
        ):
            continue

        (
            signed_from_warning,
            min_signed,
            max_signed,
            favorable,
            adverse,
            consecutive,
        ) = path_evidence(
            rows_5m,
            warning_idx,
            checkpoint_idx,
            assignment.transition.direction,
        )

        # Existing V5.6.12.2 old-trend structure evidence.
        try:
            old_structure = base.structure_break_for_direction(
                rows_5m,
                checkpoint_idx,
                assignment.transition.direction,
                base.CONTINUATION_STRUCTURE_BARS,
            )
        except TypeError:
            try:
                old_structure = base.structure_break_for_direction(
                    rows_5m,
                    checkpoint_idx,
                    assignment.transition.direction,
                )
            except Exception:
                old_structure = False
        except Exception:
            old_structure = False

        (
            opp_structure,
            opp_consecutive,
            opp_move,
        ) = opposite_evidence(
            rows_5m,
            warning_idx,
            checkpoint_idx,
            assignment.transition.direction,
        )

        state = classify_state(
            assignment.transition.direction,
            signed_from_warning,
            min_signed,
            favorable,
            adverse,
            consecutive,
            old_structure,
            opp_structure,
            opp_consecutive,
            opp_move,
        )

        next60_outcome, next60_return = future_outcome(
            rows_5m,
            checkpoint_idx,
            assignment.transition.direction,
        )

        results.append(
            ReverseCheckpoint(
                checkpoint_minutes=minutes,
                state=state,
                signed_return_from_warning=signed_from_warning,
                min_signed_from_warning=min_signed,
                max_signed_from_warning=max_signed,
                favorable_bars=favorable,
                adverse_bars=adverse,
                consecutive_adverse=consecutive,
                structure_break=old_structure,
                opposite_structure=opp_structure,
                opposite_consecutive=opp_consecutive,
                opposite_move_pct=opp_move,
                next60_outcome=next60_outcome,
                next60_return=next60_return,
            )
        )

    return results


# ============================================================
# SYMBOL ANALYSIS
# ============================================================

def analyze_symbol(symbol: str):
    rows_30m = base.load_rows(
        symbol,
        "30m",
    )

    rows_5m = base.load_rows(
        symbol,
        "5m",
    )

    transitions = base.build_directional_transitions(
        symbol,
        rows_30m,
    )

    observations = base.build_warning_observations(
        symbol,
        rows_5m,
    )

    episodes = base.cluster_warning_episodes(
        observations,
    )

    raw_assignments = base.assign_one_episode_per_transition(
        transitions,
        episodes,
    )

    assignments = []
    results_by_assignment = {}

    for transition, episode in raw_assignments:

        lead = (
            transition.timestamp
            - episode.first_timestamp
        ).total_seconds() / 60.0

        assignment = base.Assignment(
            transition,
            episode,
            lead,
        )

        evaluated = evaluate_assignment(
            rows_5m,
            assignment,
        )

        if not evaluated:
            continue

        key = (
            transition.symbol,
            transition.timestamp,
            transition.direction,
        )

        assignments.append(assignment)
        results_by_assignment[key] = evaluated

    print(
        f"\n[{symbol}] "
        f"30m={len(rows_30m):,} "
        f"5m={len(rows_5m):,} "
        f"transitions={len(transitions):3d} "
        f"episodes={len(episodes):3d} "
        f"assigned={len(assignments):3d} "
        f"checkpoints="
        f"{sum(len(v) for v in results_by_assignment.values()):3d}"
    )

    return (
        transitions,
        episodes,
        assignments,
        results_by_assignment,
    )


# ============================================================
# REPORTING
# ============================================================

def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{value:.3f}%"


def report_uniqueness(assignments):

    print("\n" + "=" * 90)
    print("UNIQUE ONE-TO-ONE ASSIGNMENT AUDIT")
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

    tc = Counter(transition_keys)
    ec = Counter(episode_keys)

    print(
        f"ASSIGNMENTS:             {len(assignments)}"
    )
    print(
        f"UNIQUE TRANSITIONS:      {len(set(transition_keys))}"
    )
    print(
        f"UNIQUE WARNING EPISODES: {len(set(episode_keys))}"
    )
    print(
        f"DUPLICATE TRANSITIONS:   "
        f"{sum(v > 1 for v in tc.values())}"
    )
    print(
        f"DUPLICATE EPISODES:      "
        f"{sum(v > 1 for v in ec.values())}"
    )

    if (
        len(transition_keys)
        == len(set(transition_keys))
        and len(episode_keys)
        == len(set(episode_keys))
    ):
        print(
            "OK: strict one-transition <-> "
            "one-warning assignment."
        )
    else:
        print(
            "ERROR: one-to-one assignment violation."
        )


def all_results(results_by_assignment):

    output = []

    for key, values in results_by_assignment.items():
        output.extend(values)

    return output


def report_checkpoint_summary(results):

    print("\n" + "=" * 90)
    print(
        "SURVIVE / UNDER_PRESSURE / THESIS_BROKEN — "
        "CHECKPOINT TEST"
    )
    print("=" * 90)

    for checkpoint in CHECKPOINTS:

        rows = [
            r
            for r in results
            if r.checkpoint_minutes == checkpoint
        ]

        state_counts = Counter(
            r.state
            for r in rows
        )

        outcome_counts = Counter(
            r.next60_outcome
            for r in rows
            if r.next60_outcome
        )

        returns = [
            r.next60_return
            for r in rows
            if r.next60_return is not None
        ]

        avg = (
            sum(returns) / len(returns)
            if returns
            else None
        )

        n = len(rows)

        def pct(numerator):
            return (
                numerator / n * 100.0
                if n
                else 0.0
            )

        print(
            f"\n+{checkpoint:2d}m "
            f"N={n:3d}"
        )

        print(
            f"  SURVIVE      "
            f"{state_counts['SURVIVE']:3d}"
            f" ({pct(state_counts['SURVIVE']):5.1f}%)"
        )

        print(
            f"  UNDER_PRESSURE "
            f"{state_counts['UNDER_PRESSURE']:3d}"
            f" ({pct(state_counts['UNDER_PRESSURE']):5.1f}%)"
        )

        print(
            f"  THESIS_BROKEN  "
            f"{state_counts['THESIS_BROKEN']:3d}"
            f" ({pct(state_counts['THESIS_BROKEN']):5.1f}%)"
        )

        print(
            f"  NEXT60 GOOD  "
            f"{outcome_counts['GOOD']:3d}"
            f" ({pct(outcome_counts['GOOD']):5.1f}%)"
        )

        print(
            f"  NEXT60 FALSE "
            f"{outcome_counts['FALSE']:3d}"
            f" ({pct(outcome_counts['FALSE']):5.1f}%)"
        )

        print(
            f"  NEXT60 NEUT  "
            f"{outcome_counts['NEUTRAL']:3d}"
            f" ({pct(outcome_counts['NEUTRAL']):5.1f}%)"
        )

        print(
            f"  AVG NEXT60   {fmt_pct(avg)}"
        )


def report_state_vs_future(results):

    print("\n" + "=" * 90)
    print("STATE -> FUTURE OUTCOME")
    print("=" * 90)

    for checkpoint in CHECKPOINTS:

        print(
            f"\n+{checkpoint}m"
        )

        for state in (
            "SURVIVE",
            "UNDER_PRESSURE",
            "THESIS_BROKEN",
        ):

            rows = [
                r
                for r in results
                if (
                    r.checkpoint_minutes
                    == checkpoint
                    and r.state
                    == state
                    and r.next60_outcome
                    is not None
                )
            ]

            if not rows:
                print(
                    f"  {state:12s} N=0"
                )
                continue

            good = sum(
                r.next60_outcome == "GOOD"
                for r in rows
            )

            false = sum(
                r.next60_outcome == "FALSE"
                for r in rows
            )

            neutral = sum(
                r.next60_outcome == "NEUTRAL"
                for r in rows
            )

            returns = [
                r.next60_return
                for r in rows
                if r.next60_return is not None
            ]

            avg = (
                sum(returns) / len(returns)
                if returns
                else None
            )

            n = len(rows)

            print(
                f"  {state:12s} "
                f"N={n:3d} "
                f"GOOD={good:3d} "
                f"({good/n*100:5.1f}%) "
                f"FALSE={false:3d} "
                f"({false/n*100:5.1f}%) "
                f"NEUT={neutral:3d} "
                f"AVG60={fmt_pct(avg)}"
            )


def report_thesis_broken_evidence(results):
    print("=" * 90)
    print("THESIS BROKEN EVIDENCE")
    print("=" * 90)

    for checkpoint in CHECKPOINTS:
        rows = [
            r for r in results
            if r.checkpoint_minutes == checkpoint
        ]

        broken = [
            r for r in rows
            if r.state == "THESIS_BROKEN"
        ]

        non_broken = [
            r for r in rows
            if r.state != "THESIS_BROKEN"
        ]

        good_broken = sum(
            1 for r in broken
            if r.next60_outcome == "GOOD"
        )
        false_broken = sum(
            1 for r in broken
            if r.next60_outcome == "FALSE"
        )

        good_non = sum(
            1 for r in non_broken
            if r.next60_outcome == "GOOD"
        )
        false_non = sum(
            1 for r in non_broken
            if r.next60_outcome == "FALSE"
        )

        print(
            f"  +{checkpoint:02d}m   "
            f"THESIS_BROKEN: N={len(broken)} "
            f"GOOD={good_broken} "
            f"FALSE={false_broken}"
        )
        print(
            f"           NOT_BROKEN:   N={len(non_broken)} "
            f"GOOD={good_non} "
            f"FALSE={false_non}"
        )


def report_direction(
    results_by_assignment,
    assignments,
):

    print("\n" + "=" * 90)
    print("DIRECTIONAL REVERSE TEST")
    print("=" * 90)

    for direction in (
        "LONG",
        "SHORT",
    ):

        keys = {
            (
                a.transition.symbol,
                a.transition.timestamp,
                a.transition.direction,
            )
            for a in assignments
            if a.transition.direction == direction
        }

        rows = []

        for key in keys:
            rows.extend(
                results_by_assignment.get(
                    key,
                    [],
                )
            )

        print(
            f"\n{direction}"
        )

        for checkpoint in CHECKPOINTS:

            subset = [
                r
                for r in rows
                if r.checkpoint_minutes == checkpoint
            ]

            states = Counter(
                r.state
                for r in subset
            )

            print(
                f"  +{checkpoint:2d}m "
                f"N={len(subset):3d} "
                f"SURVIVE={states['SURVIVE']:3d} "
                f"UNDER_PRESSURE={states['UNDER_PRESSURE']:3d} "
                f"THESIS_BROKEN={states['THESIS_BROKEN']:3d}"
            )


def report_examples(
    assignments,
    results_by_assignment,
    limit=30,
):

    print("\n" + "=" * 90)
    print("REPRESENTATIVE THESIS-BROKEN CASES")
    print("=" * 90)

    examples = []

    for assignment in assignments:

        key = (
            assignment.transition.symbol,
            assignment.transition.timestamp,
            assignment.transition.direction,
        )

        for result in results_by_assignment.get(
            key,
            [],
        ):

            if result.state == "THESIS_BROKEN":
                examples.append(
                    (
                        assignment,
                        result,
                    )
                )

    examples.sort(
        key=lambda x: (
            x[0].transition.symbol,
            x[0].transition.timestamp,
            x[1].checkpoint_minutes,
        )
    )

    for assignment, result in examples[:limit]:

        warning = assignment.episode.first

        print(
            f"\n{assignment.transition.symbol:5s} "
            f"{assignment.transition.direction:5s} "
            f"REVERSE "
            f"+{result.checkpoint_minutes}m"
        )

        print(
            f"  WARNING: "
            f"{warning.timestamp}"
        )

        print(
            f"  T0:      "
            f"{assignment.transition.timestamp}"
        )

        print(
            f"  LEAD:    "
            f"{assignment.lead_minutes:.1f}m"
        )

        print(
            f"  OLD RET: "
            f"{fmt_pct(result.signed_return_from_warning)}"
        )

        print(
            f"  MIN:     "
            f"{fmt_pct(result.min_signed_from_warning)}"
        )

        print(
            f"  MAX:     "
            f"{fmt_pct(result.max_signed_from_warning)}"
        )

        print(
            f"  OPP STR: "
            f"{result.opposite_structure}"
        )

        print(
            f"  OPP CON: "
            f"{result.opposite_consecutive}"
        )

        print(
            f"  OPP MOVE:"
            f" {fmt_pct(result.opposite_move_pct)}"
        )

        print(
            f"  NEXT60:  "
            f"{result.next60_outcome} "
            f"{fmt_pct(result.next60_return)}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "KISS V5.6.12.3.1 "
            "survive/deteriorate/reverse research"
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
    all_results_by_assignment = {}

    print("\n" + "#" * 90)
    print(
        "KISS V5.6.12.3.1 — "
        "SURVIVE / UNDER_PRESSURE / THESIS_BROKEN"
    )
    print("#" * 90)

    print(
        "Research only — "
        "no DB writes / no orders / no engine changes."
    )

    print(
        "FRONT END: exact V5.6.12.2 "
        "warning -> 15m episode -> one-to-one assignment"
    )

    print(
        f"SYMBOLS: {', '.join(args.symbols)}"
    )

    print(
        f"CHECKPOINTS: {CHECKPOINTS}m | "
        f"NEXT OUTCOME: {base.OUTCOME_MINUTES}m"
    )

    for symbol in args.symbols:

        try:

            (
                transitions,
                episodes,
                assignments,
                results_by_assignment,
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

            all_results_by_assignment.update(
                results_by_assignment
            )

        except Exception as exc:

            print(
                f"[{symbol}] ERROR: {exc}"
            )

    results = all_results(
        all_results_by_assignment
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
        f"TRANSITIONS WITHOUT ASSIGNMENT: "
        f"{len(all_transitions) - len(all_assignments)}"
    )

    report_uniqueness(
        all_assignments
    )

    report_checkpoint_summary(
        results
    )

    report_state_vs_future(
        results
    )

    report_thesis_broken_evidence(
        results
    )

    report_direction(
        all_results_by_assignment,
        all_assignments,
    )

    report_examples(
        all_assignments,
        all_results_by_assignment,
    )

    print("\n" + "#" * 90)
    print("V5.6.12.4 INTERPRETATION")
    print("#" * 90)

    print(
        "This is a research test, not a trading rule."
    )

    print(
        "The V5.6.12.2 one-to-one assignment methodology "
        "is preserved."
    )

    print(
        "State classification uses only information "
        "available through each checkpoint."
    )

    print(
        "NEXT60 is strictly future evaluation."
    )

    print(
        "REVERSE requires opposite-direction evidence; "
        "a warning alone is not treated as a reversal."
    )

    print(
        "Do NOT change the live KISS engine from this run alone."
    )


if __name__ == "__main__":
    main()
