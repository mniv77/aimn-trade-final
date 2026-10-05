"""
AIMn / KISS V13.17 COMPANION RESEARCH

RECOVERY PEAK / GIVEBACK AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
Within the LONG +30m DETERIORATING population, what happened between
the trade's best favorable excursion and its +30m state?

BACKGROUND
----------
The previous severity audit found that FAILED-RECOVERY and CLEAN cases
overlap on:

    RETURN_PCT
    FAVORABLE_RATIO
    ADVERSE_RATIO
    CONSECUTIVE_ADVERSE
    MAE

but the MFE_PCT ranges did not overlap.

Therefore this audit examines the recovery attempt itself.

TARGET POPULATION
-----------------
LONG
+
+30m STATE = DETERIORATING
+
NO PF AT OR BEFORE +30m

CURRENT PRIMARY GROUPS
----------------------
FAILED:
    RECOVERY_FAILED_BY_30M

CLEAN:
    NO_RECOVERY_FAILURE_BY_30M

RECOVERY MEASUREMENTS
---------------------
For every eligible case:

    1. Had RECOVERING before +30m?
    2. Last RECOVERING StatePoint
    3. Return at last RECOVERING
    4. Best signed return at or before +30m
    5. MFE at +30m
    6. +30m return
    7. Giveback from best signed return to +30m

GIVEBACK
--------
For signed return:

    giveback = best_signed_return - return_at_30m

This is descriptive.

A large positive giveback means the trajectory had moved favorably
and subsequently surrendered part of that favorable move.

IMPORTANT
---------
No threshold is created.

No composite score is created.

No case is ranked.

No future information after +30m is used.

Outcome is:

    PF AFTER +30m AND BY +60m
    OR
    NO PF BY +60m

The outcome is evaluated only after all +30m measurements have been
computed.

NO PRODUCTION CODE CHANGED.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, List, Optional, Sequence

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_case_aware_validation
    as base
)

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_pf_predecessor_enrichment_landmark_audit
    as landmark
)


TARGET_DIRECTION = "LONG"
TARGET_STATE = landmark.DETERIORATING
LANDMARK = 30


@dataclass
class GivebackCase:
    symbol: str
    direction: str

    outcome: str
    predictor: str

    first_pf_minutes: Optional[int]

    had_recovering: bool

    last_recovering_minutes: Optional[int]
    last_recovering_return: Optional[float]

    peak_return_minutes: Optional[int]
    peak_signed_return: Optional[float]

    return_at_30m: Optional[float]

    mfe_at_30m: Optional[float]

    giveback_from_peak: Optional[float]

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

    result = []

    for point in points:

        minute = point_minutes(
            point
        )

        state = point_state(
            point
        )

        if minute is None or state is None:
            continue

        result.append(
            point
        )

    return sorted(
        result,
        key=lambda point: point_minutes(point)
    )


def dedup_paths(
    paths: Sequence[Any],
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

        if point_state(point) == (
            landmark.PERSISTENT
        ):

            return point_minutes(
                point
            )

    return None


def recovery_failed_by_30m(
    points: Sequence[Any],
) -> bool:

    pre = [
        point
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point)
            <= LANDMARK
        )
    ]

    recovering = [
        point
        for point in pre
        if point_state(point)
        == landmark.RECOVERING
    ]

    if not recovering:
        return False

    last_recovery_minute = point_minutes(
        recovering[-1]
    )

    if last_recovery_minute is None:
        return False

    for point in pre:

        minute = point_minutes(
            point
        )

        if minute is None:
            continue

        if minute <= last_recovery_minute:
            continue

        if point_state(point) == (
            landmark.DETERIORATING
        ):

            return True

    return False


def exact_point(
    points: Sequence[Any],
    minute: int,
) -> Optional[Any]:

    for point in points:

        if point_minutes(point) == minute:
            return point

    return None


def format_path(
    points: Sequence[Any],
) -> str:

    parts = []

    for point in points:

        minute = point_minutes(
            point
        )

        state = point_state(
            point
        )

        if minute is None or state is None:
            continue

        parts.append(
            f"+{minute}m:{state}"
        )

    return " -> ".join(parts)


def build_cases() -> List[GivebackCase]:

    paths = dedup_paths(
        base.build_v1317_research_paths()
    )

    result = []

    for path in paths:

        if path_direction(path) != (
            TARGET_DIRECTION
        ):
            continue

        points = sorted_points(
            path_points(path)
        )

        if not points:
            continue

        point_30 = exact_point(
            points,
            LANDMARK
        )

        if point_30 is None:
            continue

        if point_state(point_30) != (
            TARGET_STATE
        ):
            continue

        first_pf = first_pf_minutes(
            points
        )

        # Exclude cases that reached PF
        # on or before the +30m landmark.
        if (
            first_pf is not None
            and first_pf <= LANDMARK
        ):
            continue

        failed = recovery_failed_by_30m(
            points
        )

        predictor = (
            "FAILED"
            if failed
            else "CLEAN"
        )

        if first_pf is not None and (
            first_pf > LANDMARK
            and first_pf <= 60
        ):

            outcome = landmark.LATE_PF

        else:

            outcome = landmark.NO_PF

        pre_landmark = [
            point
            for point in points
            if (
                point_minutes(point) is not None
                and point_minutes(point)
                <= LANDMARK
            )
        ]

        recovering = [
            point
            for point in pre_landmark
            if point_state(point)
            == landmark.RECOVERING
        ]

        had_recovering = bool(
            recovering
        )

        if recovering:

            last_recovery = recovering[-1]

            last_recovering_minutes = (
                point_minutes(last_recovery)
            )

            last_recovering_return = (
                point_return(last_recovery)
            )

        else:

            last_recovering_minutes = None
            last_recovering_return = None

        return_points = []

        for point in pre_landmark:

            value = point_return(
                point
            )

            minute = point_minutes(
                point
            )

            if (
                value is None
                or minute is None
            ):
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

        return_at_30m = point_return(
            point_30
        )

        mfe_at_30m = point_mfe(
            point_30
        )

        if (
            peak_signed_return is not None
            and return_at_30m is not None
        ):

            giveback = (
                peak_signed_return
                - return_at_30m
            )

        else:

            giveback = None

        result.append(
            GivebackCase(
                symbol=path_symbol(path),
                direction=path_direction(path),
                outcome=outcome,
                predictor=predictor,
                first_pf_minutes=first_pf,
                had_recovering=had_recovering,
                last_recovering_minutes=(
                    last_recovering_minutes
                ),
                last_recovering_return=(
                    last_recovering_return
                ),
                peak_return_minutes=(
                    peak_return_minutes
                ),
                peak_signed_return=(
                    peak_signed_return
                ),
                return_at_30m=return_at_30m,
                mfe_at_30m=mfe_at_30m,
                giveback_from_peak=giveback,
                path_to_30m=format_path(
                    pre_landmark
                ),
            )
        )

    return result


def values(
    cases: Sequence[GivebackCase],
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


def print_case(
    case: GivebackCase,
) -> None:

    print()
    print(
        f"{case.symbol:<6} "
        f"{case.predictor:<6} "
        f"OUTCOME={case.outcome:<18} "
        f"FIRST_PF="
        f"{('+' + str(case.first_pf_minutes) + 'm') if case.first_pf_minutes is not None else 'NONE'}"
    )

    print(
        f"  HAD RECOVERING          = "
        f"{case.had_recovering}"
    )

    print(
        f"  LAST RECOVERING         = "
        f"{('+' + str(case.last_recovering_minutes) + 'm') if case.last_recovering_minutes is not None else 'NONE'}"
    )

    print(
        f"  LAST RECOVERY RETURN    = "
        f"{case.last_recovering_return}"
    )

    print(
        f"  PEAK RETURN             = "
        f"{case.peak_signed_return}"
        f" @"
        f"{('+' + str(case.peak_return_minutes) + 'm') if case.peak_return_minutes is not None else 'NONE'}"
    )

    print(
        f"  RETURN AT +30M          = "
        f"{case.return_at_30m}"
    )

    print(
        f"  MFE AT +30M             = "
        f"{case.mfe_at_30m}"
    )

    print(
        f"  GIVEBACK FROM PEAK      = "
        f"{case.giveback_from_peak}"
    )

    print(
        f"  PATH                    = "
        f"{case.path_to_30m}"
    )


def print_exact_cases(
    cases: Sequence[GivebackCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "EXACT +30M RECOVERY / GIVEBACK CASES"
    )
    print("=" * 120)

    for predictor in (
        "FAILED",
        "CLEAN",
    ):

        group = [
            case
            for case in cases
            if case.predictor == predictor
        ]

        if not group:
            continue

        print()
        print(
            f"GROUP = {predictor}"
        )

        for case in sorted(
            group,
            key=lambda item: (
                item.outcome,
                item.symbol,
            ),
        ):

            print_case(
                case
            )


def print_summary(
    name: str,
    cases: Sequence[GivebackCase],
) -> None:

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

    later_pf = sum(
        case.outcome == landmark.LATE_PF
        for case in cases
    )

    no_pf = sum(
        case.outcome == landmark.NO_PF
        for case in cases
    )

    print(
        f"LATER PF BY +60M = {later_pf}"
    )

    print(
        f"NO PF BY +60M    = {no_pf}"
    )

    for label, attribute in (
        (
            "LAST_RECOVERY_RETURN",
            "last_recovering_return",
        ),
        (
            "PEAK_SIGNED_RETURN",
            "peak_signed_return",
        ),
        (
            "RETURN_AT_30M",
            "return_at_30m",
        ),
        (
            "MFE_AT_30M",
            "mfe_at_30m",
        ),
        (
            "GIVEBACK_FROM_PEAK",
            "giveback_from_peak",
        ),
    ):

        data = values(
            cases,
            attribute,
        )

        if not data:

            print(
                f"{label:<24} N=0"
            )

            continue

        print(
            f"{label:<24} "
            f"N={len(data)} "
            f"AVG={mean(data):+.6f} "
            f"MEDIAN={median(data):+.6f} "
            f"MIN={min(data):+.6f} "
            f"MAX={max(data):+.6f}"
        )


def print_outcome_summary(
    cases: Sequence[GivebackCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "RECOVERY / GIVEBACK BY OUTCOME"
    )
    print("=" * 120)

    for outcome in (
        landmark.LATE_PF,
        landmark.NO_PF,
    ):

        group = [
            case
            for case in cases
            if case.outcome == outcome
        ]

        print_summary(
            outcome,
            group,
        )


def print_predictor_summary(
    cases: Sequence[GivebackCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "RECOVERY / GIVEBACK BY PREDICTOR"
    )
    print("=" * 120)

    for predictor in (
        "FAILED",
        "CLEAN",
    ):

        group = [
            case
            for case in cases
            if case.predictor == predictor
        ]

        print_summary(
            predictor,
            group,
        )


def print_interpretation(
    cases: Sequence[GivebackCase],
) -> None:

    failed = [
        case
        for case in cases
        if case.predictor == "FAILED"
    ]

    clean = [
        case
        for case in cases
        if case.predictor == "CLEAN"
    ]

    failed_giveback = values(
        failed,
        "giveback_from_peak",
    )

    clean_giveback = values(
        clean,
        "giveback_from_peak",
    )

    failed_mfe = values(
        failed,
        "mfe_at_30m",
    )

    clean_mfe = values(
        clean,
        "mfe_at_30m",
    )

    print()
    print("=" * 120)
    print(
        "V13.17 RECOVERY PEAK / GIVEBACK "
        "— INTERPRETATION"
    )
    print("=" * 120)

    print()

    print(
        "This audit examines the trajectory shape before +30m."
    )

    print(
        "The failed-recovery label is determined from states only."
    )

    print(
        "Peak return, MFE, and giveback are independent measurements."
    )

    print()

    if failed_giveback and clean_giveback:

        print(
            f"FAILED GIVEBACK RANGE = "
            f"{min(failed_giveback):+.6f} "
            f"to "
            f"{max(failed_giveback):+.6f}"
        )

        print(
            f"CLEAN GIVEBACK RANGE  = "
            f"{min(clean_giveback):+.6f} "
            f"to "
            f"{max(clean_giveback):+.6f}"
        )

    print()

    if failed_mfe and clean_mfe:

        print(
            f"FAILED MFE RANGE = "
            f"{min(failed_mfe):+.6f} "
            f"to "
            f"{max(failed_mfe):+.6f}"
        )

        print(
            f"CLEAN MFE RANGE  = "
            f"{min(clean_mfe):+.6f} "
            f"to "
            f"{max(clean_mfe):+.6f}"
        )

    print()

    print(
        "This is descriptive trajectory research."
    )

    print(
        "No threshold is derived."
    )

    print(
        "No composite score is created."
    )

    print(
        "No result becomes an entry, warning, rescue, "
        "hold, or exit rule."
    )

    print(
        "The sample remains very small."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print()
    print("=" * 120)
    print(
        "V13.17 RECOVERY PEAK / GIVEBACK AUDIT"
    )
    print("=" * 120)

    print()
    print(
        "TARGET = LONG +30M DETERIORATING"
    )

    print(
        "CASES WITH PF BY +30M ARE EXCLUDED."
    )

    cases = build_cases()

    print()
    print(
        f"TARGET CASES = {len(cases)}"
    )

    print_exact_cases(
        cases
    )

    print_predictor_summary(
        cases
    )

    print_outcome_summary(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 120)
    print(
        "V13.17 RECOVERY PEAK / GIVEBACK AUDIT COMPLETE"
    )
    print("=" * 120)


if __name__ == "__main__":
    main()
