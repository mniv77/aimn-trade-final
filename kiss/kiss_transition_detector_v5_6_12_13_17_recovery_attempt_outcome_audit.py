"""
AIMn / KISS V13.17 COMPANION RESEARCH

RECOVERY ATTEMPT OUTCOME AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
Among trajectories that actually attempted recovery before +30m,
does the OUTCOME of that recovery attempt relate to later
PERSISTENT_FAILURE?

PRIMARY COMPARISON
------------------
A) RECOVERY_FAILED

    RECOVERING
        ->
    DETERIORATING

    by +30m

versus

B) RECOVERY_HELD

    RECOVERING
        and
    no later DETERIORATING after the last recovery state

    by +30m

IMPORTANT
---------
Cases with NO RECOVERING state by +30m are excluded from the
primary comparison.

This avoids comparing:

    failed recovery

against

    a case that never attempted recovery.

OUTCOME
-------
LATER PF:

    no PF by +30m
    AND
    PF at +45m or +60m

CONTROL
-------
LONG and SHORT are reported separately.

The pooled result is also shown descriptively.

SECONDARY VIEW
--------------
The +30m state is reported so we can see whether recovery outcome
is mostly just a reflection of current state.

NO FUTURE LEAKAGE
-----------------
Recovery outcome is determined entirely by StatePoints at or before
+30m.

Later PF is measured only after +30m.

NO PRODUCTION CODE CHANGED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_case_aware_validation
    as base
)


RECOVERING = "RECOVERING"
DETERIORATING = "DETERIORATING"
PERSISTENT = "PERSISTENT_FAILURE"

LATER_PF = "LATER_PF_BY_60"
NO_PF = "NO_PF_BY_60"
EARLY_EXCLUDED = "EARLY_PF_EXCLUDED"

FAILED = "RECOVERY_FAILED"
HELD = "RECOVERY_HELD"

DIRECTIONS = (
    "LONG",
    "SHORT",
)

LANDMARK = 30
OUTCOME_END = 60


@dataclass
class RecoveryAttemptCase:
    symbol: str
    direction: str

    first_pf_minutes: Optional[int]

    landmark_state: str

    recovery_outcome: str

    last_recovering_minutes: Optional[int]

    first_deteriorating_after_recovery_minutes: Optional[int]

    outcome: str

    state_path_to_30m: Tuple[Tuple[int, str], ...]


def attr(
    obj: Any,
    *names: str,
    default: Any = None,
) -> Any:

    for name in names:

        if hasattr(obj, name):
            return getattr(obj, name)

    return default


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

    return str(
        value
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


def sorted_points(
    points: Sequence[Any],
) -> List[Any]:

    valid = []

    for point in points:

        minute = point_minutes(
            point
        )

        state = point_state(
            point
        )

        if minute is None or state is None:
            continue

        valid.append(
            point
        )

    return sorted(
        valid,
        key=lambda point: point_minutes(point)
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

        if point_state(point) == PERSISTENT:

            return point_minutes(
                point
            )

    return None


def exact_landmark_point(
    points: Sequence[Any],
) -> Optional[Any]:

    for point in points:

        if point_minutes(point) == LANDMARK:
            return point

    return None


def has_pf_at_or_before_30m(
    points: Sequence[Any],
) -> bool:

    for point in points:

        minute = point_minutes(
            point
        )

        if minute is None:
            continue

        if minute > LANDMARK:
            continue

        if point_state(point) == PERSISTENT:
            return True

    return False


def classify_recovery_attempt(
    points: Sequence[Any],
) -> Tuple[
    Optional[str],
    Optional[int],
    Optional[int],
]:

    pre_landmark = [
        point
        for point in points
        if (
            point_minutes(point) is not None
            and point_minutes(point) <= LANDMARK
        )
    ]

    recovering_points = [
        point
        for point in pre_landmark
        if point_state(point) == RECOVERING
    ]

    if not recovering_points:

        return (
            None,
            None,
            None,
        )

    last_recovering = recovering_points[-1]

    last_recovering_minutes = point_minutes(
        last_recovering
    )

    if last_recovering_minutes is None:

        return (
            None,
            None,
            None,
        )

    first_deteriorating_after_recovery = None

    for point in pre_landmark:

        minute = point_minutes(
            point
        )

        if minute is None:
            continue

        if minute <= last_recovering_minutes:
            continue

        if point_state(point) == DETERIORATING:

            first_deteriorating_after_recovery = (
                minute
            )

            break

    if first_deteriorating_after_recovery is not None:

        return (
            FAILED,
            last_recovering_minutes,
            first_deteriorating_after_recovery,
        )

    return (
        HELD,
        last_recovering_minutes,
        None,
    )


def determine_outcome(
    points: Sequence[Any],
) -> str:

    for point in points:

        minute = point_minutes(
            point
        )

        if minute is None:
            continue

        if minute <= LANDMARK:
            continue

        if minute > OUTCOME_END:
            continue

        if point_state(point) == PERSISTENT:

            return LATER_PF

    return NO_PF


def format_path(
    points: Sequence[Any],
) -> Tuple[Tuple[int, str], ...]:

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

        if minute > LANDMARK:
            continue

        result.append(
            (
                minute,
                state,
            )
        )

    return tuple(
        result
    )


def build_cases() -> List[RecoveryAttemptCase]:

    paths = base.build_v1317_research_paths()

    unique_paths = dedup_case_paths(
        paths
    )

    cases = []

    for path in unique_paths:

        points = sorted_points(
            path_points(path)
        )

        if not points:
            continue

        landmark_point = exact_landmark_point(
            points
        )

        if landmark_point is None:
            continue

        first_pf = first_pf_minutes(
            points
        )

        if has_pf_at_or_before_30m(
            points
        ):

            recovery_outcome = EARLY_EXCLUDED
            last_recovering = None
            first_deteriorating = None

        else:

            (
                recovery_outcome,
                last_recovering,
                first_deteriorating,
            ) = classify_recovery_attempt(
                points
            )

            if recovery_outcome is None:
                continue

        if recovery_outcome == EARLY_EXCLUDED:

            continue

        outcome = determine_outcome(
            points
        )

        cases.append(
            RecoveryAttemptCase(
                symbol=path_symbol(path),
                direction=path_direction(path),
                first_pf_minutes=first_pf,
                landmark_state=point_state(
                    landmark_point
                ) or "",
                recovery_outcome=recovery_outcome,
                last_recovering_minutes=last_recovering,
                first_deteriorating_after_recovery_minutes=(
                    first_deteriorating
                ),
                outcome=outcome,
                state_path_to_30m=format_path(
                    points
                ),
            )
        )

    return cases


def print_header() -> None:

    print()
    print("=" * 120)
    print(
        "V13.17 RECOVERY ATTEMPT OUTCOME AUDIT"
    )
    print("=" * 120)

    print()
    print(
        "PRIMARY COMPARISON:"
    )

    print(
        "  RECOVERY_FAILED"
    )

    print(
        "  RECOVERY_HELD"
    )

    print()
    print(
        "NO-RECOVERY CASES ARE EXCLUDED."
    )

    print()
    print(
        "PF BY +30m IS EXCLUDED."
    )

    print()
    print(
        "OUTCOME = PF AFTER +30m AND BY +60m."
    )

    print()
    print(
        "LONG and SHORT are reported separately."
    )

    print(
        "No future information is used to classify recovery outcome."
    )

    print(
        "No production code changed."
    )


def print_population(
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    failed = [
        case
        for case in cases
        if case.recovery_outcome == FAILED
    ]

    held = [
        case
        for case in cases
        if case.recovery_outcome == HELD
    ]

    print()
    print("=" * 120)
    print(
        "RECOVERY ATTEMPT POPULATION"
    )
    print("=" * 120)

    print()
    print(
        f"TOTAL RECOVERY ATTEMPT CASES = "
        f"{len(cases)}"
    )

    print(
        f"RECOVERY_FAILED              = "
        f"{len(failed)}"
    )

    print(
        f"RECOVERY_HELD                = "
        f"{len(held)}"
    )

    print()

    for direction in DIRECTIONS:

        direction_cases = [
            case
            for case in cases
            if case.direction == direction
        ]

        direction_failed = [
            case
            for case in direction_cases
            if case.recovery_outcome == FAILED
        ]

        direction_held = [
            case
            for case in direction_cases
            if case.recovery_outcome == HELD
        ]

        print(
            f"{direction}: "
            f"FAILED={len(direction_failed)} "
            f"HELD={len(direction_held)}"
        )


def print_exact_cases(
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "EXACT RECOVERY ATTEMPT CASES"
    )
    print("=" * 120)

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
                item.recovery_outcome,
                item.symbol,
                item.first_pf_minutes
                if item.first_pf_minutes is not None
                else 999,
            ),
        ):

            first_pf = (
                f"+{case.first_pf_minutes}m"
                if case.first_pf_minutes is not None
                else "NONE"
            )

            last_recovery = (
                f"+{case.last_recovering_minutes}m"
                if case.last_recovering_minutes is not None
                else "NONE"
            )

            first_deteriorating = (
                f"+{case.first_deteriorating_after_recovery_minutes}m"
                if (
                    case.first_deteriorating_after_recovery_minutes
                    is not None
                )
                else "NONE"
            )

            print()
            print(
                f"  {case.symbol:<6} "
                f"{case.recovery_outcome:<16} "
                f"OUTCOME={case.outcome:<15} "
                f"FIRST_PF={first_pf}"
            )

            print(
                f"    +30M STATE        = "
                f"{case.landmark_state}"
            )

            print(
                f"    LAST RECOVERY     = "
                f"{last_recovery}"
            )

            print(
                f"    DETERIORATION     = "
                f"{first_deteriorating}"
            )

            print(
                "    PATH              = "
                + " -> ".join(
                    f"+{minute}m:{state}"
                    for minute, state
                    in case.state_path_to_30m
                )
            )


def rate(
    cases: Sequence[RecoveryAttemptCase],
) -> Optional[float]:

    if not cases:
        return None

    pf_count = sum(
        case.outcome == LATER_PF
        for case in cases
    )

    return pf_count / len(cases)


def print_group(
    name: str,
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    later_pf = sum(
        case.outcome == LATER_PF
        for case in cases
    )

    no_pf = sum(
        case.outcome == NO_PF
        for case in cases
    )

    group_rate = rate(
        cases
    )

    print()
    print(
        f"GROUP = {name}"
    )

    print(
        f"  CASES             = "
        f"{len(cases)}"
    )

    print(
        f"  LATER PF BY +60M  = "
        f"{later_pf}"
    )

    print(
        f"  NO PF BY +60M     = "
        f"{no_pf}"
    )

    print(
        f"  LATER PF RATE     = "
        f"{'NA' if group_rate is None else f'{group_rate:.4f}'}"
    )


def print_pooled_comparison(
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "POOLED RECOVERY OUTCOME COMPARISON"
    )
    print("=" * 120)

    failed = [
        case
        for case in cases
        if case.recovery_outcome == FAILED
    ]

    held = [
        case
        for case in cases
        if case.recovery_outcome == HELD
    ]

    print_group(
        FAILED,
        failed,
    )

    print_group(
        HELD,
        held,
    )

    failed_rate = rate(
        failed
    )

    held_rate = rate(
        held
    )

    print()

    if (
        failed_rate is not None
        and held_rate is not None
    ):

        print(
            f"DESCRIPTIVE RATE DELTA "
            f"(FAILED - HELD) = "
            f"{failed_rate - held_rate:+.4f}"
        )

    else:

        print(
            "DESCRIPTIVE RATE DELTA = NA"
        )


def print_direction_comparison(
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "DIRECTION-CONTROLLED RECOVERY OUTCOME"
    )
    print("=" * 120)

    for direction in DIRECTIONS:

        direction_cases = [
            case
            for case in cases
            if case.direction == direction
        ]

        failed = [
            case
            for case in direction_cases
            if case.recovery_outcome == FAILED
        ]

        held = [
            case
            for case in direction_cases
            if case.recovery_outcome == HELD
        ]

        failed_rate = rate(
            failed
        )

        held_rate = rate(
            held
        )

        print()
        print(
            f"DIRECTION = {direction}"
        )

        print(
            f"  FAILED "
            f"N={len(failed)} "
            f"PF="
            f"{sum(case.outcome == LATER_PF for case in failed)} "
            f"RATE="
            f"{'NA' if failed_rate is None else f'{failed_rate:.4f}'}"
        )

        print(
            f"  HELD   "
            f"N={len(held)} "
            f"PF="
            f"{sum(case.outcome == LATER_PF for case in held)} "
            f"RATE="
            f"{'NA' if held_rate is None else f'{held_rate:.4f}'}"
        )

        if (
            failed_rate is not None
            and held_rate is not None
        ):

            print(
                f"  DELTA (FAILED - HELD) = "
                f"{failed_rate - held_rate:+.4f}"
            )

        else:

            print(
                "  DELTA (FAILED - HELD) = NA"
            )


def print_state_crosscheck(
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    print()
    print("=" * 120)
    print(
        "RECOVERY OUTCOME x +30M STATE"
    )
    print("=" * 120)

    states = sorted(
        set(
            case.landmark_state
            for case in cases
        )
    )

    for state in states:

        state_cases = [
            case
            for case in cases
            if case.landmark_state == state
        ]

        failed = [
            case
            for case in state_cases
            if case.recovery_outcome == FAILED
        ]

        held = [
            case
            for case in state_cases
            if case.recovery_outcome == HELD
        ]

        print()
        print(
            f"STATE = {state}"
        )

        print(
            f"  FAILED N={len(failed)} "
            f"PF={sum(case.outcome == LATER_PF for case in failed)}"
        )

        print(
            f"  HELD   N={len(held)} "
            f"PF={sum(case.outcome == LATER_PF for case in held)}"
        )

        if failed and held:

            failed_rate = rate(
                failed
            )

            held_rate = rate(
                held
            )

            print(
                f"  WITHIN-STATE DELTA = "
                f"{failed_rate - held_rate:+.4f}"
            )

        else:

            print(
                "  WITHIN-STATE DELTA = NA "
                "(one cohort absent)"
            )


def print_interpretation(
    cases: Sequence[RecoveryAttemptCase],
) -> None:

    failed = [
        case
        for case in cases
        if case.recovery_outcome == FAILED
    ]

    held = [
        case
        for case in cases
        if case.recovery_outcome == HELD
    ]

    failed_rate = rate(
        failed
    )

    held_rate = rate(
        held
    )

    print()
    print("=" * 120)
    print(
        "V13.17 RECOVERY ATTEMPT OUTCOME "
        "— INTERPRETATION"
    )
    print("=" * 120)

    print()

    print(
        "This audit compares only trajectories that actually "
        "attempted recovery before +30m."
    )

    print(
        f"RECOVERY_FAILED CASES = {len(failed)}"
    )

    print(
        f"RECOVERY_HELD CASES   = {len(held)}"
    )

    print()

    if (
        failed_rate is not None
        and held_rate is not None
    ):

        print(
            f"FAILED LATER-PF RATE = "
            f"{failed_rate:.4f}"
        )

        print(
            f"HELD LATER-PF RATE   = "
            f"{held_rate:.4f}"
        )

        print(
            f"DESCRIPTIVE DELTA    = "
            f"{failed_rate - held_rate:+.4f}"
        )

    else:

        print(
            "Primary rate comparison is unavailable."
        )

    print()

    print(
        "LONG and SHORT are kept separate because direction "
        "can otherwise confound the comparison."
    )

    print(
        "The +30m state is reported as a secondary crosscheck."
    )

    print()

    print(
        "A descriptive difference does not establish causality."
    )

    print(
        "The sample remains small."
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
        f"RECOVERY ATTEMPT CASES BUILT = "
        f"{len(cases)}"
    )

    print_population(
        cases
    )

    print_exact_cases(
        cases
    )

    print_pooled_comparison(
        cases
    )

    print_direction_comparison(
        cases
    )

    print_state_crosscheck(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 120)
    print(
        "V13.17 RECOVERY ATTEMPT OUTCOME AUDIT COMPLETE"
    )
    print("=" * 120)


if __name__ == "__main__":
    main()
