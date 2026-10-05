"""
AIMn / KISS V13.17 COMPANION RESEARCH

FAILED-RECOVERY TIMING AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
Among cases where recovery failed before +30m, does the TIMING/SHAPE
of that failure distinguish cases that later reach PF from cases that
do not?

TARGET POPULATION
-----------------
Only cases satisfying:

    no PF at or before +30m
    RECOVERING occurred before +30m
    DETERIORATING occurred after the last RECOVERING state
    all before or at +30m

This produces the RECOVERY_FAILED population.

OUTCOME
-------
LATER_PF_BY_60M
    PF after +30m and by +60m

NO_PF_BY_60M
    no PF by +60m

PRE-OUTCOME MEASUREMENTS
------------------------
All measurements are determined at or before +30m:

    first recovery minute
    last recovery minute
    first deterioration after last recovery
    minutes from last recovery to deterioration
    minutes from first deterioration to +30m
    number of deteriorating StatePoints after recovery
    return at last recovery
    return at first deterioration
    return at +30m
    peak signed return through +30m
    giveback from peak to +30m
    MFE at +30m

DIRECTION
---------
LONG and SHORT are reported separately.

IMPORTANT
---------
This audit does NOT compare failed recovery against held recovery.
That question has already shown that current +30m state separates the
groups completely in the current sample.

This audit asks whether, WITHIN FAILED RECOVERY, the timing/shape
contains additional descriptive information.

No future information after +30m is used to construct any predictor.

No threshold is derived.

No production code changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Iterable, List, Optional, Sequence

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_case_aware_validation
    as base
)


PERSISTENT = "PERSISTENT_FAILURE"
RECOVERING = "RECOVERING"
DETERIORATING = "DETERIORATING"

LATER_PF = "LATER_PF_BY_60"
NO_PF = "NO_PF_BY_60"

LANDMARK = 30
OUTCOME_END = 60


@dataclass
class FailedRecoveryCase:
    symbol: str
    direction: str
    first_pf_minutes: Optional[int]

    outcome: str

    first_recovery_minutes: Optional[int]
    last_recovery_minutes: Optional[int]

    first_deterioration_after_recovery_minutes: Optional[int]

    recovery_to_deterioration_gap: Optional[int]
    deterioration_to_30m_duration: Optional[int]

    deterioration_points_after_recovery: int

    last_recovery_return: Optional[float]
    first_deterioration_return: Optional[float]
    return_at_30m: Optional[float]

    peak_return_minutes: Optional[int]
    peak_signed_return: Optional[float]

    giveback_from_peak: Optional[float]
    mfe_at_30m: Optional[float]

    path_to_30m: str


def attr(
    obj: Any,
    *names: str,
    default: Any = None,
) -> Any:

    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)

    return default


def to_float(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(
    value: Any,
) -> Optional[int]:

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def point_minutes(
    point: Any,
) -> Optional[int]:

    return to_int(
        attr(
            point,
            "minutes",
            "minute",
            "offset_minutes",
            default=None,
        )
    )


def point_state(
    point: Any,
) -> Optional[str]:

    value = attr(
        point,
        "state",
        "current_state",
        default=None,
    )

    if value is None:
        return None

    return str(value)


def point_return(
    point: Any,
) -> Optional[float]:

    return to_float(
        attr(
            point,
            "return_pct",
            "signed_return_pct",
            default=None,
        )
    )


def point_mfe(
    point: Any,
) -> Optional[float]:

    return to_float(
        attr(
            point,
            "mfe_pct",
            default=None,
        )
    )


def path_symbol(
    path: Any,
) -> str:

    return str(
        attr(
            path,
            "symbol",
            default="",
        )
    )


def path_direction(
    path: Any,
) -> str:

    return str(
        attr(
            path,
            "direction",
            default="",
        )
    ).upper()


def path_points(
    path: Any,
) -> List[Any]:

    points = attr(
        path,
        "points",
        "state_points",
        default=None,
    )

    if points is None:
        return []

    return list(points)


def sorted_points(
    points: Sequence[Any],
) -> List[Any]:

    valid = []

    for point in points:

        minute = point_minutes(point)
        state = point_state(point)

        if minute is None or state is None:
            continue

        valid.append(point)

    return sorted(
        valid,
        key=lambda point: point_minutes(point),
    )


def dedup_paths(
    paths: Iterable[Any],
) -> List[Any]:

    seen = set()
    result = []

    for path in paths:

        key = (
            path_symbol(path),
            path_direction(path),
            attr(
                path,
                "opposite_time",
                "transition_time",
                default=None,
            ),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(path)

    return result


def first_pf_minutes(
    points: Sequence[Any],
) -> Optional[int]:

    for point in points:

        if point_state(point) == PERSISTENT:

            return point_minutes(point)

    return None


def exact_point(
    points: Sequence[Any],
    minute_target: int,
) -> Optional[Any]:

    for point in points:

        if point_minutes(point) == minute_target:
            return point

    return None


def build_failed_case(
    path: Any,
) -> Optional[FailedRecoveryCase]:

    points = sorted_points(
        path_points(path)
    )

    if not points:
        return None

    point_30 = exact_point(
        points,
        LANDMARK,
    )

    if point_30 is None:
        return None

    first_pf = first_pf_minutes(
        points
    )

    # Exclude PF already present by +30m.
    if (
        first_pf is not None
        and first_pf <= LANDMARK
    ):
        return None

    pre = [
        point
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point) <= LANDMARK
        )
    ]

    recovering = [
        point
        for point in pre
        if point_state(point) == RECOVERING
    ]

    if not recovering:
        return None

    first_recovery_minutes = (
        point_minutes(recovering[0])
    )

    last_recovery_point = recovering[-1]

    last_recovery_minutes = (
        point_minutes(last_recovery_point)
    )

    if last_recovery_minutes is None:
        return None

    first_deterioration_point = None

    for point in pre:

        minute = point_minutes(point)

        if minute is None:
            continue

        if minute <= last_recovery_minutes:
            continue

        if point_state(point) == DETERIORATING:

            first_deterioration_point = point
            break

    if first_deterioration_point is None:
        return None

    first_deterioration_minutes = (
        point_minutes(
            first_deterioration_point
        )
    )

    if first_deterioration_minutes is None:
        return None

    deterioration_after_recovery = [
        point
        for point in pre
        if (
            point_minutes(point) is not None
            and point_minutes(point)
            > last_recovery_minutes
            and point_state(point)
            == DETERIORATING
        )
    ]

    recovery_to_deterioration_gap = (
        first_deterioration_minutes
        - last_recovery_minutes
    )

    deterioration_to_30m_duration = (
        LANDMARK
        - first_deterioration_minutes
    )

    return_at_30m = point_return(
        point_30
    )

    last_recovery_return = point_return(
        last_recovery_point
    )

    first_deterioration_return = point_return(
        first_deterioration_point
    )

    return_points = []

    for point in pre:

        minute = point_minutes(point)
        value = point_return(point)

        if minute is None or value is None:
            continue

        return_points.append(
            (
                minute,
                value,
            )
        )

    if return_points:

        peak_return_minutes, peak_signed_return = max(
            return_points,
            key=lambda item: item[1],
        )

    else:

        peak_return_minutes = None
        peak_signed_return = None

    if (
        peak_signed_return is not None
        and return_at_30m is not None
    ):

        giveback_from_peak = (
            peak_signed_return
            - return_at_30m
        )

    else:

        giveback_from_peak = None

    later_pf = False

    for point in points:

        minute = point_minutes(point)

        if minute is None:
            continue

        if minute <= LANDMARK:
            continue

        if minute > OUTCOME_END:
            continue

        if point_state(point) == PERSISTENT:

            later_pf = True
            break

    outcome = (
        LATER_PF
        if later_pf
        else NO_PF
    )

    path_to_30m = " -> ".join(
        f"+{point_minutes(point)}m:"
        f"{point_state(point)}"
        for point in pre
        if (
            point_minutes(point) is not None
            and point_state(point) is not None
        )
    )

    return FailedRecoveryCase(
        symbol=path_symbol(path),
        direction=path_direction(path),
        first_pf_minutes=first_pf,
        outcome=outcome,
        first_recovery_minutes=(
            first_recovery_minutes
        ),
        last_recovery_minutes=(
            last_recovery_minutes
        ),
        first_deterioration_after_recovery_minutes=(
            first_deterioration_minutes
        ),
        recovery_to_deterioration_gap=(
            recovery_to_deterioration_gap
        ),
        deterioration_to_30m_duration=(
            deterioration_to_30m_duration
        ),
        deterioration_points_after_recovery=len(
            deterioration_after_recovery
        ),
        last_recovery_return=(
            last_recovery_return
        ),
        first_deterioration_return=(
            first_deterioration_return
        ),
        return_at_30m=return_at_30m,
        peak_return_minutes=(
            peak_return_minutes
        ),
        peak_signed_return=(
            peak_signed_return
        ),
        giveback_from_peak=(
            giveback_from_peak
        ),
        mfe_at_30m=point_mfe(
            point_30
        ),
        path_to_30m=path_to_30m,
    )


def build_cases() -> List[FailedRecoveryCase]:

    paths = dedup_paths(
        base.build_v1317_research_paths()
    )

    cases = []

    for path in paths:

        case = build_failed_case(
            path
        )

        if case is None:
            continue

        cases.append(
            case
        )

    return cases


def values(
    cases: Sequence[FailedRecoveryCase],
    attribute: str,
) -> List[float]:

    result = []

    for case in cases:

        value = getattr(
            case,
            attribute,
            None,
        )

        if value is None:
            continue

        result.append(
            float(value)
        )

    return result


def count_values(
    cases: Sequence[FailedRecoveryCase],
    attribute: str,
) -> List[int]:

    result = []

    for case in cases:

        value = getattr(
            case,
            attribute,
            None,
        )

        if value is None:
            continue

        result.append(
            int(value)
        )

    return result


def print_cases(
    cases: Sequence[FailedRecoveryCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "EXACT FAILED-RECOVERY CASES"
    )
    print("=" * 120)

    for direction in (
        "LONG",
        "SHORT",
    ):

        direction_cases = [
            case
            for case in cases
            if case.direction == direction
        ]

        if not direction_cases:
            continue

        print()
        print(
            f"DIRECTION = {direction}"
        )

        for case in sorted(
            direction_cases,
            key=lambda item: (
                item.outcome,
                item.symbol,
            ),
        ):

            first_pf = (
                f"+{case.first_pf_minutes}m"
                if case.first_pf_minutes is not None
                else "NONE"
            )

            print()
            print(
                f"{case.symbol:<6} "
                f"{case.outcome:<15} "
                f"FIRST_PF={first_pf}"
            )

            print(
                f"  FIRST RECOVERY            = "
                f"+{case.first_recovery_minutes}m"
            )

            print(
                f"  LAST RECOVERY             = "
                f"+{case.last_recovery_minutes}m"
            )

            print(
                f"  FIRST DETERIORATION       = "
                f"+{case.first_deterioration_after_recovery_minutes}m"
            )

            print(
                f"  RECOVERY->DETERIORATION   = "
                f"{case.recovery_to_deterioration_gap}m"
            )

            print(
                f"  DETERIORATION->+30m       = "
                f"{case.deterioration_to_30m_duration}m"
            )

            print(
                f"  DETERIORATING POINTS      = "
                f"{case.deterioration_points_after_recovery}"
            )

            print(
                f"  LAST RECOVERY RETURN      = "
                f"{case.last_recovery_return}"
            )

            print(
                f"  FIRST DETERIORATION RETURN = "
                f"{case.first_deterioration_return}"
            )

            print(
                f"  RETURN AT +30M             = "
                f"{case.return_at_30m}"
            )

            print(
                f"  PEAK RETURN                = "
                f"{case.peak_signed_return}"
                f" @+{case.peak_return_minutes}m"
            )

            print(
                f"  GIVEBACK FROM PEAK         = "
                f"{case.giveback_from_peak}"
            )

            print(
                f"  MFE AT +30M                = "
                f"{case.mfe_at_30m}"
            )

            print(
                f"  PATH                       = "
                f"{case.path_to_30m}"
            )


def print_summary(
    name: str,
    cases: Sequence[FailedRecoveryCase],
) -> None:

    later_pf = sum(
        case.outcome == LATER_PF
        for case in cases
    )

    no_pf = sum(
        case.outcome == NO_PF
        for case in cases
    )

    print()
    print("=" * 120)
    print(
        f"SUMMARY — {name}"
    )
    print("=" * 120)

    print()
    print(
        f"CASES = {len(cases)}"
    )

    print(
        f"LATER PF BY +60M = {later_pf}"
    )

    print(
        f"NO PF BY +60M    = {no_pf}"
    )

    for label, attribute in (
        (
            "RECOVERY_TO_DETERIORATION_GAP",
            "recovery_to_deterioration_gap",
        ),
        (
            "DETERIORATION_TO_30M_DURATION",
            "deterioration_to_30m_duration",
        ),
        (
            "LAST_RECOVERY_RETURN",
            "last_recovery_return",
        ),
        (
            "FIRST_DETERIORATION_RETURN",
            "first_deterioration_return",
        ),
        (
            "RETURN_AT_30M",
            "return_at_30m",
        ),
        (
            "PEAK_SIGNED_RETURN",
            "peak_signed_return",
        ),
        (
            "GIVEBACK_FROM_PEAK",
            "giveback_from_peak",
        ),
        (
            "MFE_AT_30M",
            "mfe_at_30m",
        ),
    ):

        data = values(
            cases,
            attribute,
        )

        if not data:

            print(
                f"{label:<34} N=0"
            )

            continue

        print(
            f"{label:<34} "
            f"N={len(data)} "
            f"AVG={mean(data):+.6f} "
            f"MEDIAN={median(data):+.6f} "
            f"MIN={min(data):+.6f} "
            f"MAX={max(data):+.6f}"
        )

    counts = count_values(
        cases,
        "deterioration_points_after_recovery",
    )

    if counts:

        print(
            f"{'DETERIORATING_POINTS':<34} "
            f"N={len(counts)} "
            f"AVG={mean(counts):.3f} "
            f"MEDIAN={median(counts):.3f} "
            f"MIN={min(counts)} "
            f"MAX={max(counts)}"
        )


def print_direction_summary(
    cases: Sequence[FailedRecoveryCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "FAILED-RECOVERY OUTCOME BY DIRECTION"
    )
    print("=" * 120)

    for direction in (
        "LONG",
        "SHORT",
    ):

        group = [
            case
            for case in cases
            if case.direction == direction
        ]

        if not group:
            continue

        later_pf = sum(
            case.outcome == LATER_PF
            for case in group
        )

        no_pf = sum(
            case.outcome == NO_PF
            for case in group
        )

        print()
        print(
            f"{direction}: "
            f"CASES={len(group)} "
            f"LATER_PF={later_pf} "
            f"NO_PF={no_pf}"
        )


def print_pf_vs_no_pf(
    cases: Sequence[FailedRecoveryCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "FAILED-RECOVERY: LATER PF vs NO PF"
    )
    print("=" * 120)

    later = [
        case
        for case in cases
        if case.outcome == LATER_PF
    ]

    no_pf = [
        case
        for case in cases
        if case.outcome == NO_PF
    ]

    print_summary(
        "LATER_PF_BY_60",
        later,
    )

    print_summary(
        "NO_PF_BY_60",
        no_pf,
    )

    print()
    print(
        "DIRECTION BREAKDOWN"
    )

    for direction in (
        "LONG",
        "SHORT",
    ):

        later_direction = [
            case
            for case in later
            if case.direction == direction
        ]

        no_direction = [
            case
            for case in no_pf
            if case.direction == direction
        ]

        print()
        print(
            f"{direction}"
        )

        print(
            f"  LATER_PF = "
            f"{len(later_direction)}"
        )

        print(
            f"  NO_PF    = "
            f"{len(no_direction)}"
        )


def print_interpretation(
    cases: Sequence[FailedRecoveryCase],
) -> None:

    later = [
        case
        for case in cases
        if case.outcome == LATER_PF
    ]

    no_pf = [
        case
        for case in cases
        if case.outcome == NO_PF
    ]

    print()
    print("=" * 120)
    print(
        "V13.17 FAILED-RECOVERY TIMING "
        "— INTERPRETATION"
    )
    print("=" * 120)

    print()

    print(
        "This audit is restricted to cases where recovery "
        "already failed before +30m."
    )

    print(
        f"FAILED-RECOVERY CASES = {len(cases)}"
    )

    print(
        f"LATER PF = {len(later)}"
    )

    print(
        f"NO PF    = {len(no_pf)}"
    )

    print()

    print(
        "The measurements describe when and how the recovery "
        "failure unfolded before +30m."
    )

    print(
        "They do not use post-+30m information."
    )

    print(
        "No timing threshold is derived."
    )

    print(
        "No composite score is constructed."
    )

    print(
        "The sample is extremely small."
    )

    print(
        "LONG and SHORT are reported separately."
    )

    print(
        "No result becomes an entry, warning, rescue, "
        "hold, or exit rule."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print()
    print("=" * 120)
    print(
        "V13.17 FAILED-RECOVERY TIMING AUDIT"
    )
    print("=" * 120)

    cases = build_cases()

    print()
    print(
        f"FAILED-RECOVERY CASES BUILT = "
        f"{len(cases)}"
    )

    print_cases(
        cases
    )

    print_direction_summary(
        cases
    )

    print_pf_vs_no_pf(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 120)
    print(
        "V13.17 FAILED-RECOVERY TIMING AUDIT COMPLETE"
    )
    print("=" * 120)


if __name__ == "__main__":
    main()
