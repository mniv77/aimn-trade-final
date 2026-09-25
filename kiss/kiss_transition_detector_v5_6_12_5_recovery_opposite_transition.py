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
# V5.6.12.5 — THESIS-BROKEN PATH ANALYSIS
# ============================================================

RECOVERY_MIN_MOVE_PCT = 0.10
RECOVERY_MIN_FAVORABLE_RATIO = 0.50

OPPOSITE_MIN_CONSECUTIVE = 3
OPPOSITE_MIN_MOVE_PCT = 0.20


@dataclass
class TransitionPath:
    """
    Causal path after THESIS_BROKEN.

    All path states use candles available at that moment.
    Future outcome is stored separately and is never used
    to classify the path.
    """
    checkpoint_minutes: int
    thesis_broken: bool

    recovery: bool
    continuing_failure: bool

    opposite_structure: bool
    opposite_consecutive: int
    opposite_move_pct: Optional[float]

    opposite_transition: bool

    next60_outcome: Optional[str]
    next60_return: Optional[float]


def recovery_evidence(
    rows: Sequence,
    broken_idx: int,
    checkpoint_idx: int,
    direction: str,
) -> bool:
    """
    Determine whether the original trade thesis is recovering.

    This is deliberately conservative.

    Recovery requires:
      1. positive movement from the THESIS_BROKEN point
      2. at least half of the candles favorable
      3. no continuing severe adverse displacement

    No future candles beyond checkpoint_idx are used.
    """
    if checkpoint_idx <= broken_idx:
        return False

    signed = signed_return(
        rows[broken_idx].close,
        rows[checkpoint_idx].close,
        direction,
    )

    if signed is None or signed < RECOVERY_MIN_MOVE_PCT:
        return False

    favorable = 0
    total = 0

    for idx in range(broken_idx + 1, checkpoint_idx + 1):
        raw = pct_change(
            rows[idx - 1].close,
            rows[idx].close,
        )
        if raw is None:
            continue

        total += 1
        move = raw if direction == "LONG" else -raw

        if move >= 0:
            favorable += 1

    if total == 0:
        return False

    ratio = favorable / total

    return ratio >= RECOVERY_MIN_FAVORABLE_RATIO


def continuing_failure_evidence(
    rows: Sequence,
    broken_idx: int,
    checkpoint_idx: int,
    direction: str,
) -> bool:
    """
    Determine whether the original thesis continues to deteriorate.

    This is independent of opposite-direction recognition.
    """
    if checkpoint_idx <= broken_idx:
        return False

    signed = signed_return(
        rows[broken_idx].close,
        rows[checkpoint_idx].close,
        direction,
    )

    if signed is None:
        return False

    adverse = 0
    favorable = 0
    consecutive = 0
    max_consecutive = 0

    for idx in range(broken_idx + 1, checkpoint_idx + 1):
        raw = pct_change(
            rows[idx - 1].close,
            rows[idx].close,
        )
        if raw is None:
            continue

        move = raw if direction == "LONG" else -raw

        if move < 0:
            adverse += 1
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            favorable += 1
            consecutive = 0

    return (
        signed <= -0.20
        or adverse > favorable
        or max_consecutive >= 3
    )


def opposite_transition_evidence(
    rows: Sequence,
    broken_idx: int,
    checkpoint_idx: int,
    old_direction: str,
) -> Tuple[bool, bool, int, Optional[float]]:
    """
    Test whether a genuine opposite transition is developing.

    A single adverse candle is NOT enough.

    We require:
      - opposite structure, OR
      - at least three consecutive opposite candles
        together with meaningful opposite movement.

    This is intentionally stricter than the old two-candle
    reverse diagnostic.
    """
    if checkpoint_idx <= broken_idx:
        return False, False, 0, None

    new_direction = opposite_direction(old_direction)

    consecutive = 0
    max_consecutive = 0

    for idx in range(broken_idx + 1, checkpoint_idx + 1):
        raw = pct_change(
            rows[idx - 1].close,
            rows[idx].close,
        )
        if raw is None:
            continue

        move = raw if new_direction == "LONG" else -raw

        if move > 0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    move_pct = signed_return(
        rows[broken_idx].close,
        rows[checkpoint_idx].close,
        new_direction,
    )

    try:
        structure = base.structure_break_for_direction(
            rows,
            checkpoint_idx,
            new_direction,
            base.CONTINUATION_STRUCTURE_BARS,
        )
    except TypeError:
        try:
            structure = base.structure_break_for_direction(
                rows,
                checkpoint_idx,
                new_direction,
            )
        except Exception:
            structure = False
    except Exception:
        structure = False

    opposite = (
        structure
        or (
            max_consecutive >= OPPOSITE_MIN_CONSECUTIVE
            and move_pct is not None
            and move_pct >= OPPOSITE_MIN_MOVE_PCT
        )
    )

    return (
        opposite,
        structure,
        max_consecutive,
        move_pct,
    )


