"""
AIMn / KISS V13.17 COMPANION RESEARCH
PERSISTENT FAILURE COHORT RETURN AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
Does FIRST PERSISTENT_FAILURE behave differently depending on the
trajectory immediately preceding it?

PRIMARY COHORTS
---------------

A) DIRECT_FROM_DETERIORATING
   DETERIORATING -> PERSISTENT_FAILURE

B) RECOVERY_FAILED_THEN_DETERIORATING
   RECOVERING -> ... -> DETERIORATING -> PERSISTENT_FAILURE

OTHER CASES
-----------
DIRECT_FROM_NEUTRAL
OTHER_OR_UNKNOWN

These other cases are reported separately and are NOT forced into
either primary cohort.

CASE KEY
--------
(symbol, direction, opposite_time)

IMPORTANT
---------
One first PF onset is used per unique trajectory case.

Future returns are measured FROM THE FIRST PF ONSET checkpoint.

LONG:
    future return relative to PF-onset price

SHORT:
    signed future return relative to PF-onset price

Only exact StatePoints are used.

NO FUTURE INFORMATION is used to classify the cohort itself.

This is descriptive research only.
It does NOT create an entry, warning, rescue, hold, or exit rule.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_case_aware_validation as base
)

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_persistent_failure_predecessor_audit
    as predecessor
)


SYMBOLS = (
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "TSLA",
    "SPY",
    "QQQ",
    "GOOGL",
)

PERSISTENT = "PERSISTENT_FAILURE"

DIRECT = "DIRECT_FROM_DETERIORATING"
FAILED_RECOVERY = (
    "RECOVERY_FAILED_THEN_DETERIORATING"
)

DIRECT_NEUTRAL = "DIRECT_FROM_NEUTRAL"
OTHER = "OTHER_OR_UNKNOWN"

PRIMARY_COHORTS = (
    DIRECT,
    FAILED_RECOVERY,
)

HORIZONS = (
    5,
    10,
    15,
    20,
    30,
)


@dataclass
class CohortCase:
    case_key: Tuple[Any, Any, Any]

    symbol: str
    direction: str
    opposite_time: Any

    onset_minutes: int
    timing_group: str
    onset_return_pct: Optional[float]

    cohort: str
    prior_state: Optional[str]

    future_returns: Dict[int, Optional[float]]


def attr(
    obj: Any,
    *names: str,
    default: Any = None,
) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def point_minutes(point: Any) -> Optional[int]:
    value = attr(
        point,
        "minutes",
        "minute",
        "offset_minutes",
        default=None,
    )

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def point_state(point: Any) -> Optional[str]:
    value = attr(
        point,
        "state",
        "current_state",
        default=None,
    )

    if value is None:
        return None

    return str(value)


def point_return(point: Any) -> Optional[float]:
    value = attr(
        point,
        "return_pct",
        "signed_return_pct",
        default=None,
    )

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def path_symbol(path: Any) -> str:
    return str(
        attr(path, "symbol", default="")
    )


def path_direction(path: Any) -> str:
    return str(
        attr(path, "direction", default="")
    ).upper()


def path_opposite_time(path: Any) -> Any:
    return attr(
        path,
        "opposite_time",
        "transition_time",
        default=None,
    )


def path_points(path: Any) -> List[Any]:
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


def dedup_case_paths(
    paths: Iterable[Any],
) -> List[Any]:

    seen = set()
    result = []

    for path in paths:

        key = (
            path_symbol(path),
            path_direction(path),
            path_opposite_time(path),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(path)

    return result


def future_return_from_checkpoint(
    direction: str,
    current_return_pct: Optional[float],
    future_return_pct: Optional[float],
) -> Optional[float]:
    """
    Calculate signed return from PF-onset checkpoint to future checkpoint.

    LONG:
        price factor = 1 + return

    SHORT:
        price factor = 1 - return
    """

    if (
        current_return_pct is None
        or future_return_pct is None
    ):
        return None

    current = current_return_pct / 100.0
    future = future_return_pct / 100.0

    direction = direction.upper()

    if direction == "LONG":

        current_factor = 1.0 + current
        future_factor = 1.0 + future

        if current_factor == 0:
            return None

        return (
            future_factor / current_factor - 1.0
        ) * 100.0

    if direction == "SHORT":

        current_factor = 1.0 - current
        future_factor = 1.0 - future

        if current_factor == 0:
            return None

        return (
            1.0 - future_factor / current_factor
        ) * 100.0

    return None


def build_path_map() -> Dict[Tuple[Any, Any, Any], Any]:

    paths = base.build_v1317_research_paths()

    unique_paths = dedup_case_paths(paths)

    result = {}

    for path in unique_paths:

        key = (
            path_symbol(path),
            path_direction(path),
            path_opposite_time(path),
        )

        result[key] = path

    return result


def build_cohort_case(
    predecessor_case: Any,
    path_map: Dict[Tuple[Any, Any, Any], Any],
) -> Optional[CohortCase]:

    cohort = predecessor_case.predecessor_pattern

    if cohort not in (
        DIRECT,
        FAILED_RECOVERY,
        DIRECT_NEUTRAL,
        OTHER,
    ):
        return None

    if cohort not in PRIMARY_COHORTS:
        return None

    path = path_map.get(
        predecessor_case.case_key
    )

    if path is None:
        return None

    points = sorted_points(
        path_points(path)
    )

    if not points:
        return None

    onset_minutes = (
        predecessor_case.onset_minutes
    )

    onset_point = None

    for point in points:

        minute = point_minutes(point)

        if minute != onset_minutes:
            continue

        if point_state(point) != PERSISTENT:
            continue

        onset_point = point
        break

    if onset_point is None:
        return None

    onset_return_pct = point_return(
        onset_point
    )

    future_returns = {}

    for horizon in HORIZONS:

        target_minute = (
            onset_minutes + horizon
        )

        future_point = None

        for point in points:

            if point_minutes(point) != target_minute:
                continue

            future_point = point
            break

        if future_point is None:
            future_returns[horizon] = None
            continue

        future_returns[horizon] = (
            future_return_from_checkpoint(
                predecessor_case.direction,
                onset_return_pct,
                point_return(future_point),
            )
        )

    return CohortCase(
        case_key=predecessor_case.case_key,
        symbol=predecessor_case.symbol,
        direction=predecessor_case.direction,
        opposite_time=predecessor_case.opposite_time,
        onset_minutes=onset_minutes,
        timing_group=predecessor_case.timing_group,
        onset_return_pct=onset_return_pct,
        cohort=cohort,
        prior_state=predecessor_case.prior_state,
        future_returns=future_returns,
    )


def build_cases() -> List[CohortCase]:

    predecessor_cases = (
        predecessor.build_cases()
    )

    path_map = build_path_map()

    cases = []

    for predecessor_case in predecessor_cases:

        if (
            predecessor_case.symbol
            not in SYMBOLS
        ):
            continue

        case = build_cohort_case(
            predecessor_case,
            path_map,
        )

        if case is None:
            continue

        cases.append(case)

    return cases


def values_at_horizon(
    cases: Sequence[CohortCase],
    horizon: int,
) -> List[float]:

    values = []

    for case in cases:

        value = case.future_returns.get(
            horizon
        )

        if value is None:
            continue

        values.append(value)

    return values


def print_header() -> None:

    print()
    print("=" * 110)
    print(
        "V13.17 PERSISTENT FAILURE COHORT RETURN AUDIT"
    )
    print("=" * 110)

    print()
    print(
        "PRIMARY COHORT A:"
    )
    print(
        "  DIRECT_FROM_DETERIORATING"
    )
    print(
        "  DETERIORATING -> PERSISTENT_FAILURE"
    )

    print()
    print(
        "PRIMARY COHORT B:"
    )
    print(
        "  RECOVERY_FAILED_THEN_DETERIORATING"
    )
    print(
        "  RECOVERING -> ... -> DETERIORATING -> "
        "PERSISTENT_FAILURE"
    )

    print()
    print(
        "Future returns are measured FROM FIRST PF ONSET."
    )
    print(
        "Only exact StatePoints are used."
    )
    print(
        "No production code changed."
    )


def print_case_details(
    cases: Sequence[CohortCase],
) -> None:

    print()
    print("=" * 110)
    print(
        "PRIMARY COHORT CASE DETAILS"
    )
    print("=" * 110)

    ordered = sorted(
        cases,
        key=lambda case: (
            case.cohort,
            case.onset_minutes,
            case.symbol,
            case.direction,
        ),
    )

    for index, case in enumerate(
        ordered,
        start=1,
    ):

        print()
        print(
            "-" * 110
        )
        print(
            f"CASE {index}"
        )
        print(
            "-" * 110
        )

        print(
            f"  {case.symbol:<6} "
            f"{case.direction:<5} "
            f"PF_ONSET=+{case.onset_minutes}m "
            f"GROUP={case.timing_group}"
        )

        print(
            f"  COHORT             = "
            f"{case.cohort}"
        )

        print(
            f"  PRIOR STATE        = "
            f"{case.prior_state}"
        )

        print(
            f"  ONSET RETURN       = "
            f"{case.onset_return_pct}"
        )

        for horizon in HORIZONS:

            value = case.future_returns.get(
                horizon
            )

            if value is None:

                print(
                    f"  FUTURE +{horizon:<2}m    = NA"
                )

            else:

                print(
                    f"  FUTURE +{horizon:<2}m    = "
                    f"{value:+.6f}%"
                )


def print_return_summary(
    cohort_name: str,
    cases: Sequence[CohortCase],
) -> None:

    print()
    print(
        "=" * 110
    )
    print(
        f"RETURN SUMMARY — {cohort_name}"
    )
    print(
        "=" * 110
    )

    print()
    print(
        f"CASES = {len(cases)}"
    )

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

        print(
            f"  CASES = "
            f"{len(direction_cases)}"
        )

        for horizon in HORIZONS:

            values = values_at_horizon(
                direction_cases,
                horizon,
            )

            if not values:

                print(
                    f"  +{horizon:<2}m "
                    f"N=0"
                )

                continue

            positive = sum(
                value > 0
                for value in values
            )

            negative = sum(
                value < 0
                for value in values
            )

            zero = sum(
                value == 0
                for value in values
            )

            print(
                f"  +{horizon:<2}m "
                f"N={len(values)} "
                f"AVG={mean(values):+.6f}% "
                f"MEDIAN={median(values):+.6f}% "
                f"POS={positive} "
                f"NEG={negative} "
                f"ZERO={zero}"
            )


def print_pooled_summary(
    cases: Sequence[CohortCase],
) -> None:

    print()
    print(
        "=" * 110
    )
    print(
        "POOLED PRIMARY COHORT RETURN SUMMARY"
    )
    print(
        "=" * 110
    )

    for cohort in PRIMARY_COHORTS:

        cohort_cases = [
            case
            for case in cases
            if case.cohort == cohort
        ]

        print()
        print(
            f"COHORT = {cohort}"
        )

        print(
            f"  CASES = {len(cohort_cases)}"
        )

        for horizon in HORIZONS:

            values = values_at_horizon(
                cohort_cases,
                horizon,
            )

            if not values:

                print(
                    f"  +{horizon:<2}m "
                    f"N=0"
                )

                continue

            positive = sum(
                value > 0
                for value in values
            )

            negative = sum(
                value < 0
                for value in values
            )

            print(
                f"  +{horizon:<2}m "
                f"N={len(values)} "
                f"AVG={mean(values):+.6f}% "
                f"MEDIAN={median(values):+.6f}% "
                f"POS={positive} "
                f"NEG={negative}"
            )


def print_timing_summary(
    cases: Sequence[CohortCase],
) -> None:

    print()
    print(
        "=" * 110
    )
    print(
        "PRIMARY COHORTS BY PF ONSET TIMING"
    )
    print(
        "=" * 110
    )

    for cohort in PRIMARY_COHORTS:

        print()
        print(
            f"COHORT = {cohort}"
        )

        for timing_group in (
            "EARLY_PF",
            "LATE_PF",
        ):

            group_cases = [
                case
                for case in cases
                if (
                    case.cohort == cohort
                    and case.timing_group
                    == timing_group
                )
            ]

            print(
                f"  {timing_group:<10} "
                f"CASES={len(group_cases)}"
            )


def print_exact_comparison(
    cases: Sequence[CohortCase],
) -> None:

    print()
    print(
        "=" * 110
    )
    print(
        "DIRECT VS FAILED-RECOVERY — EXACT CASE LIST"
    )
    print(
        "=" * 110
    )

    for cohort in PRIMARY_COHORTS:

        cohort_cases = [
            case
            for case in cases
            if case.cohort == cohort
        ]

        print()
        print(
            f"COHORT = {cohort}"
        )

        for case in sorted(
            cohort_cases,
            key=lambda item: (
                item.onset_minutes,
                item.symbol,
                item.direction,
            ),
        ):

            returns = []

            for horizon in HORIZONS:

                value = case.future_returns.get(
                    horizon
                )

                if value is None:
                    returns.append(
                        f"+{horizon}m=NA"
                    )
                else:
                    returns.append(
                        f"+{horizon}m={value:+.4f}%"
                    )

            print(
                f"{case.symbol:<6} "
                f"{case.direction:<5} "
                f"PF_ONSET=+{case.onset_minutes:<2}m "
                f"{case.timing_group:<10} "
                + " ".join(returns)
            )


def print_interpretation(
    cases: Sequence[CohortCase],
) -> None:

    print()
    print(
        "=" * 110
    )
    print(
        "V13.17 PF COHORT RETURN — INTERPRETATION"
    )
    print(
        "=" * 110
    )

    direct = [
        case
        for case in cases
        if case.cohort == DIRECT
    ]

    failed = [
        case
        for case in cases
        if case.cohort == FAILED_RECOVERY
    ]

    print()
    print(
        f"DIRECT_FROM_DETERIORATING CASES = "
        f"{len(direct)}"
    )

    print(
        f"FAILED_RECOVERY CASES            = "
        f"{len(failed)}"
    )

    print()
    print(
        "The comparison is descriptive."
    )

    print(
        "It does NOT establish that failed recovery "
        "causes a different future."
    )

    print(
        "The sample is small and direction is separated."
    )

    print(
        "No result becomes an entry, warning, rescue, "
        "hold, or exit rule."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print_header()

    cases = build_cases()

    print()
    print(
        f"PRIMARY COHORT CASES = "
        f"{len(cases)}"
    )

    print_case_details(
        cases
    )

    for cohort in PRIMARY_COHORTS:

        cohort_cases = [
            case
            for case in cases
            if case.cohort == cohort
        ]

        print_return_summary(
            cohort,
            cohort_cases,
        )

    print_pooled_summary(
        cases
    )

    print_timing_summary(
        cases
    )

    print_exact_comparison(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print(
        "=" * 110
    )
    print(
        "V13.17 PERSISTENT FAILURE COHORT RETURN AUDIT COMPLETE"
    )
    print(
        "=" * 110
    )


if __name__ == "__main__":
    main()
