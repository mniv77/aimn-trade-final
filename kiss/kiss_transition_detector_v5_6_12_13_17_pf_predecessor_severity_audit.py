"""
AIMn / KISS V13.17 COMPANION RESEARCH

PF PREDECESSOR SEVERITY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
The direction + state controlled audit found exactly one comparable
stratum:

    LONG
    +30m STATE = DETERIORATING

Within that stratum:

    RECOVERY_FAILED_BY_30M
        N=3
        LATER PF=2
        RATE=0.6667

    NO_RECOVERY_FAILURE_BY_30M
        N=5
        LATER PF=1
        RATE=0.2000

The symbol sensitivity audit showed the descriptive positive delta
survived removal of each symbol.

This audit asks:

    How severe was the +30m deterioration in each case?

The goal is to determine whether the failed-recovery and clean cases
look materially different in their current +30m condition.

TARGET POPULATION
-----------------
LONG
+
+30m STATE = DETERIORATING

PREDICTOR
---------
RECOVERY_FAILED_BY_30M

OUTCOME
-------
PF AFTER +30m AND BY +60m

SEVERITY VARIABLES
------------------
At the exact +30m StatePoint, report:

    signed return / return_pct
    favorable ratio
    adverse ratio
    consecutive adverse count
    MAE
    MFE

IMPORTANT
---------
These measurements are descriptive.

This audit does NOT create severity thresholds.

This audit does NOT rank the cases.

This audit does NOT establish that one cohort is more severe.

The point is to determine whether the two predictor groups have
overlapping current-state severity.

NO FUTURE LEAKAGE
-----------------
The severity variables are taken at +30m.

Cohort membership uses only information at or before +30m.

Outcome is measured after +30m.

NO PRODUCTION CODE CHANGED.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence


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
LANDMARK_MINUTE = 30


@dataclass
class SeverityCase:
    symbol: str
    direction: str
    outcome: str
    predictor: str

    first_pf_minutes: Optional[int]

    return_pct: Optional[float]
    favorable_ratio: Optional[float]
    adverse_ratio: Optional[float]
    consecutive_adverse: Optional[int]
    mae_pct: Optional[float]
    mfe_pct: Optional[float]

    prior_state: Optional[str]

    state_path_to_30m: str


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

    value = attr(
        point,
        "minutes",
        "minute",
        "offset_minutes",
        default=None,
    )

    return to_int(
        value
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

    return str(
        value
    )


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


def point_favorable_ratio(
    point: Any,
) -> Optional[float]:

    return to_float(
        attr(
            point,
            "favorable_ratio",
            default=None,
        )
    )


def point_adverse_ratio(
    point: Any,
) -> Optional[float]:

    return to_float(
        attr(
            point,
            "adverse_ratio",
            default=None,
        )
    )


def point_consecutive_adverse(
    point: Any,
) -> Optional[int]:

    return to_int(
        attr(
            point,
            "consecutive_adverse",
            default=None,
        )
    )


def point_mae(
    point: Any,
) -> Optional[float]:

    return to_float(
        attr(
            point,
            "mae_pct",
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

    return list(
        points
    )


def point_sort_key(
    point: Any,
) -> int:

    minute = point_minutes(
        point
    )

    if minute is None:
        return 999999

    return minute


def sorted_points(
    points: Sequence[Any],
) -> List[Any]:

    valid = []

    for point in points:

        if (
            point_minutes(point)
            is None
            or point_state(point)
            is None
        ):
            continue

        valid.append(
            point
        )

    return sorted(
        valid,
        key=point_sort_key,
    )


def dedup_case_paths(
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
        result.append(
            path
        )

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

    pre_landmark = [
        point
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point)
            <= LANDMARK_MINUTE
        )
    ]

    recovering_minutes = []

    for point in pre_landmark:

        if point_state(point) == (
            landmark.RECOVERING
        ):

            minute = point_minutes(
                point
            )

            if minute is not None:

                recovering_minutes.append(
                    minute
                )

    if not recovering_minutes:

        return False

    last_recovering = max(
        recovering_minutes
    )

    for point in pre_landmark:

        minute = point_minutes(
            point
        )

        if minute is None:
            continue

        if minute <= last_recovering:
            continue

        if point_state(point) == (
            landmark.DETERIORATING
        ):

            return True

    return False


def exact_landmark_point(
    points: Sequence[Any],
) -> Optional[Any]:

    for point in points:

        if point_minutes(point) == (
            LANDMARK_MINUTE
        ):

            return point

    return None


def format_path(
    points: Sequence[Any],
) -> str:

    pieces = []

    for point in points:

        minute = point_minutes(
            point
        )

        state = point_state(
            point
        )

        if (
            minute is None
            or state is None
        ):
            continue

        pieces.append(
            f"+{minute}m:{state}"
        )

    return " -> ".join(
        pieces
    )


def build_cases() -> List[SeverityCase]:

    paths = base.build_v1317_research_paths()

    unique_paths = dedup_case_paths(
        paths
    )

    result = []

    for path in unique_paths:

        if path_direction(path) != (
            TARGET_DIRECTION
        ):
            continue

        points = sorted_points(
            path_points(path)
        )

        landmark_point = exact_landmark_point(
            points
        )

        if landmark_point is None:
            continue

        if point_state(landmark_point) != (
            TARGET_STATE
        ):
            continue

        # Exclude paths where PF already appeared
        # at or before the +30m landmark.
        first_pf = first_pf_minutes(
            points
        )

        if (
            first_pf is not None
            and first_pf <= LANDMARK_MINUTE
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

        if first_pf is None:

            outcome = landmark.NO_PF

        elif (
            first_pf > LANDMARK_MINUTE
            and first_pf <= 60
        ):

            outcome = landmark.LATE_PF

        else:

            outcome = landmark.NO_PF

        prior_state = None

        before = [
            point
            for point in points
            if (
                point_minutes(point) is not None
                and point_minutes(point)
                < LANDMARK_MINUTE
            )
        ]

        if before:

            prior_state = point_state(
                before[-1]
            )

        result.append(
            SeverityCase(
                symbol=path_symbol(path),
                direction=path_direction(path),
                outcome=outcome,
                predictor=predictor,
                first_pf_minutes=first_pf,
                return_pct=point_return(
                    landmark_point
                ),
                favorable_ratio=point_favorable_ratio(
                    landmark_point
                ),
                adverse_ratio=point_adverse_ratio(
                    landmark_point
                ),
                consecutive_adverse=(
                    point_consecutive_adverse(
                        landmark_point
                    )
                ),
                mae_pct=point_mae(
                    landmark_point
                ),
                mfe_pct=point_mfe(
                    landmark_point
                ),
                prior_state=prior_state,
                state_path_to_30m=format_path(
                    [
                        point
                        for point in points
                        if (
                            point_minutes(point)
                            is not None
                            and point_minutes(point)
                            <= LANDMARK_MINUTE
                        )
                    ]
                ),
            )
        )

    return result


def available_values(
    cases: Sequence[SeverityCase],
    attribute: str,
) -> List[float]:

    values = []

    for case in cases:

        value = getattr(
            case,
            attribute,
            None,
        )

        if value is None:
            continue

        values.append(
            float(value)
        )

    return values


def print_number_summary(
    label: str,
    cases: Sequence[SeverityCase],
    attribute: str,
) -> None:

    values = available_values(
        cases,
        attribute,
    )

    print()

    if not values:

        print(
            f"  {label:<24} N=0"
        )

        return

    print(
        f"  {label:<24} "
        f"N={len(values)} "
        f"AVG={mean(values):+.6f} "
        f"MEDIAN={median(values):+.6f} "
        f"MIN={min(values):+.6f} "
        f"MAX={max(values):+.6f}"
    )


def print_count_summary(
    label: str,
    cases: Sequence[SeverityCase],
    attribute: str,
) -> None:

    values = []

    for case in cases:

        value = getattr(
            case,
            attribute,
            None,
        )

        if value is None:
            continue

        values.append(
            int(value)
        )

    print()

    if not values:

        print(
            f"  {label:<24} N=0"
        )

        return

    print(
        f"  {label:<24} "
        f"N={len(values)} "
        f"AVG={mean(values):.3f} "
        f"MEDIAN={median(values):.3f} "
        f"MIN={min(values)} "
        f"MAX={max(values)}"
    )


def print_case_table(
    cases: Sequence[SeverityCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "EXACT +30M SEVERITY — TARGET CASES"
    )
    print("=" * 120)

    ordered = sorted(
        cases,
        key=lambda case: (
            case.predictor,
            case.symbol,
        ),
    )

    for case in ordered:

        print()
        print(
            f"{case.symbol:<6} "
            f"{case.predictor:<6} "
            f"OUTCOME={case.outcome:<18} "
            f"FIRST_PF="
            f"{('+' + str(case.first_pf_minutes) + 'm') if case.first_pf_minutes is not None else 'NONE'}"
        )

        print(
            f"  RETURN_PCT          = "
            f"{case.return_pct}"
        )

        print(
            f"  FAVORABLE_RATIO     = "
            f"{case.favorable_ratio}"
        )

        print(
            f"  ADVERSE_RATIO       = "
            f"{case.adverse_ratio}"
        )

        print(
            f"  CONSECUTIVE_ADVERSE = "
            f"{case.consecutive_adverse}"
        )

        print(
            f"  MAE_PCT             = "
            f"{case.mae_pct}"
        )

        print(
            f"  MFE_PCT             = "
            f"{case.mfe_pct}"
        )

        print(
            f"  PRIOR STATE         = "
            f"{case.prior_state}"
        )

        print(
            f"  PATH                 = "
            f"{case.state_path_to_30m}"
        )


def print_group_summary(
    name: str,
    cases: Sequence[SeverityCase],
) -> None:

    print()
    print("=" * 120)
    print(
        f"SEVERITY SUMMARY — {name}"
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

    print_number_summary(
        "RETURN_PCT",
        cases,
        "return_pct",
    )

    print_number_summary(
        "FAVORABLE_RATIO",
        cases,
        "favorable_ratio",
    )

    print_number_summary(
        "ADVERSE_RATIO",
        cases,
        "adverse_ratio",
    )

    print_count_summary(
        "CONSECUTIVE_ADVERSE",
        cases,
        "consecutive_adverse",
    )

    print_number_summary(
        "MAE_PCT",
        cases,
        "mae_pct",
    )

    print_number_summary(
        "MFE_PCT",
        cases,
        "mfe_pct",
    )


def print_outcome_severity(
    cases: Sequence[SeverityCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "SEVERITY BY OUTCOME"
    )
    print("=" * 120)

    later = [
        case
        for case in cases
        if case.outcome == landmark.LATE_PF
    ]

    no_pf = [
        case
        for case in cases
        if case.outcome == landmark.NO_PF
    ]

    print_group_summary(
        "LATER_PF_BY_60",
        later,
    )

    print_group_summary(
        "NO_PF_BY_60",
        no_pf,
    )


def print_overlap_view(
    failed: Sequence[SeverityCase],
    clean: Sequence[SeverityCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "FAILED-RECOVERY vs CLEAN — CURRENT SEVERITY OVERLAP"
    )
    print("=" * 120)

    print()
    print(
        "The audit does NOT create a severity score."
    )

    print(
        "Each variable is shown independently."
    )

    print()

    variables = (
        (
            "RETURN_PCT",
            "return_pct",
        ),
        (
            "FAVORABLE_RATIO",
            "favorable_ratio",
        ),
        (
            "ADVERSE_RATIO",
            "adverse_ratio",
        ),
        (
            "CONSECUTIVE_ADVERSE",
            "consecutive_adverse",
        ),
        (
            "MAE_PCT",
            "mae_pct",
        ),
        (
            "MFE_PCT",
            "mfe_pct",
        ),
    )

    for label, attribute in variables:

        failed_values = available_values(
            failed,
            attribute,
        )

        clean_values = available_values(
            clean,
            attribute,
        )

        print(
            f"{label}:"
        )

        print(
            f"  FAILED N={len(failed_values)} "
            f"VALUES="
            f"{failed_values}"
        )

        print(
            f"  CLEAN  N={len(clean_values)} "
            f"VALUES="
            f"{clean_values}"
        )

        if failed_values and clean_values:

            failed_min = min(
                failed_values
            )

            failed_max = max(
                failed_values
            )

            clean_min = min(
                clean_values
            )

            clean_max = max(
                clean_values
            )

            overlap_low = max(
                failed_min,
                clean_min,
            )

            overlap_high = min(
                failed_max,
                clean_max,
            )

            overlap = (
                overlap_low
                <= overlap_high
            )

            print(
                f"  RANGE OVERLAP = "
                f"{overlap}"
            )

            if overlap:

                print(
                    f"  OVERLAP RANGE = "
                    f"{overlap_low} "
                    f"to "
                    f"{overlap_high}"
                )


def print_interpretation(
    cases: Sequence[SeverityCase],
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

    print()
    print("=" * 120)
    print(
        "V13.17 PF PREDECESSOR SEVERITY "
        "— INTERPRETATION"
    )
    print("=" * 120)

    print()

    print(
        f"TARGET CASES = {len(cases)}"
    )

    print(
        f"FAILED-RECOVERY = {len(failed)}"
    )

    print(
        f"CLEAN = {len(clean)}"
    )

    print()

    print(
        "The purpose of this audit is to determine whether "
        "the two groups occupy similar or different current-state "
        "severity ranges at +30m."
    )

    print(
        "No composite severity score is constructed."
    )

    print(
        "No threshold is derived."
    )

    print(
        "No result becomes an entry, warning, rescue, hold, "
        "or exit rule."
    )

    print(
        "The sample remains very small."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print_header = print_header_function()

    print_header()

    cases = build_cases()

    print()
    print(
        f"TARGET CASES BUILT = {len(cases)}"
    )

    print_case_table(
        cases
    )

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

    print_group_summary(
        "RECOVERY_FAILED_BY_30M",
        failed,
    )

    print_group_summary(
        "NO_RECOVERY_FAILURE_BY_30M",
        clean,
    )

    print_outcome_severity(
        cases
    )

    print_overlap_view(
        failed,
        clean,
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 120)
    print(
        "V13.17 PF PREDECESSOR SEVERITY AUDIT COMPLETE"
    )
    print("=" * 120)


def print_header_function():

    def _print():

        print()
        print("=" * 120)
        print(
            "V13.17 PF PREDECESSOR SEVERITY AUDIT"
        )
        print("=" * 120)

        print()
        print(
            "TARGET: LONG +30M STATE = DETERIORATING"
        )

        print(
            "PREDICTOR: RECOVERY_FAILED_BY_30M"
        )

        print(
            "OUTCOME: PF AFTER +30M AND BY +60M"
        )

        print(
            "SEVERITY = exact +30m StatePoint measurements"
        )

        print(
            "NO FUTURE LEAKAGE"
        )

        print(
            "NO PRODUCTION CODE CHANGED"
        )

    return _print


if __name__ == "__main__":
    main()
