"""
AIMn / KISS V13.17 COMPANION RESEARCH
PERSISTENT FAILURE PERSISTENCE / RE-ENTRY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
When PERSISTENT_FAILURE appears in a trajectory:

1. How long does the state persist?
2. Does it ever clear?
3. What state does it clear into?
4. Does it later re-enter PERSISTENT_FAILURE?
5. Does the trajectory ever recover after a Persistent-Failure episode?

This is a structural trajectory audit.

CASE KEY
--------
(symbol, direction, opposite_time)

IMPORTANT
---------
Episodes are described separately from unique trajectory cases.

Checkpoint observations are NOT treated as independent predictive cases.

The audit does NOT create an entry, hold, warning, rescue, or exit rule.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
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
NEUTRAL = "NEUTRAL"


@dataclass
class StateObservation:
    minutes: int
    state: str


@dataclass
class PersistentFailureEpisode:
    case_key: Tuple[Any, Any, Any]
    symbol: str
    direction: str
    opposite_time: Any

    start_minutes: int
    end_minutes: Optional[int]

    observation_count: int

    clearance_state: Optional[str]
    clearance_minutes: Optional[int]

    later_reentered: bool
    later_recovery_after_episode: bool

    full_state_path: Tuple[StateObservation, ...]


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
    Keep exactly one trajectory per:

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


def build_observations(
    path: Any,
) -> List[StateObservation]:

    raw = []

    for point in path_points(path):

        minutes = point_minutes(point)
        state = point_state(point)

        if minutes is None or state is None:
            continue

        raw.append(
            StateObservation(
                minutes=minutes,
                state=state,
            )
        )

    raw.sort(
        key=lambda item: item.minutes
    )

    return raw


def compress_consecutive_states(
    observations: Sequence[StateObservation],
) -> List[StateObservation]:

    if not observations:
        return []

    compressed = [observations[0]]

    for observation in observations[1:]:

        if (
            observation.state
            == compressed[-1].state
        ):
            # Preserve the latest time for the
            # current consecutive state block.
            compressed[-1] = observation
        else:
            compressed.append(observation)

    return compressed


def state_path_text(
    observations: Sequence[StateObservation],
) -> str:

    return " -> ".join(
        f"+{item.minutes}m:{item.state}"
        for item in observations
    )


def find_next_state_change(
    observations: Sequence[StateObservation],
    start_index: int,
) -> Optional[Tuple[int, StateObservation]]:

    current_state = observations[
        start_index
    ].state

    for index in range(
        start_index + 1,
        len(observations),
    ):

        candidate = observations[index]

        if candidate.state != current_state:
            return index, candidate

    return None


def build_persistent_failure_episodes(
    paths: Sequence[Any],
) -> List[PersistentFailureEpisode]:

    episodes: List[PersistentFailureEpisode] = []

    for path in dedup_case_paths(paths):

        observations = build_observations(path)

        if not observations:
            continue

        # Compress consecutive identical states.
        compressed = compress_consecutive_states(
            observations
        )

        case_key = (
            path_symbol(path),
            path_direction(path),
            path_opposite_time(path),
        )

        for index, observation in enumerate(
            compressed
        ):

            if observation.state != PERSISTENT:
                continue

            # Beginning of a Persistent-Failure episode:
            # either first state, or previous compressed
            # state was something else.
            if (
                index > 0
                and compressed[index - 1].state
                == PERSISTENT
            ):
                continue

            next_change = find_next_state_change(
                compressed,
                index,
            )

            if next_change is None:

                end_minutes = None
                clearance_state = None
                clearance_minutes = None
                later_reentered = False
                later_recovery_after_episode = False

            else:

                next_index, next_observation = next_change

                end_minutes = next_observation.minutes
                clearance_state = next_observation.state
                clearance_minutes = (
                    next_observation.minutes
                )

                later_reentered = any(
                    item.state == PERSISTENT
                    for item in compressed[
                        next_index + 1:
                    ]
                )

                recovery_positions = [
                    pos
                    for pos, item
                    in enumerate(
                        compressed[
                            next_index:
                        ],
                        start=next_index,
                    )
                    if item.state == RECOVERING
                ]

                later_recovery_after_episode = (
                    len(recovery_positions) > 0
                )

            # Determine how many original observed StatePoints
            # were inside this Persistent-Failure episode.
            start_minutes = observation.minutes

            if next_change is None:
                end_boundary = None
            else:
                end_boundary = (
                    next_change[1].minutes
                )

            episode_points = []

            for item in observations:

                if item.minutes < start_minutes:
                    continue

                if (
                    end_boundary is not None
                    and item.minutes >= end_boundary
                ):
                    break

                if item.state == PERSISTENT:
                    episode_points.append(item)

            episodes.append(
                PersistentFailureEpisode(
                    case_key=case_key,
                    symbol=path_symbol(path),
                    direction=path_direction(path),
                    opposite_time=path_opposite_time(path),

                    start_minutes=start_minutes,
                    end_minutes=end_minutes,

                    observation_count=len(
                        episode_points
                    ),

                    clearance_state=clearance_state,
                    clearance_minutes=clearance_minutes,

                    later_reentered=later_reentered,
                    later_recovery_after_episode=(
                        later_recovery_after_episode
                    ),

                    full_state_path=tuple(
                        observations
                    ),
                )
            )

    return episodes


def print_population_summary(
    paths: Sequence[Any],
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE POPULATION SUMMARY")
    print("=" * 110)

    unique_paths = dedup_case_paths(
        paths
    )

    cases_with_pf = {
        episode.case_key
        for episode in episodes
    }

    print(
        f"UNIQUE TRAJECTORY CASES      = "
        f"{len(unique_paths)}"
    )

    print(
        f"CASES WITH PERSISTENT FAILURE = "
        f"{len(cases_with_pf)}"
    )

    print(
        f"PERSISTENT FAILURE EPISODES  = "
        f"{len(episodes)}"
    )


def print_episode_detail(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE EPISODE DETAIL")
    print("=" * 110)

    if not episodes:
        print("NO PERSISTENT FAILURE EPISODES")
        return

    ordered = sorted(
        episodes,
        key=lambda item: (
            item.symbol,
            item.direction,
            item.start_minutes,
        ),
    )

    for number, episode in enumerate(
        ordered,
        start=1,
    ):

        print()
        print(f"EPISODE {number}")

        print(
            f"  SYMBOL              = "
            f"{episode.symbol}"
        )

        print(
            f"  DIRECTION           = "
            f"{episode.direction}"
        )

        print(
            f"  OPPOSITE_TIME       = "
            f"{episode.opposite_time}"
        )

        print(
            f"  PF START            = "
            f"+{episode.start_minutes}m"
        )

        if episode.end_minutes is None:
            print(
                "  PF CLEARANCE        = NONE / "
                "REMAINS TERMINAL"
            )
        else:
            print(
                f"  PF CLEARANCE        = "
                f"+{episode.end_minutes}m"
            )

        print(
            f"  CLEARANCE STATE     = "
            f"{episode.clearance_state}"
        )

        print(
            f"  PF STATEPOINTS      = "
            f"{episode.observation_count}"
        )

        if episode.end_minutes is None:
            duration = "TERMINAL"
        else:
            duration = (
                f"{episode.end_minutes - episode.start_minutes}m"
            )

        print(
            f"  PF DURATION WINDOW  = "
            f"{duration}"
        )

        print(
            f"  LATER RE-ENTERED    = "
            f"{episode.later_reentered}"
        )

        print(
            f"  LATER RECOVERY      = "
            f"{episode.later_recovery_after_episode}"
        )

        print(
            "  STATE PATH          = "
            + state_path_text(
                episode.full_state_path
            )
        )


def print_clearance_summary(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE CLEARANCE DESTINATIONS")
    print("=" * 110)

    cleared = [
        episode
        for episode in episodes
        if episode.clearance_state is not None
    ]

    terminal = [
        episode
        for episode in episodes
        if episode.clearance_state is None
    ]

    print(
        f"EPISODES THAT CLEARED = "
        f"{len(cleared)}"
    )

    print(
        f"TERMINAL EPISODES     = "
        f"{len(terminal)}"
    )

    if not cleared:
        print("NO CLEARANCE OBSERVATIONS")
        return

    counts = Counter(
        episode.clearance_state
        for episode in cleared
    )

    for state, count in sorted(
        counts.items()
    ):
        print(
            f"  {state:22s} "
            f"N={count}"
        )


def print_reentry_summary(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE RE-ENTRY SUMMARY")
    print("=" * 110)

    if not episodes:
        print("NONE")
        return

    total = len(episodes)

    reentered = sum(
        episode.later_reentered
        for episode in episodes
    )

    recovered = sum(
        episode.later_recovery_after_episode
        for episode in episodes
    )

    print(
        f"TOTAL PF EPISODES       = "
        f"{total}"
    )

    print(
        f"LATER PF RE-ENTRY       = "
        f"{reentered}"
    )

    print(
        f"LATER RECOVERY          = "
        f"{recovered}"
    )


def print_symbol_summary(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE EPISODES BY SYMBOL")
    print("=" * 110)

    counts = Counter(
        episode.symbol
        for episode in episodes
    )

    for symbol in SYMBOLS:
        print(
            f"{symbol:6s} "
            f"EPISODES={counts.get(symbol, 0)}"
        )


def print_direction_summary(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE EPISODES BY DIRECTION")
    print("=" * 110)

    counts = Counter(
        episode.direction
        for episode in episodes
    )

    for direction in (
        "LONG",
        "SHORT",
    ):

        print(
            f"{direction:6s} "
            f"EPISODES={counts.get(direction, 0)}"
        )


def print_duration_summary(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENT FAILURE DURATION WINDOWS")
    print("=" * 110)

    cleared = [
        episode
        for episode in episodes
        if (
            episode.end_minutes is not None
            and episode.end_minutes
            >= episode.start_minutes
        )
    ]

    if not cleared:
        print("NO CLEARED EPISODES")
        return

    duration_counts = Counter(
        episode.end_minutes
        - episode.start_minutes
        for episode in cleared
    )

    for duration, count in sorted(
        duration_counts.items()
    ):

        print(
            f"PF DURATION={duration:3d}m "
            f"N={count}"
        )


def print_case_level_summary(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("UNIQUE CASES WITH PERSISTENT FAILURE")
    print("=" * 110)

    case_groups: Dict[
        Tuple[Any, Any, Any],
        List[PersistentFailureEpisode]
    ] = defaultdict(list)

    for episode in episodes:
        case_groups[
            episode.case_key
        ].append(episode)

    for case_key, case_episodes in sorted(
        case_groups.items(),
        key=lambda item: (
            str(item[0][0]),
            str(item[0][1]),
            str(item[0][2]),
        ),
    ):

        symbol, direction, opposite_time = (
            case_key
        )

        print()
        print(
            f"{symbol} "
            f"{direction} "
            f"{opposite_time}"
        )

        print(
            f"  PF EPISODES = "
            f"{len(case_episodes)}"
        )

        for index, episode in enumerate(
            case_episodes,
            start=1,
        ):

            print(
                f"  EPISODE {index}: "
                f"+{episode.start_minutes}m "
                f"-> "
                f"{episode.clearance_state}"
                f"@+"
                f"{episode.end_minutes}m"
                if episode.end_minutes is not None
                else
                f"  EPISODE {index}: "
                f"+{episode.start_minutes}m "
                f"-> TERMINAL"
            )


def print_structural_findings(
    episodes: Sequence[PersistentFailureEpisode],
) -> None:

    print()
    print("=" * 110)
    print("STRUCTURAL FINDINGS")
    print("=" * 110)

    if not episodes:
        print(
            "No Persistent-Failure episodes were observed."
        )
        return

    cleared = [
        episode
        for episode in episodes
        if episode.clearance_state is not None
    ]

    continued_to_pf = [
        episode
        for episode in cleared
        if episode.clearance_state
        == PERSISTENT
    ]

    cleared_to_deteriorating = [
        episode
        for episode in cleared
        if episode.clearance_state
        == DETERIORATING
    ]

    cleared_to_recovering = [
        episode
        for episode in cleared
        if episode.clearance_state
        == RECOVERING
    ]

    print(
        f"PF EPISODES                  = "
        f"{len(episodes)}"
    )

    print(
        f"PF EPISODES THAT CLEAR       = "
        f"{len(cleared)}"
    )

    print(
        f"CLEAR -> DETERIORATING       = "
        f"{len(cleared_to_deteriorating)}"
    )

    print(
        f"CLEAR -> RECOVERING          = "
        f"{len(cleared_to_recovering)}"
    )

    print(
        f"CLEAR -> PERSISTENT_FAILURE  = "
        f"{len(continued_to_pf)}"
    )

    print()
    print(
        "This is a structural description only."
    )

    print(
        "No state path becomes an entry, hold, "
        "warning, rescue, or exit rule."
    )


def main() -> None:

    print("=" * 110)
    print(
        "V13.17 PERSISTENT FAILURE "
        "PERSISTENCE / RE-ENTRY AUDIT"
    )
    print("=" * 110)

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

    unique_paths = dedup_case_paths(
        all_paths
    )

    print(
        f"RAW PATH OBJECTS = "
        f"{len(all_paths)}"
    )

    print(
        f"UNIQUE TRAJECTORY CASES = "
        f"{len(unique_paths)}"
    )

    episodes = (
        build_persistent_failure_episodes(
            unique_paths
        )
    )

    print_population_summary(
        unique_paths,
        episodes,
    )

    print_episode_detail(
        episodes
    )

    print_clearance_summary(
        episodes
    )

    print_reentry_summary(
        episodes
    )

    print_symbol_summary(
        episodes
    )

    print_direction_summary(
        episodes
    )

    print_duration_summary(
        episodes
    )

    print_case_level_summary(
        episodes
    )

    print_structural_findings(
        episodes
    )

    print()
    print("=" * 110)
    print(
        "V13.17 PERSISTENT FAILURE "
        "PERSISTENCE — INTERPRETATION"
    )
    print("=" * 110)

    print(
        "This audit measures Persistence, "
        "Clearance, and Re-entry."
    )

    print(
        "Episode counts and checkpoint observations "
        "are not treated as independent predictive cases."
    )

    print(
        "A small number of Persistent-Failure episodes "
        "does NOT validate a trading rule."
    )

    print(
        "A zero recovery count does NOT prove recovery "
        "is impossible."
    )

    print(
        "NO PRODUCTION CODE CHANGED."
    )

    print()
    print(
        "V13.17 PERSISTENT FAILURE "
        "PERSISTENCE AUDIT COMPLETE"
    )


if __name__ == "__main__":
    main()
