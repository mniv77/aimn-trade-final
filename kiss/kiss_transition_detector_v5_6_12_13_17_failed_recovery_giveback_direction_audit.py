"""
AIMn V13.17 Research Audit

FAILED-RECOVERY DIRECTION-CONTROLLED GIVEBACK AUDIT

Follow-up to:
    kiss_transition_detector_v5_6_12_13_17_failed_recovery_timing_audit.py

Purpose:
    Control the failed-recovery giveback comparison by direction.

    LONG:
        LATER_PF_BY_60 vs NO_PF_BY_60

    SHORT:
        LATER_PF_BY_60 vs NO_PF_BY_60

Research only.
No production trading rule changes.
No threshold promotion.
No orders.
No AI training.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    build_v1317_research_paths,
)


# ================================================================
# DATA STRUCTURE
# ================================================================

@dataclass
class GivebackCase:
    symbol: str
    direction: str

    outcome: str
    first_pf_time: int | None

    first_recovery_time: int
    last_recovery_time: int
    first_deterioration_time: int

    recovery_to_deterioration_gap: int
    deterioration_to_30: int

    deteriorating_points: int

    last_recovery_return: float
    first_deterioration_return: float
    return_30: float

    peak_return: float
    peak_time: int

    giveback: float
    mfe: float


# ================================================================
# RETURN HELPERS
# ================================================================

def directional_return(
    direction: str,
    return_pct: float,
) -> float:
    """
    StatePoint.return_pct in V13.17 is already directional
    according to the StatePath construction.

    Keep this helper explicit for audit readability.
    """
    return return_pct


# ================================================================
# STATE HELPERS
# ================================================================

def first_time_for_state(points, state: str):
    for point in points:
        if point.state == state:
            return point.minutes

    return None


def last_time_for_state(points, state: str):
    matches = [
        point.minutes
        for point in points
        if point.state == state
    ]

    if not matches:
        return None

    return matches[-1]


def first_persistent_failure_time(points):
    return first_time_for_state(
        points,
        "PERSISTENT_FAILURE",
    )


def has_persistent_failure_by_60(points) -> bool:
    return any(
        point.minutes <= 60
        and point.state == "PERSISTENT_FAILURE"
        for point in points
    )


# ================================================================
# BUILD ONE FAILED-RECOVERY CASE
# ================================================================

def build_case(
    path,
) -> GivebackCase | None:

    points = list(path.points)

    if not points:
        return None

    # ------------------------------------------------------------
    # Recovery must occur.
    # ------------------------------------------------------------

    first_recovery = first_time_for_state(
        points,
        "RECOVERING",
    )

    last_recovery = last_time_for_state(
        points,
        "RECOVERING",
    )

    if first_recovery is None:
        return None

    if last_recovery is None:
        return None

    # ------------------------------------------------------------
    # We need deterioration AFTER the recovery attempt.
    # ------------------------------------------------------------

    deterioration_after_recovery = [
        point
        for point in points
        if (
            point.state == "DETERIORATING"
            and point.minutes > last_recovery
        )
    ]

    if not deterioration_after_recovery:
        return None

    first_deterioration_point = min(
        deterioration_after_recovery,
        key=lambda point: point.minutes,
    )

    first_deterioration = (
        first_deterioration_point.minutes
    )

    # Keep the exact failed-recovery population
    # defined by the prior timing audit:
    # first deterioration must occur by +30m.
    if first_deterioration > 30:
        return None

    # ------------------------------------------------------------
    # Need +30 checkpoint.
    # ------------------------------------------------------------

    point_30 = next(
        (
            point
            for point in points
            if point.minutes == 30
        ),
        None,
    )

    if point_30 is None:
        return None

    # ------------------------------------------------------------
    # Outcome.
    # ------------------------------------------------------------

    pf_time = first_persistent_failure_time(points)

    if has_persistent_failure_by_60(points):
        outcome = "LATER_PF_BY_60"
    else:
        outcome = "NO_PF_BY_60"

    # ------------------------------------------------------------
    # Recovery points.
    # ------------------------------------------------------------

    recovery_points = [
        point
        for point in points
        if point.state == "RECOVERING"
    ]

    if not recovery_points:
        return None

    last_recovery_point = max(
        recovery_points,
        key=lambda point: point.minutes,
    )

    # ------------------------------------------------------------
    # Deterioration points from first deterioration through +30.
    # ------------------------------------------------------------

    deteriorating_points = [
        point
        for point in points
        if (
            point.state == "DETERIORATING"
            and first_deterioration
            <= point.minutes
            <= 30
        )
    ]

    # ------------------------------------------------------------
    # Returns.
    # ------------------------------------------------------------

    last_recovery_return = directional_return(
        path.direction,
        last_recovery_point.return_pct,
    )

    first_deterioration_return = directional_return(
        path.direction,
        first_deterioration_point.return_pct,
    )

    return_30 = directional_return(
        path.direction,
        point_30.return_pct,
    )

    # ------------------------------------------------------------
    # Peak.
    #
    # IMPORTANT:
    # Use the actual StatePoint return_pct supplied by V13.17.
    # Do not reconstruct the return from prices.
    # ------------------------------------------------------------

    peak_point = max(
        points,
        key=lambda point: directional_return(
            path.direction,
            point.return_pct,
        ),
    )

    peak_return = directional_return(
        path.direction,
        peak_point.return_pct,
    )

    peak_time = peak_point.minutes

    # ------------------------------------------------------------
    # Giveback.
    #
    # Peak minus return at +30.
    # ------------------------------------------------------------

    giveback = peak_return - return_30

    # ------------------------------------------------------------
    # Timing.
    # ------------------------------------------------------------

    recovery_to_deterioration_gap = (
        first_deterioration
        - last_recovery
    )

    deterioration_to_30 = max(
        0,
        30 - first_deterioration,
    )

    return GivebackCase(
        symbol=path.symbol,
        direction=path.direction,
        outcome=outcome,
        first_pf_time=pf_time,
        first_recovery_time=first_recovery,
        last_recovery_time=last_recovery,
        first_deterioration_time=first_deterioration,
        recovery_to_deterioration_gap=(
            recovery_to_deterioration_gap
        ),
        deterioration_to_30=deterioration_to_30,
        deteriorating_points=len(
            deteriorating_points
        ),
        last_recovery_return=last_recovery_return,
        first_deterioration_return=(
            first_deterioration_return
        ),
        return_30=return_30,
        peak_return=peak_return,
        peak_time=peak_time,
        giveback=giveback,
        mfe=peak_return,
    )


# ================================================================
# BUILD CASE POPULATION
# ================================================================

def build_failed_recovery_cases() -> List[GivebackCase]:

    paths = build_v1317_research_paths()

    cases: List[GivebackCase] = []

    seen = set()

    for path in paths:

        # --------------------------------------------------------
        # Unique trajectory identity.
        # --------------------------------------------------------

        key = (
            path.symbol,
            path.direction,
            path.opposite_time,
        )

        if key in seen:
            continue

        seen.add(key)

        case = build_case(path)

        if case is None:
            continue

        cases.append(case)

    return cases


# ================================================================
# STATISTICS
# ================================================================

def mean(values):
    if not values:
        return 0.0

    return sum(values) / len(values)


def median(values):
    if not values:
        return 0.0

    values = sorted(values)

    n = len(values)

    if n % 2 == 1:
        return values[n // 2]

    return (
        values[n // 2 - 1]
        + values[n // 2]
    ) / 2.0


def minimum(values):
    if not values:
        return 0.0

    return min(values)


def maximum(values):
    if not values:
        return 0.0

    return max(values)


def print_metric(
    label,
    pf_values,
    no_pf_values,
):
    print(
        f"{label:<34}"
        f" PF mean={mean(pf_values):>9.4f}"
        f" med={median(pf_values):>9.4f}"
        f" range=[{minimum(pf_values):>9.4f},"
        f" {maximum(pf_values):>9.4f}]"
        f" | NO_PF mean={mean(no_pf_values):>9.4f}"
        f" med={median(no_pf_values):>9.4f}"
        f" range=[{minimum(no_pf_values):>9.4f},"
        f" {maximum(no_pf_values):>9.4f}]"
    )


# ================================================================
# DIRECTION AUDIT
# ================================================================

def print_direction_audit(
    direction: str,
    cases: List[GivebackCase],
):

    direction_cases = [
        case
        for case in cases
        if case.direction == direction
    ]

    pf_cases = [
        case
        for case in direction_cases
        if case.outcome == "LATER_PF_BY_60"
    ]

    no_pf_cases = [
        case
        for case in direction_cases
        if case.outcome == "NO_PF_BY_60"
    ]

    print()
    print("=" * 110)
    print(f"DIRECTION-CONTROLLED AUDIT: {direction}")
    print("=" * 110)

    print(
        f"TOTAL FAILED-RECOVERY CASES = "
        f"{len(direction_cases)}"
    )

    print(
        f"LATER_PF_BY_60 = {len(pf_cases)}"
    )

    print(
        f"NO_PF_BY_60 = {len(no_pf_cases)}"
    )

    if not pf_cases or not no_pf_cases:

        print()
        print(
            "INSUFFICIENT CASES FOR "
            "WITHIN-DIRECTION COMPARISON."
        )

        return

    print()
    print("-" * 110)
    print("WITHIN-DIRECTION METRICS")
    print("-" * 110)

    print_metric(
        "Recovery -> deterioration (min)",
        [
            case.recovery_to_deterioration_gap
            for case in pf_cases
        ],
        [
            case.recovery_to_deterioration_gap
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Deterioration -> +30 (min)",
        [
            case.deterioration_to_30
            for case in pf_cases
        ],
        [
            case.deterioration_to_30
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Last recovery return (%)",
        [
            case.last_recovery_return
            for case in pf_cases
        ],
        [
            case.last_recovery_return
            for case in no_pf_cases
        ],
    )

    print_metric(
        "First deterioration return (%)",
        [
            case.first_deterioration_return
            for case in pf_cases
        ],
        [
            case.first_deterioration_return
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Return at +30 (%)",
        [
            case.return_30
            for case in pf_cases
        ],
        [
            case.return_30
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Peak signed return (%)",
        [
            case.peak_return
            for case in pf_cases
        ],
        [
            case.peak_return
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Giveback from peak (%)",
        [
            case.giveback
            for case in pf_cases
        ],
        [
            case.giveback
            for case in no_pf_cases
        ],
    )

    print_metric(
        "MFE (%)",
        [
            case.mfe
            for case in pf_cases
        ],
        [
            case.mfe
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Deteriorating points",
        [
            float(case.deteriorating_points)
            for case in pf_cases
        ],
        [
            float(case.deteriorating_points)
            for case in no_pf_cases
        ],
    )

    # ------------------------------------------------------------
    # Range overlap.
    # ------------------------------------------------------------

    pf_givebacks = [
        case.giveback
        for case in pf_cases
    ]

    no_pf_givebacks = [
        case.giveback
        for case in no_pf_cases
    ]

    pf_min = minimum(pf_givebacks)
    pf_max = maximum(pf_givebacks)

    no_pf_min = minimum(no_pf_givebacks)
    no_pf_max = maximum(no_pf_givebacks)

    overlap = not (
        pf_max < no_pf_min
        or no_pf_max < pf_min
    )

    print()
    print("-" * 110)
    print("GIVEBACK RANGE CHECK")
    print("-" * 110)

    print(
        f"LATER_PF_BY_60: "
        f"{pf_min:.6f}% -> {pf_max:.6f}%"
    )

    print(
        f"NO_PF_BY_60:     "
        f"{no_pf_min:.6f}% -> {no_pf_max:.6f}%"
    )

    print(
        f"RANGE OVERLAP: "
        f"{'YES' if overlap else 'NO'}"
    )

    # ------------------------------------------------------------
    # Exact cases.
    # ------------------------------------------------------------

    print()
    print("-" * 110)
    print("EXACT CASES")
    print("-" * 110)

    for case in sorted(
        direction_cases,
        key=lambda item: (
            item.outcome,
            item.symbol,
            item.first_recovery_time,
        ),
    ):

        print(
            f"{case.symbol:<6} "
            f"{case.direction:<5} "
            f"{case.outcome:<16} "
            f"FIRST_REC={case.first_recovery_time:>3}m "
            f"LAST_REC={case.last_recovery_time:>3}m "
            f"FIRST_DET={case.first_deterioration_time:>3}m "
            f"GAP={case.recovery_to_deterioration_gap:>2}m "
            f"DET->30={case.deterioration_to_30:>2}m "
            f"LAST_REC={case.last_recovery_return:>8.4f}% "
            f"FIRST_DET={case.first_deterioration_return:>8.4f}% "
            f"RET30={case.return_30:>8.4f}% "
            f"PEAK={case.peak_return:>8.4f}% "
            f"PEAK@{case.peak_time:>3}m "
            f"GIVEBACK={case.giveback:>8.4f}% "
            f"MFE={case.mfe:>8.4f}% "
            f"DETPTS={case.deteriorating_points}"
        )


# ================================================================
# POOLED REFERENCE
# ================================================================

def print_pooled_reference(cases):

    pf_cases = [
        case
        for case in cases
        if case.outcome == "LATER_PF_BY_60"
    ]

    no_pf_cases = [
        case
        for case in cases
        if case.outcome == "NO_PF_BY_60"
    ]

    print()
    print("=" * 110)
    print("POOLED REFERENCE")
    print("=" * 110)

    print(
        f"LATER_PF_BY_60 = {len(pf_cases)}"
    )

    print(
        f"NO_PF_BY_60 = {len(no_pf_cases)}"
    )

    if not pf_cases or not no_pf_cases:
        return

    print()

    print_metric(
        "Giveback from peak (%)",
        [
            case.giveback
            for case in pf_cases
        ],
        [
            case.giveback
            for case in no_pf_cases
        ],
    )

    print_metric(
        "Peak signed return (%)",
        [
            case.peak_return
            for case in pf_cases
        ],
        [
            case.peak_return
            for case in no_pf_cases
        ],
    )


# ================================================================
# MAIN
# ================================================================

def main():

    print()
    print("=" * 110)
    print("AIMn V13.17")
    print("FAILED-RECOVERY DIRECTION-CONTROLLED GIVEBACK AUDIT")
    print("=" * 110)

    print()
    print("RESEARCH ONLY")
    print("No production rule changes.")
    print("No threshold promotion.")
    print("No future information used for earlier state construction.")

    cases = build_failed_recovery_cases()

    print()
    print(
        f"FAILED-RECOVERY CASES BUILT = {len(cases)}"
    )

    print_direction_audit(
        "LONG",
        cases,
    )

    print_direction_audit(
        "SHORT",
        cases,
    )

    print_pooled_reference(cases)

    print()
    print("=" * 110)
    print("AUDIT COMPLETE")
    print("=" * 110)

    print()
    print("INTERPRETATION:")
    print(
        "Direction-specific differences are descriptive only."
    )
    print(
        "Do not promote a giveback threshold from this sample."
    )
    print(
        "The next decision should depend on whether the observed "
        "pattern survives direction control and case-level sensitivity."
    )


if __name__ == "__main__":
    main()
