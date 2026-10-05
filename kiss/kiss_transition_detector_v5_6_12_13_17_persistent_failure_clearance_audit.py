"""
AIMn / KISS V13.17 COMPANION RESEARCH
PERSISTENT FAILURE CLEARANCE / RECOVERY PATH AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
After a trajectory reaches PERSISTENT_FAILURE, does the path that follows
the failure state contain information?

PRIMARY PATHS
-------------
A) PERSISTENT_FAILURE -> DETERIORATING -> RECOVERING

B) PERSISTENT_FAILURE -> DETERIORATING ->
   DETERIORATING / PERSISTENT_FAILURE

This is NOT a trading-rule test.

The audit asks whether post-failure trajectory direction is associated with
different subsequent returns after controlling for:

    direction + current state + checkpoint

CASE KEY
--------
(symbol, direction, opposite_time)

METHODOLOGY
-----------
1. Use the existing V13.17 research path builder.
2. Deduplicate to one observation set per unique trajectory case.
3. Find the FIRST checkpoint where:
       prior history contains PERSISTENT_FAILURE
       AND current state is no longer PERSISTENT_FAILURE
4. This is the "failure clearance" checkpoint.
5. Inspect the next observed state.
6. Classify the post-failure path:
       RECOVERY_PATH
       CONTINUED_FAILURE_PATH
       OTHER_PATH
7. Measure future return FROM THE CLEARANCE CHECKPOINT.
8. Never use information after that checkpoint to define the checkpoint itself.
9. No checkpoint is treated as an independent case.
10. Research only. No production logic is changed.

IMPORTANT
---------
A result with one case is descriptive only.
A result with one symbol is descriptive only.
A result with one horizon is descriptive only.
No path becomes an entry, hold, warning, rescue, or exit rule.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
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

CHECKPOINTS = (15, 30, 45, 60)
FUTURE_HORIZONS = (15, 30, 45)

PERSISTENT = "PERSISTENT_FAILURE"
DETERIORATING = "DETERIORATING"
RECOVERING = "RECOVERING"
NEUTRAL = "NEUTRAL"

RECOVERY_PATH = "RECOVERY_PATH"
CONTINUED_FAILURE_PATH = "CONTINUED_FAILURE_PATH"
OTHER_PATH = "OTHER_PATH"


def attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first available attribute from a list of candidate names."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def point_minutes(point: Any) -> Optional[int]:
    value = attr(point, "minutes", "minute", "offset_minutes", default=None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def point_state(point: Any) -> Optional[str]:
    value = attr(point, "state", "current_state", default=None)
    if value is None:
        return None
    return str(value)


def point_return(point: Any) -> Optional[float]:
    value = attr(point, "return_pct", "signed_return_pct", default=None)
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def path_symbol(path: Any) -> str:
    value = attr(path, "symbol", default="")
    return str(value)


def path_direction(path: Any) -> str:
    value = attr(path, "direction", default="")
    return str(value).upper()


def path_opposite_time(path: Any) -> Any:
    return attr(path, "opposite_time", "transition_time", default=None)


def path_points(path: Any) -> List[Any]:
    points = attr(path, "points", "state_points", default=None)
    if points is None:
        return []
    return list(points)


def dedup_case_paths(paths: Iterable[Any]) -> List[Any]:
    """
    Keep exactly one path per:
        (symbol, direction, opposite_time)

    Later duplicate aliases are ignored.
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


def sort_points(points: Sequence[Any]) -> List[Any]:
    valid = [p for p in points if point_minutes(p) is not None]
    return sorted(valid, key=lambda p: point_minutes(p))


def state_history_before(points: Sequence[Any], checkpoint_minutes: int) -> List[str]:
    return [
        s
        for p in points
        if (m := point_minutes(p)) is not None
        and m < checkpoint_minutes
        and (s := point_state(p)) is not None
    ]


def find_checkpoint_point(
    points: Sequence[Any],
    checkpoint_minutes: int,
) -> Optional[Any]:
    for p in points:
        if point_minutes(p) == checkpoint_minutes:
            return p
    return None


def find_next_checkpoint_point(
    points: Sequence[Any],
    checkpoint_minutes: int,
) -> Optional[Any]:
    for p in points:
        m = point_minutes(p)
        if m is not None and m > checkpoint_minutes:
            return p
    return None


def has_prior_persistent_failure(
    points: Sequence[Any],
    checkpoint_minutes: int,
) -> bool:
    return PERSISTENT in state_history_before(points, checkpoint_minutes)


