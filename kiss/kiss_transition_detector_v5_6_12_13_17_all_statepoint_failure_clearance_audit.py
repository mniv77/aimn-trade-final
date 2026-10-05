"""
AIMn / KISS V13.17 COMPANION RESEARCH
ALL-STATEPOINT PERSISTENT FAILURE CLEARANCE AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
When PERSISTENT_FAILURE first clears, what happens at the very next
observed state point?

This audit removes the checkpoint-selection limitation of the previous
clearance audit.

PREVIOUS AUDIT
--------------
Only +15m / +30m / +45m / +60m were searched for the first residual
Persistent-Failure observation.

THIS AUDIT
----------
Uses every StatePoint already produced by the V13.17 path builder.

CASE KEY
--------
(symbol, direction, opposite_time)

PRIMARY CLASSIFICATIONS
-----------------------
RECOVERY_PATH
    PERSISTENT_FAILURE history
    -> current state is no longer PERSISTENT_FAILURE
    -> next observed state is RECOVERING

CONTINUED_FAILURE_PATH
    PERSISTENT_FAILURE history
    -> current state is no longer PERSISTENT_FAILURE
    -> next observed state is DETERIORATING or PERSISTENT_FAILURE

NEUTRAL_OR_OTHER_PATH
    Anything else.

METHODOLOGY
-----------
1. Use the existing V13.17 path builder.
2. Deduplicate cases by (symbol, direction, opposite_time).
3. Inspect every existing StatePoint.
4. Find the FIRST StatePoint where:
       prior history contains PERSISTENT_FAILURE
       AND current state != PERSISTENT_FAILURE
5. Look only at the next observed StatePoint to classify the path.
6. Future returns are measured from the clearance StatePoint.
7. No future information is used to define the current state.
8. Checkpoint observations are not treated as independent cases.
9. No production logic changes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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


def attr(obj: Any, *names: str, default: Any = None) -> Any:
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
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(result):
        return None

    return result


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


def dedup_case_paths(paths: Iterable[Any]) -> List[Any]:
    """
    One path per:
        (symbol, direction, opposite_time)
    """
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


def sorted_points(points: Sequence[Any]) -> List[Any]:
    valid = [
        p
        for p in points
        if point_minutes(p) is not None
    ]

    return sorted(
        valid,
        key=lambda p: point_minutes(p),
    )


def future_return_from_checkpoint(
    direction: str,
    current_return_pct: Optional[float],
    future_return_pct: Optional[float],
) -> Optional[float]:
    """
    Convert an entry-relative return into a checkpoint-relative return.

    LONG:
        current price factor = 1 + current_return
        future price factor  = 1 + future_return

    SHORT:
        current price factor = 1 - current_return
        future price factor  = 1 - future_return
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
            (future_factor / current_factor) - 1.0
        ) * 100.0

    if direction == "SHORT":
        current_factor = 1.0 - current
        future_factor = 1.0 - future

        if current_factor == 0:
            return None

        return (
            1.0 -
            (future_factor / current_factor)
        ) * 100.0

    return None


def classify_next_state(
    next_state: Optional[str],
) -> str:
    if next_state == RECOVERING:
        return "RECOVERY_PATH"

    if next_state in (
        DETERIORATING,
        PERSISTENT,
    ):
        return "CONTINUED_FAILURE_PATH"

    return "NEUTRAL_OR_OTHER_PATH"


def first_all_statepoint_clearance(
    path: Any,
) -> Optional[Dict[str, Any]]:
    """
    Find the FIRST existing StatePoint where:

        prior state history contains PERSISTENT_FAILURE
        AND current state != PERSISTENT_FAILURE

    No artificial checkpoints are created.
    """

    points = sorted_points(
        path_points(path)
    )

    if not points:
        return None

    prior_states: List[str] = []

    for index, point in enumerate(points):
        state = point_state(point)
        minute = point_minutes(point)

        if state is None or minute is None:
            continue

        # We need Persistent Failure to have occurred BEFORE
        # the current StatePoint.
        had_prior_persistent = (
            PERSISTENT in prior_states
        )

        if (
            had_prior_persistent
            and state != PERSISTENT
        ):
            next_point = None

            for candidate in points[index + 1:]:
                if (
                    point_minutes(candidate)
                    is not None
                    and point_state(candidate)
                    is not None
                ):
                    next_point = candidate
                    break

            next_state = (
                point_state(next_point)
                if next_point is not None
                else None
            )

            return {
                "symbol": path_symbol(path),
                "direction": path_direction(path),
                "opposite_time": path_opposite_time(path),
                "clearance_minutes": minute,
                "current_state": state,
                "current_return_pct": point_return(point),
                "next_minutes": (
                    point_minutes(next_point)
                    if next_point is not None
                    else None
                ),
                "next_state": next_state,
                "path_class": classify_next_state(
                    next_state
                ),
                "points": points,
            }

        prior_states.append(state)

    return None


