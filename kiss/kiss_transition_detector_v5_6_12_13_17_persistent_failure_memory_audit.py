"""
KISS V13.17 COMPANION RESEARCH
PERSISTENT FAILURE MEMORY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
Does prior PERSISTENT_FAILURE history add information after the current
state is no longer PERSISTENT_FAILURE?

This is a case-level audit of trajectory memory.

CORE IDEA
---------
CURRENT STATE tells us what the trajectory looks like NOW.

PERSISTENT_FAILURE HISTORY tells us whether the trajectory previously
reached the persistent-failure state.

The key research question is whether that history still matters after
the current state changes.

CANONICAL CONDITION
-------------------
PERSISTENT_FAILURE HISTORY

CASE KEY
--------
(symbol, direction, opposite_time)

METHODOLOGY
-----------
- Uses the existing V13.17 expanded 8-symbol / 28-case population.
- One unique trajectory case at a time.
- First eligible MEMORY observation per case is used.
- Memory is tested only AFTER PERSISTENT_FAILURE history exists.
- Primary analysis excludes CURRENT_STATE=PERSISTENT_FAILURE,
  because in that state history and current condition overlap.
- Control is matched on:
      direction
      current state
      checkpoint
- Future return is measured FROM THE MEMORY CHECKPOINT.
- No trading rule is created.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple
import importlib


# ---------------------------------------------------------------------------
# Existing V13.17 research implementation
# ---------------------------------------------------------------------------

rep = importlib.import_module(
    "kiss.kiss_transition_detector_v5_6_12_13_17_googl_replication_audit"
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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


def fmt(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{value:+.3f}%"


def point_at(path: Any, minutes: int) -> Optional[Any]:
    return rep.point_at(path, minutes)


def sequence_through(
    path: Any,
    checkpoint: int,
) -> List[str]:
    return rep.sequence_through(
        path,
        checkpoint,
    )


def history_present(
    path: Any,
    checkpoint: int,
) -> bool:
    sequence = sequence_through(
        path,
        checkpoint,
    )

    return "PERSISTENT_FAILURE" in sequence


def future_return_from_checkpoint(
    direction: str,
    checkpoint_point: Any,
    future_point: Any,
) -> Optional[float]:

    return rep.future_return_from_checkpoint(
        direction,
        checkpoint_point,
        future_point,
    )


def unique_cases() -> List[Any]:
    raw = rep.build_unique_cases()

    by_key: Dict[Tuple[str, str, Any], Any] = {}

    for path in raw:
        key = (
            path.symbol,
            path.direction,
            path.opposite_time,
        )

        if key not in by_key:
            by_key[key] = path

    return list(by_key.values())


# ---------------------------------------------------------------------------
# Find first memory observation after persistent failure
# ---------------------------------------------------------------------------

def find_first_memory_observation(
    path: Any,
) -> Optional[Dict[str, Any]]:
    """
    Find the first checkpoint where:

      PERSISTENT_FAILURE_HISTORY = True

    while:

      CURRENT_STATE != PERSISTENT_FAILURE

    This isolates residual trajectory memory after the current state
    has moved away from persistent failure.
    """

    for checkpoint in CHECKPOINTS:

        point = point_at(
            path,
            checkpoint,
        )

        if point is None:
            continue

        if not history_present(
            path,
            checkpoint,
        ):
            continue

        current_state = point.state

        if current_state == "PERSISTENT_FAILURE":
            continue

        future = {}

        for horizon in FUTURE_HORIZONS:

            future_point = point_at(
                path,
                checkpoint + horizon,
            )

            if future_point is None:
                future[horizon] = None
                continue

            future[horizon] = future_return_from_checkpoint(
                path.direction,
                point,
                future_point,
            )

        return {
            "symbol": path.symbol,
            "direction": path.direction,
            "opposite_time": path.opposite_time,
            "checkpoint": checkpoint,
            "current_state": current_state,
            "current_return": point.return_pct,
            "sequence": sequence_through(
                path,
                checkpoint,
            ),
            "future": future,
        }

    return None


# ---------------------------------------------------------------------------
# Find first persistent failure itself
# ---------------------------------------------------------------------------

def find_first_persistent_state(
    path: Any,
) -> Optional[Dict[str, Any]]:

    for checkpoint in CHECKPOINTS:

        point = point_at(
            path,
            checkpoint,
        )

        if point is None:
            continue

        if point.state != "PERSISTENT_FAILURE":
            continue

        return {
            "symbol": path.symbol,
            "direction": path.direction,
            "opposite_time": path.opposite_time,
            "checkpoint": checkpoint,
            "current_return": point.return_pct,
            "sequence": sequence_through(
                path,
                checkpoint,
            ),
        }

    return None


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------

def population_summary(
    cases: Sequence[Any],
) -> None:

    print("=" * 80)
    print("V13.17 PERSISTENT FAILURE MEMORY AUDIT")
    print("=" * 80)
    print()
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print()

    print(
        f"UNIQUE TRAJECTORY CASES: {len(cases)}"
    )

    by_symbol = defaultdict(int)

    for path in cases:
        by_symbol[path.symbol] += 1

    print()

    for symbol in SYMBOLS:
        print(
            f"{symbol:5s} CASES={by_symbol[symbol]:2d}"
        )

    print()


# ---------------------------------------------------------------------------
# Memory observations
# ---------------------------------------------------------------------------

def memory_observations(
    cases: Sequence[Any],
) -> List[Dict[str, Any]]:

    observations = []

    for path in cases:

        record = find_first_memory_observation(
            path
        )

        if record is not None:
            observations.append(record)

    print("=" * 80)
    print("FIRST RESIDUAL-MEMORY OBSERVATIONS")
    print("=" * 80)
    print()

    print(
        "One observation per case: first checkpoint where prior "
        "PERSISTENT_FAILURE exists but CURRENT_STATE is different."
    )
    print()

    if not observations:
        print(
            "NO CASES FOUND."
        )
        print()
        return observations

    for record in sorted(
        observations,
        key=lambda r: (
            r["symbol"],
            r["opposite_time"],
        ),
    ):

        print("-" * 80)

        print(
            f"{record['symbol']:5s} "
            f"{record['direction']:5s} "
            f"OPPOSITE={record['opposite_time']}"
        )

        print(
            f"  FIRST MEMORY CHECKPOINT="
            f"+{record['checkpoint']}m"
        )

        print(
            f"  CURRENT STATE="
            f"{record['current_state']}"
        )

        print(
            f"  CURRENT RETURN="
            f"{fmt(record['current_return'])}"
        )

        print(
            "  HISTORY SEQUENCE="
            + (
                " -> ".join(record["sequence"])
                if record["sequence"]
                else "NONE"
            )
        )

        for horizon in FUTURE_HORIZONS:

            value = record["future"].get(
                horizon
            )

            print(
                f"  FUTURE +{horizon:02d}m "
                f"FROM MEMORY CHECKPOINT="
                f"{fmt(value)}"
            )

    print()

    return observations


# ---------------------------------------------------------------------------
# Memory by symbol
# ---------------------------------------------------------------------------

def memory_by_symbol(
    observations: Sequence[Dict[str, Any]],
) -> None:

    print("=" * 80)
    print("RESIDUAL MEMORY BY SYMBOL")
    print("=" * 80)

    grouped = defaultdict(list)

    for record in observations:
        grouped[
            record["symbol"]
        ].append(record)

    print()

    for symbol in SYMBOLS:

        rows = grouped.get(
            symbol,
            [],
        )

        counts = defaultdict(int)

        for row in rows:
            counts[
                row["current_state"]
            ] += 1

        state_text = (
            " ".join(
                f"{state}={counts[state]}"
                for state in sorted(counts)
            )
            if counts
            else "NONE"
        )

        print(
            f"{symbol:5s} "
            f"MEMORY_CASES={len(rows):2d} "
            f"{state_text}"
        )

    print()


# ---------------------------------------------------------------------------
# Matched control comparison
# ---------------------------------------------------------------------------

def matched_memory_control(
    cases: Sequence[Any],
    observations: Sequence[Dict[str, Any]],
) -> None:

    print("=" * 80)
    print("MATCHED RESIDUAL-MEMORY CONTROL")
    print("=" * 80)

    print()
    print(
        "MATCH KEY = DIRECTION + CURRENT STATE + CHECKPOINT"
    )
    print(
        "PRESENT = prior persistent failure exists"
    )
    print(
        "ABSENT = no prior persistent failure exists"
    )
    print()

    # -----------------------------------------------------------------------
    # Build one comparison observation per case per checkpoint.
    #
    # This is intentionally case-level. We never count repeated checkpoints
    # for one case as independent evidence in this primary analysis.
    # -----------------------------------------------------------------------

    candidates = []

    for path in cases:

        for checkpoint in CHECKPOINTS:

            point = point_at(
                path,
                checkpoint,
            )

            if point is None:
                continue

            # Exclude CURRENT_STATE=PERSISTENT_FAILURE because history is
            # redundant with the current state there.
            if point.state == "PERSISTENT_FAILURE":
                continue

            candidates.append(
                (
                    path,
                    checkpoint,
                    point,
                    history_present(
                        path,
                        checkpoint,
                    ),
                )
            )

    # -----------------------------------------------------------------------
    # For each case, keep only its first eligible MEMORY state and first
    # eligible ABSENT state at the matching control stratum. This keeps the
    # evidence case-oriented rather than checkpoint-oriented.
    # -----------------------------------------------------------------------

    present_by_key = defaultdict(list)
    absent_by_key = defaultdict(list)

    for path, checkpoint, point, present in candidates:

        key = (
            path.direction,
            point.state,
            checkpoint,
        )

        future_returns = {}

        for horizon in FUTURE_HORIZONS:

            future_point = point_at(
                path,
                checkpoint + horizon,
            )

            if future_point is None:
                continue

            value = future_return_from_checkpoint(
                path.direction,
                point,
                future_point,
            )

            if value is not None:
                future_returns[horizon] = value

        row = {
            "case_key": (
                path.symbol,
                path.direction,
                path.opposite_time,
            ),
            "symbol": path.symbol,
            "direction": path.direction,
            "state": point.state,
            "checkpoint": checkpoint,
            "future": future_returns,
        }

        if present:
            present_by_key[key].append(row)
        else:
            absent_by_key[key].append(row)

    # -----------------------------------------------------------------------
    # Deduplicate case observations.
    # -----------------------------------------------------------------------

    def dedupe(rows):
        seen = set()
        result = []

        for row in rows:

            key = row["case_key"]

            if key in seen:
                continue

            seen.add(key)
            result.append(row)

        return result

    valid_rows = []

    for key in sorted(
        set(present_by_key)
        | set(absent_by_key)
    ):

        present = dedupe(
            present_by_key.get(
                key,
                [],
            )
        )

        absent = dedupe(
            absent_by_key.get(
                key,
                [],
            )
        )

        if not present or not absent:
            continue

        direction, state, checkpoint = key

        for horizon in FUTURE_HORIZONS:

            p_values = [
                row["future"][horizon]
                for row in present
                if horizon in row["future"]
            ]

            a_values = [
                row["future"][horizon]
                for row in absent
                if horizon in row["future"]
            ]

            if not p_values or not a_values:
                continue

            p_avg = sum(p_values) / len(p_values)
            a_avg = sum(a_values) / len(a_values)

            delta = p_avg - a_avg

            valid_rows.append(
                (
                    direction,
                    state,
                    checkpoint,
                    horizon,
                    len(p_values),
                    len(a_values),
                    p_avg,
                    a_avg,
                    delta,
                )
            )

    if not valid_rows:
        print(
            "NO TWO-SIDED CASE-LEVEL MEMORY COMPARISONS."
        )
        print()
        return

    for row in valid_rows:

        (
            direction,
            state,
            checkpoint,
            horizon,
            p_n,
            a_n,
            p_avg,
            a_avg,
            delta,
        ) = row

        print(
            f"{direction:5s} "
            f"STATE={state:18s} "
            f"CP=+{checkpoint:02d}m "
            f"H=+{horizon:02d}m "
            f"P_N={p_n:2d} "
            f"A_N={a_n:2d} "
            f"P_AVG={fmt(p_avg):>9s} "
            f"A_AVG={fmt(a_avg):>9s} "
            f"DELTA={fmt(delta):>9s}"
        )

    print()


# ---------------------------------------------------------------------------
# Important overlap audit
# ---------------------------------------------------------------------------

def overlap_audit(
    cases: Sequence[Any],
) -> None:

    print("=" * 80)
    print("HISTORY / CURRENT-STATE OVERLAP AUDIT")
    print("=" * 80)
    print()

    total_memory = 0
    overlap_persistent = 0
    residual_memory = 0

    residual_states = defaultdict(int)

    for path in cases:

        for checkpoint in CHECKPOINTS:

            if not history_present(
                path,
                checkpoint,
            ):
                continue

            total_memory += 1

            point = point_at(
                path,
                checkpoint,
            )

            if point is None:
                continue

            if point.state == "PERSISTENT_FAILURE":
                overlap_persistent += 1
            else:
                residual_memory += 1
                residual_states[
                    point.state
                ] += 1

    print(
        f"MEMORY OBSERVATIONS: {total_memory}"
    )

    print(
        f"CURRENT=PERSISTENT_FAILURE: {overlap_persistent}"
    )

    print(
        f"CURRENT!=PERSISTENT_FAILURE: {residual_memory}"
    )

    print()

    for state in sorted(residual_states):
        print(
            f"RESIDUAL MEMORY + CURRENT STATE "
            f"{state}: "
            f"{residual_states[state]}"
        )

    print()


# ---------------------------------------------------------------------------
# GOOGL focus
# ---------------------------------------------------------------------------

def googl_focus(
    observations: Sequence[Dict[str, Any]],
) -> None:

    print("=" * 80)
    print("GOOGL RESIDUAL-MEMORY FOCUS")
    print("=" * 80)
    print()

    rows = [
        row
        for row in observations
        if row["symbol"] == "GOOGL"
    ]

    if not rows:
        print(
            "GOOGL HAS NO RESIDUAL-MEMORY OBSERVATION."
        )
        print()
        return

    for row in rows:

        print("-" * 80)

        print(
            f"GOOGL {row['direction']} "
            f"OPPOSITE={row['opposite_time']}"
        )

        print(
            f"  FIRST MEMORY CHECKPOINT="
            f"+{row['checkpoint']}m"
        )

        print(
            f"  CURRENT STATE="
            f"{row['current_state']}"
        )

        print(
            f"  CURRENT RETURN="
            f"{fmt(row['current_return'])}"
        )

        print(
            "  SEQUENCE="
            + " -> ".join(
                row["sequence"]
            )
        )

        for horizon in FUTURE_HORIZONS:

            value = row["future"].get(
                horizon
            )

            print(
                f"  FUTURE +{horizon}m="
                f"{fmt(value)}"
            )

    print()


# ---------------------------------------------------------------------------
# Final interpretation
# ---------------------------------------------------------------------------

def interpretation(
    cases: Sequence[Any],
    observations: Sequence[Dict[str, Any]],
) -> None:

    print("=" * 80)
    print("V13.17 PERSISTENT FAILURE MEMORY — INTERPRETATION")
    print("=" * 80)
    print()

    print(
        f"UNIQUE CASES: {len(cases)}"
    )

    print(
        f"RESIDUAL-MEMORY CASES: {len(observations)}"
    )

    print()

    print(
        "PRIMARY QUESTION:"
    )

    print(
        "Does prior persistent failure remain informative "
        "after CURRENT_STATE changes?"
    )

    print()

    print(
        "If memory persists while CURRENT_STATE is recovering, "
        "deteriorating, or neutral, it may represent trajectory "
        "history rather than simply duplicating the current state."
    )

    print()

    print(
        "The evidence is descriptive and exploratory."
    )

    print(
        "Small samples do NOT validate a trading rule."
    )

    print(
        "NO ENTRY / HOLD / WARNING / EXIT RULE CREATED."
    )

    print(
        "NO PRODUCTION ENGINE CHANGE."
    )

    print(
        "NO ORDERS."
    )

    print(
        "NO AI TRAINING."
    )

    print()

    print("=" * 80)
    print("PERSISTENT FAILURE MEMORY AUDIT COMPLETE")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:

    cases = unique_cases()

    population_summary(
        cases
    )

    observations = memory_observations(
        cases
    )

    memory_by_symbol(
        observations
    )

    overlap_audit(
        cases
    )

    googl_focus(
        observations
    )

    matched_memory_control(
        cases,
        observations
    )

    interpretation(
        cases,
        observations
    )


if __name__ == "__main__":
    main()