def future_return_from_checkpoint(
    direction: str,
    current_return_pct: Optional[float],
    future_return_pct: Optional[float],
) -> Optional[float]:
    """
    Reconstruct future return from the CURRENT CHECKPOINT.

    StatePoint.return_pct is measured from the original entry/opposite
    transition. We convert that into a relative price factor first.

    LONG:
        price factor = 1 + return_pct/100
        checkpoint -> future return =
            future_factor/current_factor - 1

    SHORT:
        underlying price factor = 1 - return_pct/100
        checkpoint -> future short return =
            1 - future_price_factor/current_price_factor
    """
    if current_return_pct is None or future_return_pct is None:
        return None

    current = current_return_pct / 100.0
    future = future_return_pct / 100.0

    direction = direction.upper()

    if direction == "LONG":
        current_factor = 1.0 + current
        future_factor = 1.0 + future

        if current_factor == 0:
            return None

        return (future_factor / current_factor - 1.0) * 100.0

    if direction == "SHORT":
        current_price_factor = 1.0 - current
        future_price_factor = 1.0 - future

        if current_price_factor == 0:
            return None

        return (1.0 - future_price_factor / current_price_factor) * 100.0

    return None


def classify_next_path(current_state: str, next_state: Optional[str]) -> str:
    """
    The audit focuses on trajectories that have left Persistent Failure.

    RECOVERY_PATH:
        current state is DETERIORATING
        and next state is RECOVERING

    CONTINUED_FAILURE_PATH:
        current state is DETERIORATING
        and next state is DETERIORATING or PERSISTENT_FAILURE

    OTHER_PATH:
        anything else.
    """
    if current_state == DETERIORATING:
        if next_state == RECOVERING:
            return RECOVERY_PATH

        if next_state in (DETERIORATING, PERSISTENT):
            return CONTINUED_FAILURE_PATH

    return OTHER_PATH


def build_clearance_observations(paths: Sequence[Any]) -> List[Dict[str, Any]]:
    """
    Find exactly one FIRST clearance checkpoint per unique trajectory case.
    """
    observations: List[Dict[str, Any]] = []

    for path in dedup_case_paths(paths):
        symbol = path_symbol(path)
        direction = path_direction(path)
        opposite_time = path_opposite_time(path)

        points = sort_points(path_points(path))
        if not points:
            continue

        for checkpoint in CHECKPOINTS:
            current_point = find_checkpoint_point(points, checkpoint)
            if current_point is None:
                continue

            current_state = point_state(current_point)
            if current_state is None:
                continue

            if current_state == PERSISTENT:
                continue

            if not has_prior_persistent_failure(points, checkpoint):
                continue

            next_point = find_next_checkpoint_point(points, checkpoint)
            next_state = point_state(next_point) if next_point is not None else None
            next_minutes = (
                point_minutes(next_point) if next_point is not None else None
            )

            current_return = point_return(current_point)

            path_class = classify_next_path(
                current_state=current_state,
                next_state=next_state,
            )

            observations.append(
                {
                    "case_key": (symbol, direction, opposite_time),
                    "symbol": symbol,
                    "direction": direction,
                    "opposite_time": opposite_time,
                    "clearance_checkpoint": checkpoint,
                    "current_state": current_state,
                    "current_return_pct": current_return,
                    "next_checkpoint": next_minutes,
                    "next_state": next_state,
                    "path_class": path_class,
                    "state_history": state_history_before(
                        points,
                        checkpoint,
                    ),
                    "points": points,
                }
            )

            # FIRST clearance checkpoint only.
            break

    return observations


def outcome_at_horizon(
    observation: Dict[str, Any],
    horizon: int,
) -> Optional[float]:
    checkpoint = observation["clearance_checkpoint"]
    current_return = observation["current_return_pct"]
    direction = observation["direction"]
    points = observation["points"]

    target = checkpoint + horizon

    for point in points:
        if point_minutes(point) == target:
            future_return = point_return(point)
            return future_return_from_checkpoint(
                direction=direction,
                current_return_pct=current_return,
                future_return_pct=future_return,
            )

    return None


