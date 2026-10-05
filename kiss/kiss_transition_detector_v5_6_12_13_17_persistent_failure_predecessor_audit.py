"""
AIMn / KISS V13.17 COMPANION RESEARCH
PERSISTENT FAILURE PREDECESSOR TRAJECTORY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
What trajectory immediately precedes FIRST PERSISTENT_FAILURE?

In particular:

    1. What was the state immediately before PF?
    2. Did the trajectory contain RECOVERING before PF?
    3. Did RECOVERING transition into DETERIORATING before PF?
    4. Did PF arise directly from DETERIORATING?
    5. Did PF arise after NEUTRAL?
    6. How do these patterns differ descriptively between:
           EARLY PF <= +30m
           LATE PF  >= +45m

IMPORTANT
---------
Only StatePoints BEFORE the first PF onset are used for predecessor
classification.

No future information is used.

CASE KEY
--------
(symbol, direction, opposite_time)

One first PF onset is used per unique trajectory case.

This is descriptive research only.
It does NOT create a trading rule.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_case_aware_validation as base
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
DETERIORATING = "DETERIORATING"
RECOVERING = "RECOVERING"
NEUTRAL = "NEUTRAL"

EARLY = "EARLY_PF"
LATE = "LATE_PF"
UNKNOWN = "UNKNOWN_TIMING"

LOOKBACK_MINUTES = 30


@dataclass
class PFPredecessorCase:
    case_key: Tuple[Any, Any, Any]

    symbol: str
    direction: str
    opposite_time: Any

    onset_minutes: int
    timing_group: str
    onset_return_pct: Optional[float]

    prior_state: Optional[str]
    prior_minutes: Optional[int]

    had_recovering_before_pf: bool
    had_neutral_before_pf: bool
    had_deteriorating_before_pf: bool

    recovery_attempt_failed: bool

    last_recovering_minutes: Optional[int]
    first_deteriorating_after_last_recovery_minutes: Optional[int]

    predecessor_pattern: str

    state_path_before_pf: Tuple[Tuple[int, str], ...]


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


def classify_timing(
    onset_minutes: int,
) -> str:
    if onset_minutes <= 30:
        return EARLY

    if onset_minutes >= 45:
        return LATE

    return UNKNOWN


def first_pf_index(
    points: Sequence[Any],
) -> Optional[int]:
    for index, point in enumerate(points):
        if point_state(point) == PERSISTENT:
            return index

    return None


def build_predecessor_case(
    path: Any,
) -> Optional[PFPredecessorCase]:

    points = sorted_points(
        path_points(path)
    )

    if not points:
        return None

    pf_index = first_pf_index(points)

    if pf_index is None:
        return None

    onset_point = points[pf_index]
    onset_minutes = point_minutes(onset_point)

    if onset_minutes is None:
        return None

    case_key = (
        path_symbol(path),
        path_direction(path),
        path_opposite_time(path),
    )

    previous_points = list(
        points[:pf_index]
    )

    prior_state = None
    prior_minutes = None

    if previous_points:
        prior_point = previous_points[-1]

        prior_state = point_state(
            prior_point
        )

        prior_minutes = point_minutes(
            prior_point
        )

    # Restrict the predecessor study to the
    # preceding LOOKBACK_MINUTES only.
    lookback_points = [
        point
        for point in previous_points
        if (
            point_minutes(point) is not None
            and onset_minutes - point_minutes(point)
            <= LOOKBACK_MINUTES
        )
    ]

    states = [
        point_state(point)
        for point in lookback_points
        if point_state(point) is not None
    ]

    had_recovering_before_pf = (
        RECOVERING in states
    )

    had_neutral_before_pf = (
        NEUTRAL in states
    )

    had_deteriorating_before_pf = (
        DETERIORATING in states
    )

    last_recovering_minutes = None

    for point in reversed(lookback_points):
        if point_state(point) == RECOVERING:
            last_recovering_minutes = (
                point_minutes(point)
            )
            break

    first_deteriorating_after_last_recovery_minutes = None

    if last_recovering_minutes is not None:

        for point in lookback_points:

            minute = point_minutes(point)

            if minute is None:
                continue

            if minute <= last_recovering_minutes:
                continue

            if point_state(point) == DETERIORATING:
                first_deteriorating_after_last_recovery_minutes = (
                    minute
                )
                break

    recovery_attempt_failed = (
        last_recovering_minutes is not None
        and first_deteriorating_after_last_recovery_minutes
        is not None
    )

    if prior_state == RECOVERING:
        predecessor_pattern = (
            "DIRECT_FROM_RECOVERING"
        )

    elif prior_state == NEUTRAL:
        predecessor_pattern = (
            "DIRECT_FROM_NEUTRAL"
        )

    elif prior_state == DETERIORATING:
        if recovery_attempt_failed:
            predecessor_pattern = (
                "RECOVERY_FAILED_THEN_DETERIORATING"
            )
        else:
            predecessor_pattern = (
                "DIRECT_FROM_DETERIORATING"
            )

    else:
        predecessor_pattern = (
            "OTHER_OR_UNKNOWN"
        )

    state_path_before_pf = tuple(
        (
            point_minutes(point),
            point_state(point),
        )
        for point in lookback_points
        if (
            point_minutes(point) is not None
            and point_state(point) is not None
        )
    )

    return PFPredecessorCase(
        case_key=case_key,
        symbol=path_symbol(path),
        direction=path_direction(path),
        opposite_time=path_opposite_time(path),
        onset_minutes=onset_minutes,
        timing_group=classify_timing(onset_minutes),
        onset_return_pct=point_return(onset_point),
        prior_state=prior_state,
        prior_minutes=prior_minutes,
        had_recovering_before_pf=had_recovering_before_pf,
        had_neutral_before_pf=had_neutral_before_pf,
        had_deteriorating_before_pf=had_deteriorating_before_pf,
        recovery_attempt_failed=recovery_attempt_failed,
        last_recovering_minutes=last_recovering_minutes,
        first_deteriorating_after_last_recovery_minutes=(
            first_deteriorating_after_last_recovery_minutes
        ),
        predecessor_pattern=predecessor_pattern,
        state_path_before_pf=state_path_before_pf,
    )


def build_cases() -> List[PFPredecessorCase]:

    paths = base.build_v1317_research_paths()

    unique_paths = dedup_case_paths(paths)

    cases = []

    for path in unique_paths:

        if path_symbol(path) not in SYMBOLS:
            continue

        case = build_predecessor_case(path)

        if case is None:
            continue

        cases.append(case)

    return cases


def print_header() -> None:
    print()
    print("=" * 110)
    print("V13.17 PERSISTENT FAILURE PREDECESSOR TRAJECTORY AUDIT")
    print("=" * 110)
    print()
    print(
        "Question: what trajectory immediately precedes FIRST "
        "PERSISTENT_FAILURE?"
    )
    print()
    print(
        f"Lookback window = {LOOKBACK_MINUTES} minutes"
    )
    print(
        "No future information is used."
    )
    print(
        "No production code changed."
    )


def print_case_detail(
    index: int,
    case: PFPredecessorCase,
) -> None:

    print()
    print("-" * 110)
    print(f"CASE {index}")
    print("-" * 110)

    print(
        f"  {case.symbol:<6} "
        f"{case.direction:<5} "
        f"PF_ONSET=+{case.onset_minutes}m "
        f"GROUP={case.timing_group}"
    )

    print(
        f"  ONSET RETURN       = "
        f"{case.onset_return_pct}"
    )

    print(
        f"  PRIOR STATE        = "
        f"{case.prior_state}"
        f" @+{case.prior_minutes}m"
        if case.prior_minutes is not None
        else
        "  PRIOR STATE        = NONE"
    )

    print(
        f"  HAD RECOVERING     = "
        f"{case.had_recovering_before_pf}"
    )

    print(
        f"  HAD NEUTRAL        = "
        f"{case.had_neutral_before_pf}"
    )

    print(
        f"  HAD DETERIORATING  = "
        f"{case.had_deteriorating_before_pf}"
    )

    print(
        f"  RECOVERY FAILED    = "
        f"{case.recovery_attempt_failed}"
    )

    if case.last_recovering_minutes is not None:
        print(
            f"  LAST RECOVERING    = "
            f"+{case.last_recovering_minutes}m"
        )
    else:
        print(
            "  LAST RECOVERING    = NONE"
        )

    if (
        case.first_deteriorating_after_last_recovery_minutes
        is not None
    ):
        print(
            f"  DETERIORATING AFTER RECOVERY = "
            f"+{case.first_deteriorating_after_last_recovery_minutes}m"
        )
    else:
        print(
            "  DETERIORATING AFTER RECOVERY = NONE"
        )

    print(
        f"  PREDECESSOR PATTERN = "
        f"{case.predecessor_pattern}"
    )

    if case.state_path_before_pf:
        formatted = " -> ".join(
            f"+{minute}m:{state}"
            for minute, state in case.state_path_before_pf
        )

        print(
            f"  PRE-PF PATH        = "
            f"{formatted}"
        )


def print_group_summary(
    cases: Sequence[PFPredecessorCase],
) -> None:

    print()
    print("=" * 110)
    print("EARLY VS LATE PF PREDECESSOR SUMMARY")
    print("=" * 110)

    for group in (
        EARLY,
        LATE,
        UNKNOWN,
    ):

        group_cases = [
            case
            for case in cases
            if case.timing_group == group
        ]

        if not group_cases:
            continue

        pattern_counts = Counter(
            case.predecessor_pattern
            for case in group_cases
        )

        recovering_count = sum(
            case.had_recovering_before_pf
            for case in group_cases
        )

        neutral_count = sum(
            case.had_neutral_before_pf
            for case in group_cases
        )

        deteriorating_count = sum(
            case.had_deteriorating_before_pf
            for case in group_cases
        )

        failed_recovery_count = sum(
            case.recovery_attempt_failed
            for case in group_cases
        )

        print()
        print(
            f"GROUP = {group}"
        )
        print(
            f"  CASES                    = "
            f"{len(group_cases)}"
        )
        print(
            f"  HAD RECOVERING           = "
            f"{recovering_count}"
        )
        print(
            f"  HAD NEUTRAL              = "
            f"{neutral_count}"
        )
        print(
            f"  HAD DETERIORATING        = "
            f"{deteriorating_count}"
        )
        print(
            f"  RECOVERY FAILED          = "
            f"{failed_recovery_count}"
        )

        print()
        print(
            "  PREDECESSOR PATTERNS:"
        )

        for pattern, count in sorted(
            pattern_counts.items()
        ):
            print(
                f"    {pattern:<42} = {count}"
            )


def print_exact_onsets(
    cases: Sequence[PFPredecessorCase],
) -> None:

    print()
    print("=" * 110)
    print("EXACT PF ONSET + PREDECESSOR PATTERN")
    print("=" * 110)

    ordered = sorted(
        cases,
        key=lambda case: (
            case.onset_minutes,
            case.symbol,
            case.direction,
        ),
    )

    for case in ordered:

        print(
            f"{case.symbol:<6} "
            f"{case.direction:<5} "
            f"PF_ONSET=+{case.onset_minutes}m "
            f"GROUP={case.timing_group:<10} "
            f"PRIOR={str(case.prior_state):<18} "
            f"RECOVERY_FAILED={case.recovery_attempt_failed!s:<5} "
            f"PATTERN={case.predecessor_pattern}"
        )


def print_symbol_summary(
    cases: Sequence[PFPredecessorCase],
) -> None:

    print()
    print("=" * 110)
    print("PF PREDECESSOR SUMMARY BY SYMBOL")
    print("=" * 110)

    symbols = sorted(
        set(case.symbol for case in cases)
    )

    for symbol in symbols:

        symbol_cases = [
            case
            for case in cases
            if case.symbol == symbol
        ]

        failed = sum(
            case.recovery_attempt_failed
            for case in symbol_cases
        )

        recovering = sum(
            case.had_recovering_before_pf
            for case in symbol_cases
        )

        print(
            f"{symbol:<6} "
            f"CASES={len(symbol_cases)} "
            f"HAD_RECOVERING={recovering} "
            f"RECOVERY_FAILED={failed}"
        )


def print_direction_summary(
    cases: Sequence[PFPredecessorCase],
) -> None:

    print()
    print("=" * 110)
    print("PF PREDECESSOR SUMMARY BY DIRECTION")
    print("=" * 110)

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

        failed = sum(
            case.recovery_attempt_failed
            for case in direction_cases
        )

        recovering = sum(
            case.had_recovering_before_pf
            for case in direction_cases
        )

        print(
            f"{direction:<6} "
            f"CASES={len(direction_cases)} "
            f"HAD_RECOVERING={recovering} "
            f"RECOVERY_FAILED={failed}"
        )


def print_interpretation(
    cases: Sequence[PFPredecessorCase],
) -> None:

    print()
    print("=" * 110)
    print("V13.17 PF PREDECESSOR TRAJECTORY — INTERPRETATION")
    print("=" * 110)

    early = [
        case
        for case in cases
        if case.timing_group == EARLY
    ]

    late = [
        case
        for case in cases
        if case.timing_group == LATE
    ]

    early_failed = sum(
        case.recovery_attempt_failed
        for case in early
    )

    late_failed = sum(
        case.recovery_attempt_failed
        for case in late
    )

    early_recovering = sum(
        case.had_recovering_before_pf
        for case in early
    )

    late_recovering = sum(
        case.had_recovering_before_pf
        for case in late
    )

    print()
    print(
        "EARLY PF:"
    )
    print(
        f"  cases = {len(early)}"
    )
    print(
        f"  had prior RECOVERING = "
        f"{early_recovering}"
    )
    print(
        f"  recovery attempt failed before PF = "
        f"{early_failed}"
    )

    print()
    print(
        "LATE PF:"
    )
    print(
        f"  cases = {len(late)}"
    )
    print(
        f"  had prior RECOVERING = "
        f"{late_recovering}"
    )
    print(
        f"  recovery attempt failed before PF = "
        f"{late_failed}"
    )

    print()
    print(
        "These counts are descriptive only."
    )
    print(
        "They do not establish that one predecessor pattern "
        "causes PF."
    )
    print(
        "They do not create an entry, hold, warning, rescue, "
        "or exit rule."
    )
    print(
        "No production code changed."
    )


def main() -> None:

    print_header()

    paths = base.build_v1317_research_paths()

    print()
    print(
        f"RAW PATH OBJECTS = {len(paths)}"
    )

    unique_paths = dedup_case_paths(paths)

    print(
        f"UNIQUE TRAJECTORY CASES = "
        f"{len(unique_paths)}"
    )

    cases = build_cases()

    print(
        f"FIRST PF ONSET CASES = "
        f"{len(cases)}"
    )

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print_case_detail(
            index,
            case,
        )

    print_group_summary(
        cases
    )

    print_exact_onsets(
        cases
    )

    print_symbol_summary(
        cases
    )

    print_direction_summary(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 110)
    print(
        "V13.17 PERSISTENT FAILURE PREDECESSOR "
        "TRAJECTORY AUDIT COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()