def classify_transition_path(
    rows: Sequence,
    broken_idx: int,
    checkpoint_idx: int,
    direction: str,
) -> Tuple[
    bool,
    bool,
    bool,
    bool,
    int,
    Optional[float],
]:
    """
    Classify the causal path AFTER THESIS_BROKEN.

    Priority:

        RECOVERY
        >
        CONTINUING_FAILURE
        >
        OPPOSITE_TRANSITION

    Recovery is evaluated first because an original trend
    can recover after its thesis temporarily breaks.

    Opposite transition is reported independently as the
    final reversal candidate.
    """
    recovery = recovery_evidence(
        rows,
        broken_idx,
        checkpoint_idx,
        direction,
    )

    continuing = continuing_failure_evidence(
        rows,
        broken_idx,
        checkpoint_idx,
        direction,
    )

    (
        opposite,
        structure,
        consecutive,
        move_pct,
    ) = opposite_transition_evidence(
        rows,
        broken_idx,
        checkpoint_idx,
        direction,
    )

    return (
        recovery,
        continuing,
        opposite,
        structure,
        consecutive,
        move_pct,
    )

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

def evaluate_assignment(rows_5m, assignment):
    """
    V5.6.12.5 causal transition-path evaluation.

    Existing V5.6.12.4 checkpoint analysis is preserved.

    In addition, once THESIS_BROKEN is first observed, this function
    searches forward using ONLY candles available at each moment for:

        THESIS_BROKEN
             |
             +--> RECOVERY
             |
             +--> CONTINUING_FAILURE
             |
             +--> OPPOSITE_TRANSITION

    Future outcome is evaluated separately and is never used to
    determine the causal state.

    IMPORTANT:
        No trading-engine behavior is changed here.
        This is research/measurement only.
    """

    warning = assignment.episode.first

    warning_idx = find_close_index(
        rows_5m,
        warning.timestamp,
    )

    if warning_idx is None:
        return []

    results = []

    # ------------------------------------------------------------
    # EXISTING V5.6.12.4 CHECKPOINT ANALYSIS
    # ------------------------------------------------------------

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
            favorable_bars,
            adverse_bars,
            consecutive_adverse,
        ) = path_evidence(
            rows_5m,
            warning_idx,
            checkpoint_idx,
            assignment.transition.direction,
        )

        # --------------------------------------------------------
        # ORIGINAL-TREND STRUCTURE
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # OPPOSITE-DIRECTION EVIDENCE
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # V5.6.12.4 STATE
        # --------------------------------------------------------

        state = classify_state(
            assignment.transition.direction,
            signed_from_warning,
            min_signed,
            favorable_bars,
            adverse_bars,
            consecutive_adverse,
            old_structure,
            opp_structure,
            opp_consecutive,
            opp_move,
        )

        # --------------------------------------------------------
        # FUTURE OUTCOME
        # --------------------------------------------------------

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
                favorable_bars=favorable_bars,
                adverse_bars=adverse_bars,
                consecutive_adverse=consecutive_adverse,
                structure_break=old_structure,
                opposite_structure=opp_structure,
                opposite_consecutive=opp_consecutive,
                opposite_move_pct=opp_move,
                next60_outcome=next60_outcome,
                next60_return=next60_return,
            )
        )

    # ------------------------------------------------------------
    # V5.6.12.5 CAUSAL PATH
    # ------------------------------------------------------------
    #
    # Find the FIRST checkpoint where the existing V5.6.12.4
    # classifier says THESIS_BROKEN.
    #
    # We then move forward from that exact candle.
    #
    # This prevents the experiment from treating later observations
    # as if they were available at the original warning.
    # ------------------------------------------------------------

    broken_idx = None
    broken_minutes = None

    for checkpoint in results:
        if checkpoint.state == "THESIS_BROKEN":

            target_time = (
                warning.timestamp
                + timedelta(minutes=checkpoint.checkpoint_minutes)
            )

            candidate_idx = find_close_index(
                rows_5m,
                target_time,
            )

            if candidate_idx is not None:
                broken_idx = candidate_idx
                broken_minutes = checkpoint.checkpoint_minutes
                break

    if broken_idx is None:
        return results

    # ------------------------------------------------------------
    # SEARCH FORWARD AFTER THESIS_BROKEN
    # ------------------------------------------------------------
    #
    # We inspect the existing checkpoint times AFTER the broken
    # point. No future outcome is used for classification.
    # ------------------------------------------------------------

    for checkpoint in results:

        if (
            broken_minutes is None
            or checkpoint.checkpoint_minutes <= broken_minutes
        ):
            continue

        target_time = (
            warning.timestamp
            + timedelta(minutes=checkpoint.checkpoint_minutes)
        )

        checkpoint_idx = find_close_index(
            rows_5m,
            target_time,
        )

        if (
            checkpoint_idx is None
            or checkpoint_idx <= broken_idx
        ):
            continue

        (
            recovery,
            continuing,
            opposite,
            opposite_structure,
            opposite_consecutive,
            opposite_move,
        ) = classify_transition_path(
            rows_5m,
            broken_idx,
            checkpoint_idx,
            assignment.transition.direction,
        )

        # --------------------------------------------------------
        # ATTACH RESEARCH ATTRIBUTES TO THE EXISTING CHECKPOINT
        # --------------------------------------------------------
        #
        # We deliberately do not change the dataclass yet.
        # These attributes allow the next reporting layer to use
        # the causal path without disturbing existing results.
        # --------------------------------------------------------

        checkpoint.path_recovery = recovery
        checkpoint.path_continuing_failure = continuing
        checkpoint.path_opposite_transition = opposite
        checkpoint.path_opposite_structure = opposite_structure
        checkpoint.path_opposite_consecutive = opposite_consecutive
        checkpoint.path_opposite_move_pct = opposite_move

    return results


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
# V5.6.12.5 — CAUSAL PATH REPORT
# ============================================================

