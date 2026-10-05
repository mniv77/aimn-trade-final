"""
AIMn / KISS V13.17 COMPANION RESEARCH

PF PREDECESSOR ENRICHMENT — +30 MINUTE LANDMARK AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
Among trajectories that have NOT yet reached PERSISTENT_FAILURE by +30m,
is a failed-recovery sequence during the first 30 minutes associated
with PERSISTENT_FAILURE occurring later?

LANDMARK DESIGN
---------------
The predictor is measured using StatePoints at or before +30m.

The outcome is measured ONLY AFTER +30m.

PREDICTOR
---------
RECOVERY_FAILED_BY_30M

Definition:

    RECOVERING
        followed later by
    DETERIORATING

with both observations occurring at or before +30m.

OUTCOME
-------
LATE_PF_BY_60M

A case is positive if:

    no PF at or before +30m
    AND
    PF appears at +45m or +60m

A case is negative if:

    no PF at or before +30m
    AND
    no PF by +60m

IMPORTANT
---------
Cases reaching PF at +30m or earlier are NOT eligible for this
landmark comparison.

That exclusion is intentional.

It prevents the future outcome from leaking into the predictor.

DIRECTION CONTROL
-----------------
LONG and SHORT are reported separately.

The pooled result is also reported, but it is not used as the
primary interpretation.

CASE KEY
--------
(symbol, direction, opposite_time)

One unique trajectory case per key.

NO PRODUCTION CODE CHANGED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_case_aware_validation as base
)


PERSISTENT = "PERSISTENT_FAILURE"
RECOVERING = "RECOVERING"
DETERIORATING = "DETERIORATING"
NEUTRAL = "NEUTRAL"

LANDMARK = 30
OUTCOME_END = 60

EARLY_PF_EXCLUDED = "EARLY_PF_EXCLUDED"
ELIGIBLE = "ELIGIBLE"
LATE_PF = "LATE_PF_BY_60"
NO_PF = "NO_PF_BY_60"

DIRECTIONS = (
    "LONG",
    "SHORT",
)


@dataclass
class LandmarkCase:
    case_key: Tuple[Any, Any, Any]

    symbol: str
    direction: str
    opposite_time: Any

    landmark_state: Optional[str]

    first_pf_minutes: Optional[int]

    eligible: bool

    recovery_failed_by_30m: bool

    last_recovering_minutes: Optional[int]

    first_deteriorating_after_recovery_minutes: Optional[int]

    outcome: str

    state_path_to_30m: Tuple[Tuple[int, str], ...]

    state_path_after_30m: Tuple[Tuple[int, str], ...]


def attr(
    obj: Any,
    *names: str,
    default: Any = None,
) -> Any:

    for name in names:

        if hasattr(obj, name):
            return getattr(obj, name)

    return default


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

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):

        return None


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


def path_opposite_time(
    path: Any,
) -> Any:

    return attr(
        path,
        "opposite_time",
        "transition_time",
        default=None,
    )


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


def first_pf_minutes(
    points: Sequence[Any],
) -> Optional[int]:

    for point in points:

        if point_state(point) == PERSISTENT:

            return point_minutes(point)

    return None


def has_pf_at_or_before(
    points: Sequence[Any],
    minute_limit: int,
) -> bool:

    for point in points:

        minute = point_minutes(point)

        if minute is None:
            continue

        if minute > minute_limit:
            continue

        if point_state(point) == PERSISTENT:
            return True

    return False


def exact_point(
    points: Sequence[Any],
    minute_target: int,
) -> Optional[Any]:

    for point in points:

        if point_minutes(point) == minute_target:
            return point

    return None


def recovery_failure_by_landmark(
    points: Sequence[Any],
) -> Tuple[
    bool,
    Optional[int],
    Optional[int],
]:

    landmark_points = [
        point
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point) <= LANDMARK
        )
    ]

    last_recovering_minutes = None

    for point in reversed(landmark_points):

        if point_state(point) == RECOVERING:

            last_recovering_minutes = (
                point_minutes(point)
            )

            break

    if last_recovering_minutes is None:

        return (
            False,
            None,
            None,
        )

    first_deteriorating_after_recovery_minutes = None

    for point in landmark_points:

        minute = point_minutes(point)

        if minute is None:
            continue

        if minute <= last_recovering_minutes:
            continue

        if point_state(point) == DETERIORATING:

            first_deteriorating_after_recovery_minutes = (
                minute
            )

            break

    failed = (
        first_deteriorating_after_recovery_minutes
        is not None
    )

    return (
        failed,
        last_recovering_minutes,
        first_deteriorating_after_recovery_minutes,
    )


def build_case(
    path: Any,
) -> Optional[LandmarkCase]:

    points = sorted_points(
        path_points(path)
    )

    if not points:
        return None

    landmark_point = exact_point(
        points,
        LANDMARK,
    )

    if landmark_point is None:
        return None

    first_pf = first_pf_minutes(
        points
    )

    # Any PF occurring on or before the landmark
    # makes this case ineligible.
    eligible = not has_pf_at_or_before(
        points,
        LANDMARK,
    )

    if not eligible:

        outcome = (
            EARLY_PF_EXCLUDED
        )

        recovery_failed = False
        last_recovering = None
        first_deteriorating = None

    else:

        (
            recovery_failed,
            last_recovering,
            first_deteriorating,
        ) = recovery_failure_by_landmark(
            points
        )

        # PF AFTER the +30m landmark and by +60m.
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

        if later_pf:

            outcome = LATE_PF

        else:

            outcome = NO_PF

    state_path_to_30m = tuple(
        (
            point_minutes(point),
            point_state(point),
        )
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point) <= LANDMARK
            and point_state(point) is not None
        )
    )

    state_path_after_30m = tuple(
        (
            point_minutes(point),
            point_state(point),
        )
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point) > LANDMARK
            and point_minutes(point) <= OUTCOME_END
            and point_state(point) is not None
        )
    )

    return LandmarkCase(
        case_key=(
            path_symbol(path),
            path_direction(path),
            path_opposite_time(path),
        ),
        symbol=path_symbol(path),
        direction=path_direction(path),
        opposite_time=path_opposite_time(path),
        landmark_state=point_state(
            landmark_point
        ),
        first_pf_minutes=first_pf,
        eligible=eligible,
        recovery_failed_by_30m=recovery_failed,
        last_recovering_minutes=last_recovering,
        first_deteriorating_after_recovery_minutes=(
            first_deteriorating
        ),
        outcome=outcome,
        state_path_to_30m=state_path_to_30m,
        state_path_after_30m=state_path_after_30m,
    )


def build_cases() -> List[LandmarkCase]:

    paths = base.build_v1317_research_paths()

    unique_paths = dedup_case_paths(
        paths
    )

    result = []

    for path in unique_paths:

        case = build_case(path)

        if case is None:
            continue

        result.append(case)

    return result


def print_header() -> None:

    print()
    print("=" * 115)
    print(
        "V13.17 PF PREDECESSOR ENRICHMENT "
        "— +30M LANDMARK AUDIT"
    )
    print("=" * 115)

    print()
    print(
        "PREDICTOR:"
    )
    print(
        "  RECOVERING -> DETERIORATING "
        "BY +30M"
    )

    print()
    print(
        "OUTCOME:"
    )
    print(
        "  PF AFTER +30M AND BY +60M"
    )

    print()
    print(
        "Cases reaching PF by +30m are excluded."
    )

    print(
        "LONG and SHORT are reported separately."
    )

    print(
        "No future information is used for predictor classification."
    )

    print(
        "No production code changed."
    )


def print_population(
    cases: Sequence[LandmarkCase],
) -> None:

    print()
    print("=" * 115)
    print(
        "LANDMARK POPULATION"
    )
    print("=" * 115)

    total = len(cases)

    excluded = sum(
        case.outcome == EARLY_PF_EXCLUDED
        for case in cases
    )

    eligible = sum(
        case.eligible
        for case in cases
    )

    later_pf = sum(
        case.outcome == LATE_PF
        for case in cases
    )

    no_pf = sum(
        case.outcome == NO_PF
        for case in cases
    )

    print()
    print(
        f"TOTAL CASES             = {total}"
    )

    print(
        f"EARLY PF EXCLUDED       = {excluded}"
    )

    print(
        f"ELIGIBLE AT +30M        = {eligible}"
    )

    print(
        f"LATER PF BY +60M       = {later_pf}"
    )

    print(
        f"NO PF BY +60M           = {no_pf}"
    )


def print_direction_population(
    cases: Sequence[LandmarkCase],
) -> None:

    print()
    print("=" * 115)
    print(
        "LANDMARK POPULATION BY DIRECTION"
    )
    print("=" * 115)

    for direction in DIRECTIONS:

        direction_cases = [
            case
            for case in cases
            if case.direction == direction
        ]

        eligible = [
            case
            for case in direction_cases
            if case.eligible
        ]

        later_pf = [
            case
            for case in eligible
            if case.outcome == LATE_PF
        ]

        no_pf = [
            case
            for case in eligible
            if case.outcome == NO_PF
        ]

        print()
        print(
            f"DIRECTION = {direction}"
        )

        print(
            f"  TOTAL              = "
            f"{len(direction_cases)}"
        )

        print(
            f"  EARLY PF EXCLUDED  = "
            f"{sum(case.outcome == EARLY_PF_EXCLUDED for case in direction_cases)}"
        )

        print(
            f"  ELIGIBLE            = "
            f"{len(eligible)}"
        )

        print(
            f"  LATER PF            = "
            f"{len(later_pf)}"
        )

        print(
            f"  NO PF                = "
            f"{len(no_pf)}"
        )


def print_exact_cases(
    cases: Sequence[LandmarkCase],
) -> None:

    print()
    print("=" * 115)
    print(
        "EXACT LANDMARK CASES"
    )
    print("=" * 115)

    for direction in DIRECTIONS:

        print()
        print(
            f"DIRECTION = {direction}"
        )

        direction_cases = [
            case
            for case in cases
            if case.direction == direction
        ]

        for case in sorted(
            direction_cases,
            key=lambda item: (
                item.first_pf_minutes
                if item.first_pf_minutes is not None
                else 999,
                item.symbol,
            ),
        ):

            print()
            print(
                f"{case.symbol:<6} "
                f"{case.direction:<5} "
                f"OUTCOME={case.outcome:<18} "
                f"FIRST_PF="
                f"{('+' + str(case.first_pf_minutes) + 'm') if case.first_pf_minutes is not None else 'NONE'}"
            )

            print(
                f"  LANDMARK STATE       = "
                f"{case.landmark_state}"
            )

            print(
                f"  RECOVERY FAILED      = "
                f"{case.recovery_failed_by_30m}"
            )

            print(
                f"  LAST RECOVERING      = "
                f"{('+' + str(case.last_recovering_minutes) + 'm') if case.last_recovering_minutes is not None else 'NONE'}"
            )

            print(
                f"  FIRST DETERIORATING  = "
                f"{('+' + str(case.first_deteriorating_after_recovery_minutes) + 'm') if case.first_deteriorating_after_recovery_minutes is not None else 'NONE'}"
            )

            before = " -> ".join(
                f"+{minute}m:{state}"
                for minute, state
                in case.state_path_to_30m
            )

            after = " -> ".join(
                f"+{minute}m:{state}"
                for minute, state
                in case.state_path_after_30m
            )

            print(
                f"  PRE-30M PATH         = "
                f"{before}"
            )

            print(
                f"  POST-30M PATH        = "
                f"{after}"
            )


def print_enrichment(
    cases: Sequence[LandmarkCase],
    direction: Optional[str] = None,
) -> None:

    eligible = [
        case
        for case in cases
        if (
            case.eligible
            and (
                direction is None
                or case.direction == direction
            )
        )
    ]

    failed_recovery = [
        case
        for case in eligible
        if case.recovery_failed_by_30m
    ]

    no_failed_recovery = [
        case
        for case in eligible
        if not case.recovery_failed_by_30m
    ]

    failed_total = len(
        failed_recovery
    )

    failed_late_pf = sum(
        case.outcome == LATE_PF
        for case in failed_recovery
    )

    clean_total = len(
        no_failed_recovery
    )

    clean_late_pf = sum(
        case.outcome == LATE_PF
        for case in no_failed_recovery
    )

    print()
    print("=" * 115)

    if direction is None:
        print(
            "ENRICHMENT — POOLED"
        )
    else:
        print(
            f"ENRICHMENT — {direction}"
        )

    print("=" * 115)

    print()

    print(
        "RECOVERY_FAILED_BY_30M"
    )

    print(
        f"  CASES             = "
        f"{failed_total}"
    )

    print(
        f"  LATER PF BY +60M = "
        f"{failed_late_pf}"
    )

    if failed_total:
        print(
            f"  LATER PF RATE     = "
            f"{failed_late_pf / failed_total:.4f}"
        )
    else:
        print(
            "  LATER PF RATE     = NA"
        )

    print()

    print(
        "NO RECOVERY FAILURE BY +30M"
    )

    print(
        f"  CASES             = "
        f"{clean_total}"
    )

    print(
        f"  LATER PF BY +60M = "
        f"{clean_late_pf}"
    )

    if clean_total:
        print(
            f"  LATER PF RATE     = "
            f"{clean_late_pf / clean_total:.4f}"
        )
    else:
        print(
            "  LATER PF RATE     = NA"
        )

    print()

    if (
        failed_total
        and clean_total
    ):

        failed_rate = (
            failed_late_pf
            / failed_total
        )

        clean_rate = (
            clean_late_pf
            / clean_total
        )

        enrichment_ratio = None

        if clean_rate > 0:
            enrichment_ratio = (
                failed_rate
                / clean_rate
            )

        print(
            f"DESCRIPTIVE RATE DELTA = "
            f"{failed_rate - clean_rate:+.4f}"
        )

        if enrichment_ratio is None:
            print(
                "DESCRIPTIVE RATE RATIO = NA"
            )
        else:
            print(
                f"DESCRIPTIVE RATE RATIO = "
                f"{enrichment_ratio:.4f}"
            )

    else:

        print(
            "DESCRIPTIVE COMPARISON = "
            "NOT AVAILABLE"
        )

    print()

    print(
        "This is descriptive enrichment only."
    )


def print_pattern_counts(
    cases: Sequence[LandmarkCase],
) -> None:

    print()
    print("=" * 115)
    print(
        "PREDICTOR x OUTCOME CONTINGENCY"
    )
    print("=" * 115)

    eligible = [
        case
        for case in cases
        if case.eligible
    ]

    for predictor in (
        True,
        False,
    ):

        label = (
            "RECOVERY_FAILED_BY_30M"
            if predictor
            else "NO_RECOVERY_FAILURE_BY_30M"
        )

        group = [
            case
            for case in eligible
            if case.recovery_failed_by_30m == predictor
        ]

        later = sum(
            case.outcome == LATE_PF
            for case in group
        )

        no_pf = sum(
            case.outcome == NO_PF
            for case in group
        )

        print()
        print(
            f"{label}"
        )

        print(
            f"  LATER_PF_BY_60M = "
            f"{later}"
        )

        print(
            f"  NO_PF_BY_60M    = "
            f"{no_pf}"
        )

        print(
            f"  TOTAL           = "
            f"{len(group)}"
        )


def print_interpretation(
    cases: Sequence[LandmarkCase],
) -> None:

    eligible = [
        case
        for case in cases
        if case.eligible
    ]

    later_pf = [
        case
        for case in eligible
        if case.outcome == LATE_PF
    ]

    failed = [
        case
        for case in eligible
        if case.recovery_failed_by_30m
    ]

    clean = [
        case
        for case in eligible
        if not case.recovery_failed_by_30m
    ]

    print()
    print("=" * 115)
    print(
        "V13.17 PF PREDECESSOR ENRICHMENT "
        "— INTERPRETATION"
    )
    print("=" * 115)

    print()

    print(
        f"ELIGIBLE CASES AT +30M = "
        f"{len(eligible)}"
    )

    print(
        f"LATER PF CASES          = "
        f"{len(later_pf)}"
    )

    print(
        f"RECOVERY-FAILED CASES   = "
        f"{len(failed)}"
    )

    print(
        f"OTHER PRE-PF CASES      = "
        f"{len(clean)}"
    )

    print()

    print(
        "The predictor is measured entirely at or before +30m."
    )

    print(
        "The outcome is measured only after +30m."
    )

    print(
        "Cases reaching PF by +30m are excluded."
    )

    print(
        "This prevents PF outcome information from defining "
        "the predictor."
    )

    print()

    print(
        "A rate difference would be evidence of descriptive "
        "association only."
    )

    print(
        "It would NOT establish causality."
    )

    print(
        "The sample remains too small for promotion to a rule."
    )

    print(
        "No result becomes an entry, warning, rescue, hold, "
        "or exit rule."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print_header()

    cases = build_cases()

    print()
    print(
        f"TOTAL BUILT CASES = "
        f"{len(cases)}"
    )

    print_population(
        cases
    )

    print_direction_population(
        cases
    )

    print_exact_cases(
        cases
    )

    print_pattern_counts(
        cases
    )

    print_enrichment(
        cases,
        direction="LONG",
    )

    print_enrichment(
        cases,
        direction="SHORT",
    )

    print_enrichment(
        cases,
        direction=None,
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 115)
    print(
        "V13.17 PF PREDECESSOR ENRICHMENT "
        "LANDMARK AUDIT COMPLETE"
    )
    print("=" * 115)


if __name__ == "__main__":
    main()