def build_clearance_observations(
    paths: Sequence[Any],
) -> List[Dict[str, Any]]:
    observations = []

    for path in dedup_case_paths(paths):
        observation = first_all_statepoint_clearance(path)

        if observation is not None:
            observations.append(observation)

    return observations


def find_exact_future_point(
    points: Sequence[Any],
    target_minutes: int,
) -> Optional[Any]:

    for point in points:
        if point_minutes(point) == target_minutes:
            return point

    return None


def future_return(
    observation: Dict[str, Any],
    horizon_minutes: int,
) -> Optional[float]:

    current_minutes = observation[
        "clearance_minutes"
    ]

    target = current_minutes + horizon_minutes

    future_point = find_exact_future_point(
        observation["points"],
        target,
    )

    if future_point is None:
        return None

    return future_return_from_checkpoint(
        direction=observation["direction"],
        current_return_pct=observation[
            "current_return_pct"
        ],
        future_return_pct=point_return(
            future_point
        ),
    )


def print_header(title: str) -> None:
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)


def print_cases(
    observations: Sequence[Dict[str, Any]]
) -> None:

    print_header(
        "ALL-STATEPOINT FIRST PERSISTENT-FAILURE CLEARANCE"
    )

    if not observations:
        print("NONE")
        return

    ordered = sorted(
        observations,
        key=lambda x: (
            x["symbol"],
            x["direction"],
            x["clearance_minutes"],
        ),
    )

    for number, obs in enumerate(
        ordered,
        start=1,
    ):
        print()
        print(f"CASE {number}")
        print(
            f"  SYMBOL            = {obs['symbol']}"
        )
        print(
            f"  DIRECTION         = {obs['direction']}"
        )
        print(
            f"  OPPOSITE_TIME     = {obs['opposite_time']}"
        )
        print(
            f"  CLEARANCE STATE   = "
            f"+{obs['clearance_minutes']}m"
        )
        print(
            f"  CURRENT STATE     = "
            f"{obs['current_state']}"
        )
        print(
            f"  CURRENT RETURN    = "
            f"{obs['current_return_pct']}"
        )
        print(
            f"  NEXT STATEPOINT   = "
            f"+{obs['next_minutes']}m"
        )
        print(
            f"  NEXT STATE        = "
            f"{obs['next_state']}"
        )
        print(
            f"  PATH CLASS        = "
            f"{obs['path_class']}"
        )

        for horizon in (
            5,
            10,
            15,
            20,
            30,
        ):
            value = future_return(
                obs,
                horizon,
            )

            if value is None:
                print(
                    f"  FUTURE +{horizon:<2}m     = NA"
                )
            else:
                print(
                    f"  FUTURE +{horizon:<2}m     = "
                    f"{value:+.3f}%"
                )


def print_path_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:

    print_header(
        "POST-FAILURE PATH SUMMARY"
    )

    counts = Counter(
        obs["path_class"]
        for obs in observations
    )

    print(
        "RECOVERY_PATH            = "
        f"{counts.get('RECOVERY_PATH', 0)}"
    )

    print(
        "CONTINUED_FAILURE_PATH  = "
        f"{counts.get('CONTINUED_FAILURE_PATH', 0)}"
    )

    print(
        "NEUTRAL_OR_OTHER_PATH   = "
        f"{counts.get('NEUTRAL_OR_OTHER_PATH', 0)}"
    )


def print_state_transition_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:

    print_header(
        "IMMEDIATE POST-FAILURE STATE TRANSITIONS"
    )

    counts = Counter(
        (
            obs["current_state"],
            obs["next_state"],
        )
        for obs in observations
    )

    if not counts:
        print("NONE")
        return

    for (
        current_state,
        next_state,
    ), count in sorted(counts.items()):

        print(
            f"{current_state:22s} -> "
            f"{str(next_state):22s} "
            f"N={count}"
        )


def print_symbol_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:

    print_header(
        "ALL-STATEPOINT CLEARANCE CASES BY SYMBOL"
    )

    counts = Counter(
        obs["symbol"]
        for obs in observations
    )

    for symbol in SYMBOLS:
        print(
            f"{symbol:6s} "
            f"CASES={counts.get(symbol, 0)}"
        )


def print_timing_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:

    print_header(
        "CLEARANCE TIMING SUMMARY"
    )

    counts = Counter(
        obs["clearance_minutes"]
        for obs in observations
    )

    if not counts:
        print("NONE")
        return

    for minute, count in sorted(
        counts.items()
    ):
        print(
            f"+{minute}m "
            f"CASES={count}"
        )


def print_full_paths(
    observations: Sequence[Dict[str, Any]]
) -> None:

    print_header(
        "FULL OBSERVED STATE PATHS"
    )

    for obs in sorted(
        observations,
        key=lambda x: (
            x["symbol"],
            x["direction"],
            x["clearance_minutes"],
        ),
    ):

        compact = []

        for point in obs["points"]:

            minute = point_minutes(point)
            state = point_state(point)

            if minute is None or state is None:
                continue

            compact.append(
                f"+{minute}m:{state}"
            )

        print()
        print(
            f"{obs['symbol']:6s} "
            f"{obs['direction']:5s} "
            f"CLEARANCE=+"
            f"{obs['clearance_minutes']}m "
            f"PATH={obs['path_class']}"
        )

        print(
            "  "
            + " -> ".join(compact)
        )