def report_causal_paths(
    assignments,
    results_by_assignment,
):
    """
    Report the actual causal path after the FIRST THESIS_BROKEN
    checkpoint.

    This report uses only information available at each checkpoint.

    It measures:

        WARNING
           |
           v
        THESIS_BROKEN
           |
           +--> RECOVERY
           |
           +--> CONTINUING_FAILURE
           |
           +--> OPPOSITE_TRANSITION
                         |
                         v
                  OFFICIAL TRANSITION

    NEXT60 is future-only and is never used to classify the path.
    """

    print("\n" + "=" * 90)
    print("V5.6.12.5 — CAUSAL TRANSITION PATH REPORT")
    print("=" * 90)

    print(
        "Path: WARNING -> THESIS_BROKEN -> "
        "RECOVERY / CONTINUING_FAILURE / OPPOSITE_TRANSITION"
    )
    print(
        "All path decisions use only candles available at that checkpoint."
    )

    # ------------------------------------------------------------
    # Collect one record per uniquely assigned transition.
    # ------------------------------------------------------------

    records = []

    for assignment in assignments:

        key = (
            assignment.transition.symbol,
            assignment.transition.timestamp,
            assignment.transition.direction,
        )

        checkpoints = results_by_assignment.get(key, [])

        if not checkpoints:
            continue

        broken = [
            r for r in checkpoints
            if r.state == "THESIS_BROKEN"
        ]

        if not broken:
            continue

        # FIRST thesis-broken checkpoint only.
        first_broken = min(
            broken,
            key=lambda r: r.checkpoint_minutes,
        )

        broken_minutes = first_broken.checkpoint_minutes

        later = [
            r for r in checkpoints
            if r.checkpoint_minutes > broken_minutes
        ]

        first_recovery = next(
            (
                r for r in later
                if getattr(r, "path_recovery", False)
            ),
            None,
        )

        first_continuing = next(
            (
                r for r in later
                if getattr(r, "path_continuing_failure", False)
            ),
            None,
        )

        first_opposite = next(
            (
                r for r in later
                if getattr(r, "path_opposite_transition", False)
            ),
            None,
        )

        warning_time = assignment.episode.first_timestamp
        transition_time = assignment.transition.timestamp

        def event_time(result):
            if result is None:
                return None
            return (
                warning_time
                + timedelta(minutes=result.checkpoint_minutes)
            )

        def lead_from_transition(result):
            if result is None:
                return None
            event = event_time(result)
            return (
                (transition_time - event).total_seconds() / 60.0
            )

        records.append(
            {
                "assignment": assignment,
                "first_broken": first_broken,
                "first_recovery": first_recovery,
                "first_continuing": first_continuing,
                "first_opposite": first_opposite,
                "warning_time": warning_time,
                "transition_time": transition_time,
                "broken_time": event_time(first_broken),
                "broken_lead": lead_from_transition(first_broken),
                "recovery_time": event_time(first_recovery),
                "continuing_time": event_time(first_continuing),
                "opposite_time": event_time(first_opposite),
                "recovery_lead": lead_from_transition(first_recovery),
                "continuing_lead": lead_from_transition(first_continuing),
                "opposite_lead": lead_from_transition(first_opposite),
            }
        )

    # ------------------------------------------------------------
    # Summary counts
    # ------------------------------------------------------------

    print("\n" + "-" * 90)
    print("PATH SUMMARY")
    print("-" * 90)

    total = len(records)

    print(f"TRANSITIONS WITH THESIS_BROKEN: {total}")

    recovery_count = sum(
        r["first_recovery"] is not None
        for r in records
    )

    continuing_count = sum(
        r["first_continuing"] is not None
        for r in records
    )

    opposite_count = sum(
        r["first_opposite"] is not None
        for r in records
    )

    print(
        f"FIRST RECOVERY:                 "
        f"{recovery_count:3d}"
        f" ({recovery_count / total * 100:5.1f}%)"
        if total else
        "FIRST RECOVERY:                 0"
    )

    print(
        f"FIRST CONTINUING FAILURE:       "
        f"{continuing_count:3d}"
        f" ({continuing_count / total * 100:5.1f}%)"
        if total else
        "FIRST CONTINUING FAILURE:       0"
    )

    print(
        f"FIRST OPPOSITE TRANSITION:       "
        f"{opposite_count:3d}"
        f" ({opposite_count / total * 100:5.1f}%)"
        if total else
        "FIRST OPPOSITE TRANSITION:       0"
    )

    # ------------------------------------------------------------
    # Timing summary
    # ------------------------------------------------------------

    print("\n" + "-" * 90)
    print("TIMING RELATIVE TO OFFICIAL TRANSITION")
    print("-" * 90)

    def timing_stats(name, field):
        values = [
            r[field]
            for r in records
            if r[field] is not None
        ]

        if not values:
            print(f"{name:28s} N=0")
            return

        avg = sum(values) / len(values)
        values_sorted = sorted(values)
        median = values_sorted[len(values_sorted) // 2]

        print(
            f"{name:28s} "
            f"N={len(values):3d} "
            f"AVG={avg:7.1f}m "
            f"MEDIAN={median:7.1f}m "
            f"MIN={min(values):7.1f}m "
            f"MAX={max(values):7.1f}m"
        )

    timing_stats(
        "THESIS_BROKEN",
        "broken_lead",
    )

    timing_stats(
        "RECOVERY",
        "recovery_lead",
    )

    timing_stats(
        "CONTINUING_FAILURE",
        "continuing_lead",
    )

    timing_stats(
        "OPPOSITE TRANSITION",
        "opposite_lead",
    )

    # ------------------------------------------------------------
    # Direction split
    # ------------------------------------------------------------

    print("\n" + "-" * 90)
    print("DIRECTIONAL PATH SUMMARY")
    print("-" * 90)

    for direction in ("LONG", "SHORT"):

        subset = [
            r for r in records
            if r["assignment"].transition.direction == direction
        ]

        n = len(subset)

        rec = sum(
            r["first_recovery"] is not None
            for r in subset
        )

        cont = sum(
            r["first_continuing"] is not None
            for r in subset
        )

        opp = sum(
            r["first_opposite"] is not None
            for r in subset
        )

        print(
            f"{direction:5s} "
            f"N={n:3d} "
            f"RECOVERY={rec:3d} "
            f"CONTINUING={cont:3d} "
            f"OPPOSITE={opp:3d}"
        )

    # ------------------------------------------------------------
    # Detailed transition-by-transition path
    # ------------------------------------------------------------

    print("\n" + "=" * 90)
    print("DETAILED CAUSAL PATHS")
    print("=" * 90)

    records.sort(
        key=lambda r: (
            r["assignment"].transition.symbol,
            r["assignment"].transition.timestamp,
        )
    )

    for record in records:

        assignment = record["assignment"]
        broken = record["first_broken"]
        recovery = record["first_recovery"]
        continuing = record["first_continuing"]
        opposite = record["first_opposite"]

        print("\n" + "-" * 90)

        print(
            f"{assignment.transition.symbol:5s} "
            f"{assignment.transition.direction:5s}"
        )

        print(
            f"  WARNING:              "
            f"{record['warning_time']}"
        )

        print(
            f"  THESIS BROKEN:        "
            f"+{broken.checkpoint_minutes:02d}m "
            f"{record['broken_time']}"
        )

        if recovery is not None:
            print(
                f"  RECOVERY:             "
                f"+{recovery.checkpoint_minutes:02d}m "
                f"{record['recovery_time']} "
                f"({record['recovery_lead']:+.1f}m)"
            )
        else:
            print(
                "  RECOVERY:             NONE"
            )

        if continuing is not None:
            print(
                f"  CONTINUING FAILURE:   "
                f"+{continuing.checkpoint_minutes:02d}m "
                f"{record['continuing_time']} "
                f"({record['continuing_lead']:+.1f}m)"
            )
        else:
            print(
                "  CONTINUING FAILURE:   NONE"
            )

        if opposite is not None:

            opp_structure = getattr(
                opposite,
                "path_opposite_structure",
                False,
            )

            opp_consecutive = getattr(
                opposite,
                "path_opposite_consecutive",
                0,
            )

            opp_move = getattr(
                opposite,
                "path_opposite_move_pct",
                None,
            )

            print(
                f"  OPPOSITE TRANSITION:  "
                f"+{opposite.checkpoint_minutes:02d}m "
                f"{record['opposite_time']} "
                f"({record['opposite_lead']:+.1f}m)"
            )

            print(
                f"      structure={opp_structure} "
                f"consecutive={opp_consecutive} "
                f"move={fmt_pct(opp_move)}"
            )

        else:
            print(
                "  OPPOSITE TRANSITION:  NONE"
            )

        print(
            f"  OFFICIAL TRANSITION:  "
            f"{record['transition_time']}"
        )

        # --------------------------------------------------------
        # Future outcome from the latest available path checkpoint
        # --------------------------------------------------------

        outcome_result = opposite or continuing or recovery or broken

        if outcome_result is not None:
            print(
                f"  NEXT60 OUTCOME:       "
                f"{outcome_result.next60_outcome} "
                f"{fmt_pct(outcome_result.next60_return)}"
            )

    # ------------------------------------------------------------
    # Most important research question:
    # Did opposite transition appear before official transition?
    # ------------------------------------------------------------

    print("\n" + "=" * 90)
    print("OPPOSITE TRANSITION EARLY-RECOGNITION TEST")
    print("=" * 90)

    opposite_records = [
        r for r in records
        if r["first_opposite"] is not None
    ]

    early = [
        r for r in opposite_records
        if r["opposite_lead"] > 0
    ]

    at_transition = [
        r for r in opposite_records
        if r["opposite_lead"] == 0
    ]

    late = [
        r for r in opposite_records
        if r["opposite_lead"] < 0
    ]

    print(
        f"OPPOSITE TRANSITION DETECTED: {len(opposite_records)}"
    )
    print(
        f"BEFORE OFFICIAL TRANSITION:   {len(early)}"
    )
    print(
        f"AT OFFICIAL TRANSITION:       {len(at_transition)}"
    )
    print(
        f"AFTER OFFICIAL TRANSITION:    {len(late)}"
    )

    early_leads = [
        r["opposite_lead"]
        for r in early
        if r["opposite_lead"] is not None
    ]

    if early_leads:
        print(
            f"EARLY AVG LEAD:               "
            f"{sum(early_leads) / len(early_leads):.1f}m"
        )
        print(
            f"EARLY MEDIAN LEAD:            "
            f"{sorted(early_leads)[len(early_leads)//2]:.1f}m"
        )

    print("\nResearch only. No trading-engine behavior is changed.")

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

    report_causal_paths(
        all_assignments,
        all_results_by_assignment,
    )

    print("\n" + "#" * 90)
    print("V5.6.12.5 INTERPRETATION")
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