def print_clearance_cases(observations: Sequence[Dict[str, Any]]) -> None:
    print()
    print("=" * 110)
    print("FIRST PERSISTENT-FAILURE CLEARANCE OBSERVATIONS")
    print("=" * 110)

    if not observations:
        print("NONE")
        return

    for index, obs in enumerate(
        sorted(
            observations,
            key=lambda x: (
                x["symbol"],
                x["direction"],
                x["clearance_checkpoint"],
                str(x["opposite_time"]),
            ),
        ),
        start=1,
    ):
        print()
        print(f"CASE {index}")
        print(f"  SYMBOL              = {obs['symbol']}")
        print(f"  DIRECTION           = {obs['direction']}")
        print(f"  OPPOSITE_TIME       = {obs['opposite_time']}")
        print(f"  CLEARANCE CP        = +{obs['clearance_checkpoint']}m")
        print(f"  CURRENT STATE       = {obs['current_state']}")
        print(f"  CURRENT RETURN      = {obs['current_return_pct']}")
        print(f"  NEXT CP             = {obs['next_checkpoint']}")
        print(f"  NEXT STATE          = {obs['next_state']}")
        print(f"  POST-FAILURE PATH   = {obs['path_class']}")
        print(
            "  PRIOR STATES        = "
            + " -> ".join(obs["state_history"])
        )

        for horizon in FUTURE_HORIZONS:
            value = outcome_at_horizon(obs, horizon)
            if value is None:
                display = "NA"
            else:
                display = f"{value:+.3f}%"

            print(
                f"  FUTURE +{horizon}m     = {display}"
            )


def print_path_class_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:
    print()
    print("=" * 110)
    print("POST-FAILURE PATH SUMMARY")
    print("=" * 110)

    counts = Counter(obs["path_class"] for obs in observations)

    print(
        f"RECOVERY_PATH            = {counts.get(RECOVERY_PATH, 0)}"
    )
    print(
        f"CONTINUED_FAILURE_PATH  = "
        f"{counts.get(CONTINUED_FAILURE_PATH, 0)}"
    )
    print(
        f"OTHER_PATH              = {counts.get(OTHER_PATH, 0)}"
    )


def print_state_transition_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:
    print()
    print("=" * 110)
    print("POST-FAILURE NEXT-STATE SUMMARY")
    print("=" * 110)

    counts = Counter(
        (
            obs["current_state"],
            obs["next_state"],
        )
        for obs in observations
    )

    for (current_state, next_state), count in sorted(
        counts.items(),
        key=lambda item: (
            str(item[0][0]),
            str(item[0][1]),
        ),
    ):
        print(
            f"{current_state:22s} -> "
            f"{str(next_state):22s} N={count}"
        )


def average(values: Sequence[float]) -> Optional[float]:
    clean = [
        value
        for value in values
        if value is not None and isfinite(value)
    ]

    if not clean:
        return None

    return sum(clean) / len(clean)


def matched_control_analysis(
    observations: Sequence[Dict[str, Any]],
) -> None:
    """
    Compare:

        RECOVERY_PATH
    vs
        all cases with the same direction + current state + checkpoint

    using future return measured FROM THE CLEARANCE CHECKPOINT.

    This is deliberately descriptive and very conservative.
    """
    print()
    print("=" * 110)
    print("MATCHED POST-FAILURE PATH CONTROL")
    print("=" * 110)
    print(
        "MATCH KEY = DIRECTION + CURRENT STATE + CLEARANCE CHECKPOINT"
    )

    candidates = [
        obs
        for obs in observations
        if obs["current_state"] == DETERIORATING
    ]

    if not candidates:
        print("NO DETERIORATING CLEARANCE OBSERVATIONS")
        return

    groups: Dict[
        Tuple[str, str, int],
        List[Dict[str, Any]]
    ] = defaultdict(list)

    for obs in candidates:
        key = (
            obs["direction"],
            obs["current_state"],
            obs["clearance_checkpoint"],
        )
        groups[key].append(obs)

    for key, group in sorted(groups.items()):
        direction, current_state, checkpoint = key

        print()
        print(
            f"CONTROL: DIRECTION={direction} "
            f"CURRENT_STATE={current_state} "
            f"CLEARANCE_CP=+{checkpoint}m "
            f"CASES={len(group)}"
        )

        for path_class in (
            RECOVERY_PATH,
            CONTINUED_FAILURE_PATH,
        ):
            class_group = [
                obs
                for obs in group
                if obs["path_class"] == path_class
            ]

            if not class_group:
                continue

            print(
                f"  PATH={path_class} "
                f"N={len(class_group)}"
            )

            for horizon in FUTURE_HORIZONS:
                values = [
                    outcome_at_horizon(obs, horizon)
                    for obs in class_group
                ]

                values = [
                    value
                    for value in values
                    if value is not None
                ]

                if not values:
                    print(
                        f"    +{horizon}m N=0"
                    )
                    continue

                avg_value = average(values)

                print(
                    f"    +{horizon}m "
                    f"N={len(values)} "
                    f"AVG={avg_value:+.3f}%"
                )

        recovery_values_by_horizon: Dict[int, List[float]] = defaultdict(list)
        continued_values_by_horizon: Dict[int, List[float]] = defaultdict(list)

        for obs in group:
            path_class = obs["path_class"]

            for horizon in FUTURE_HORIZONS:
                value = outcome_at_horizon(obs, horizon)
                if value is None:
                    continue

                if path_class == RECOVERY_PATH:
                    recovery_values_by_horizon[horizon].append(value)

                elif path_class == CONTINUED_FAILURE_PATH:
                    continued_values_by_horizon[horizon].append(value)

        print("  PATH DIFFERENCE: RECOVERY_PATH - CONTINUED_FAILURE_PATH")

        for horizon in FUTURE_HORIZONS:
            r = average(recovery_values_by_horizon[horizon])
            c = average(continued_values_by_horizon[horizon])

            if r is None or c is None:
                print(
                    f"    +{horizon}m NO TWO-SIDED COMPARISON"
                )
                continue

            print(
                f"    +{horizon}m "
                f"RECOVERY_AVG={r:+.3f}% "
                f"CONTINUED_AVG={c:+.3f}% "
                f"DELTA={r - c:+.3f}%"
            )