def compare_paths(
    observations: Sequence[Dict[str, Any]]
) -> None:
    """
    Descriptive comparison only.

    Recovery-path versus continued-failure-path.

    There is deliberately NO state+direction statistical claim
    when one side of a comparison is missing.
    """

    print_header(
        "RECOVERY VS CONTINUED-FAILURE DESCRIPTIVE COMPARISON"
    )

    groups: Dict[
        Tuple[str, str, int],
        List[Dict[str, Any]],
    ] = defaultdict(list)

    for obs in observations:

        key = (
            obs["direction"],
            obs["current_state"],
            obs["clearance_minutes"],
        )

        groups[key].append(obs)

    if not groups:
        print("NONE")
        return

    for key, group in sorted(groups.items()):

        direction, current_state, minute = key

        print()
        print(
            f"CONTROL GROUP: "
            f"DIRECTION={direction} "
            f"STATE={current_state} "
            f"CLEARANCE=+{minute}m "
            f"CASES={len(group)}"
        )

        recovery = [
            obs
            for obs in group
            if obs["path_class"]
            == "RECOVERY_PATH"
        ]

        continued = [
            obs
            for obs in group
            if obs["path_class"]
            == "CONTINUED_FAILURE_PATH"
        ]

        print(
            f"  RECOVERY_PATH N={len(recovery)}"
        )

        print(
            f"  CONTINUED_FAILURE_PATH "
            f"N={len(continued)}"
        )

        for horizon in (
            5,
            10,
            15,
            20,
            30,
        ):

            recovery_values = [
                value
                for obs in recovery
                for value in [
                    future_return(
                        obs,
                        horizon,
                    )
                ]
                if value is not None
            ]

            continued_values = [
                value
                for obs in continued
                for value in [
                    future_return(
                        obs,
                        horizon,
                    )
                ]
                if value is not None
            ]

            print()

            if not recovery_values:
                recovery_display = "NA"
            else:
                recovery_display = (
                    f"{sum(recovery_values) / len(recovery_values):+.3f}%"
                )

            if not continued_values:
                continued_display = "NA"
            else:
                continued_display = (
                    f"{sum(continued_values) / len(continued_values):+.3f}%"
                )

            if (
                recovery_values
                and continued_values
            ):

                recovery_avg = (
                    sum(recovery_values)
                    / len(recovery_values)
                )

                continued_avg = (
                    sum(continued_values)
                    / len(continued_values)
                )

                delta = (
                    recovery_avg
                    - continued_avg
                )

                print(
                    f"  +{horizon}m "
                    f"RECOVERY_AVG={recovery_display} "
                    f"CONTINUED_AVG={continued_display} "
                    f"DELTA={delta:+.3f}%"
                )

            else:
                print(
                    f"  +{horizon}m "
                    f"RECOVERY_AVG={recovery_display} "
                    f"CONTINUED_AVG={continued_display} "
                    f"NO TWO-SIDED COMPARISON"
                )


def main() -> None:

    print_header(
        "V13.17 ALL-STATEPOINT PERSISTENT FAILURE CLEARANCE AUDIT"
    )

    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")

    print()
    print(
        "===== BUILD V13.17 RESEARCH PATHS ====="
    )

    all_paths = (
        base.build_v1317_research_paths()
    )

    print(
        f"RAW PATH OBJECTS = "
        f"{len(all_paths)}"
    )

    unique_paths = dedup_case_paths(
        all_paths
    )

    print(
        f"UNIQUE TRAJECTORY CASES = "
        f"{len(unique_paths)}"
    )

    observations = (
        build_clearance_observations(
            unique_paths
        )
    )

    print(
        f"ALL-STATEPOINT CLEARANCE "
        f"OBSERVATIONS = {len(observations)}"
    )

    print_cases(observations)
    print_path_summary(observations)
    print_state_transition_summary(observations)
    print_symbol_summary(observations)
    print_timing_summary(observations)
    print_full_paths(observations)
    compare_paths(observations)

    print()
    print("=" * 110)
    print(
        "V13.17 ALL-STATEPOINT CLEARANCE — "
        "INTERPRETATION"
    )
    print("=" * 110)

    print(
        "This audit uses every existing StatePoint "
        "already produced by V13.17."
    )

    print(
        "It does not create new indicators or "
        "production rules."
    )

    print(
        "A single observation, symbol, or horizon "
        "does NOT validate a trading rule."
    )

    print(
        "No result becomes an entry, hold, warning, "
        "rescue, or exit rule."
    )

    print(
        "NO PRODUCTION CODE CHANGED."
    )

    print()
    print(
        "V13.17 ALL-STATEPOINT FAILURE CLEARANCE "
        "AUDIT COMPLETE"
    )


if __name__ == "__main__":
    main()