def print_symbol_summary(
    observations: Sequence[Dict[str, Any]]
) -> None:
    print()
    print("=" * 110)
    print("RESIDUAL CLEARANCE CASES BY SYMBOL")
    print("=" * 110)

    counts = Counter(obs["symbol"] for obs in observations)

    for symbol in SYMBOLS:
        print(
            f"{symbol:6s} "
            f"CASES={counts.get(symbol, 0)}"
        )


def print_case_paths(
    observations: Sequence[Dict[str, Any]]
) -> None:
    print()
    print("=" * 110)
    print("FULL POST-FAILURE CHECKPOINT PATHS")
    print("=" * 110)

    for obs in sorted(
        observations,
        key=lambda x: (
            x["symbol"],
            x["direction"],
            x["clearance_checkpoint"],
        ),
    ):
        compact = []

        for point in obs["points"]:
            minutes = point_minutes(point)
            state = point_state(point)

            if minutes is None or state is None:
                continue

            compact.append(
                f"+{minutes}m:{state}"
            )

        print()
        print(
            f"{obs['symbol']:6s} "
            f"{obs['direction']:5s} "
            f"CP=+{obs['clearance_checkpoint']}m "
            f"PATH={obs['path_class']}"
        )
        print("  " + " -> ".join(compact))


def main() -> None:
    print("=" * 110)
    print("V13.17 PERSISTENT FAILURE CLEARANCE / RECOVERY PATH AUDIT")
    print("=" * 110)
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print()

    print("===== BUILD V13.17 RESEARCH PATHS =====")

    try:
        all_paths = base.build_v1317_research_paths()
    except Exception as exc:
        print(f"ERROR BUILDING V13.17 PATHS: {exc}")
        raise

    print(
        f"RAW PATH OBJECTS = {len(all_paths)}"
    )

    unique_paths = dedup_case_paths(all_paths)

    print(
        f"UNIQUE TRAJECTORY CASES = {len(unique_paths)}"
    )

    symbol_counts = Counter(
        path_symbol(path)
        for path in unique_paths
    )

    for symbol in SYMBOLS:
        print(
            f"{symbol:6s} CASES={symbol_counts.get(symbol, 0)}"
        )

    print()
    print("===== FIND FIRST FAILURE-CLEARANCE OBSERVATIONS =====")

    observations = build_clearance_observations(unique_paths)

    print(
        f"FIRST CLEARANCE OBSERVATIONS = {len(observations)}"
    )

    print_clearance_cases(observations)
    print_path_class_summary(observations)
    print_state_transition_summary(observations)
    print_symbol_summary(observations)
    print_case_paths(observations)
    matched_control_analysis(observations)

    print()
    print("=" * 110)
    print("V13.17 PERSISTENT FAILURE CLEARANCE — INTERPRETATION")
    print("=" * 110)
    print(
        "The audit asks whether the path AFTER Persistent Failure "
        "contains information beyond the current state."
    )
    print(
        "A single case, symbol, or horizon does NOT validate a rule."
    )
    print(
        "No result from this audit becomes an entry, hold, warning, "
        "rescue, or exit rule."
    )
    print(
        "V13.17 remains research only."
    )
    print(
        "NO PRODUCTION CODE CHANGED."
    )

    print()
    print(
        "V13.17 PERSISTENT FAILURE CLEARANCE AUDIT COMPLETE"
    )


if __name__ == "__main__":
    main()
