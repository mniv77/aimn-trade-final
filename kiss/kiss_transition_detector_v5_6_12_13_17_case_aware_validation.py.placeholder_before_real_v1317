#  File name: /kiss_transition_detector_v5_6_12_13_15_sequence_motif_information_audit.py

# V5.6.12.11 - Trajectory State Machine
# V5.6.12.13 - Classification Outcome Validation
# RESEARCH ONLY - NO ORDERS - NO PRODUCTION ENGINE CHANGES
# RESEARCH ONLY - NO ORDERS - NO PRODUCTION ENGINE CHANGES

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import kiss_transition_detector_v5_6_12_8_persistent_reversal as v128

def val(row, *names):
    for name in names:
        if isinstance(row, dict):
            if name in row:
                return row[name]
        elif hasattr(row, name):
            return getattr(row, name)
    return None


CHECKPOINTS = (5, 10, 15, 20, 25, 30, 45, 60)

RECOVERY_MOVE_PCT = 0.10
DETERIORATING_MOVE_PCT = 0.20
PERSISTENT_MOVE_PCT = 0.50

RECOVERY_FAVORABLE_RATIO = 0.50
DETERIORATING_ADVERSE_RATIO = 0.67

DETERIORATING_CONSECUTIVE = 2
PERSISTENT_CONSECUTIVE = 3

@dataclass
class StatePoint:
    minutes: int
    state: str
    return_pct: float
    favorable_ratio: float
    adverse_ratio: float
    consecutive_adverse: int
    mae_pct: float
    mfe_pct: float

@dataclass
class StatePath:
    symbol: str
    direction: str
    opposite_time: datetime
    official_time: datetime
    warning_lead: float
    points: List[StatePoint]
def signed_return(direction: str, entry_price: float, price: float) -> float:
    if not entry_price:
        return 0.0

    raw = (price - entry_price) / entry_price * 100.0

    if direction == "SHORT":
        raw = -raw

    return raw


def classify_state(
    return_pct: float,
    favorable_ratio: float,
    adverse_ratio: float,
    consecutive_adverse: int,
) -> str:
    if (
        return_pct <= -PERSISTENT_MOVE_PCT
        and (
            consecutive_adverse >= PERSISTENT_CONSECUTIVE
            or adverse_ratio >= DETERIORATING_ADVERSE_RATIO
        )
    ):
        return "PERSISTENT_FAILURE"

    if (
        return_pct >= RECOVERY_MOVE_PCT
        and favorable_ratio >= RECOVERY_FAVORABLE_RATIO
    ):
        return "RECOVERING"

    if (
        return_pct <= -DETERIORATING_MOVE_PCT
        or adverse_ratio >= DETERIORATING_ADVERSE_RATIO
        or consecutive_adverse >= DETERIORATING_CONSECUTIVE
    ):
        return "DETERIORATING"

    return "NEUTRAL"
def close_index(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    for i, row in enumerate(rows):
        ts = val(row, "timestamp", "time", "datetime", "date")
        if ts + timedelta(minutes=5) == target:
            return i
    return None


def price_from_row(row: Any) -> float:
    x = val(row, "close", "Close", "c")
    if x is None:
        raise KeyError("No close price found")
    return float(x)


def measure_checkpoint(
    rows: Sequence[Dict[str, Any]],
    start_index: int,
    direction: str,
    entry_price: float,
    minutes: int,
) -> Optional[StatePoint]:
    target_time = val(rows[start_index], "timestamp", "time", "datetime", "date") + timedelta(minutes=minutes)

    end_index = close_index(rows, target_time)
    if end_index is None or end_index <= start_index:
        return None

    prices = [price_from_row(rows[i]) for i in range(start_index, end_index + 1)]

    if not prices:
        return None

    return_pct = signed_return(direction, entry_price, prices[-1])

    favorable = 0
    adverse = 0
    consecutive = 0
    max_consecutive = 0

    for i in range(1, len(prices)):
        move = signed_return(direction, prices[i - 1], prices[i])

        if move > 0:
            favorable += 1
            consecutive = 0
        elif move < 0:
            adverse += 1
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)

    total_moves = favorable + adverse

    favorable_ratio = favorable / total_moves if total_moves else 0.0
    adverse_ratio = adverse / total_moves if total_moves else 0.0

    mae_pct = min(
        signed_return(direction, entry_price, price)
        for price in prices
    )

    mfe_pct = max(
        signed_return(direction, entry_price, price)
        for price in prices
    )

    state = classify_state(
        return_pct,
        favorable_ratio,
        adverse_ratio,
        max_consecutive,
    )

    return StatePoint(
        minutes=minutes,
        state=state,
        return_pct=return_pct,
        favorable_ratio=favorable_ratio,
        adverse_ratio=adverse_ratio,
        consecutive_adverse=max_consecutive,
        mae_pct=mae_pct,
        mfe_pct=mfe_pct,
    )
def build_state_path(
    rows5: Sequence[Dict[str, Any]],
    case: Any,
) -> Optional[StatePath]:
    start_index = close_index(rows5, case.opposite_time)

    if start_index is None:
        return None

    entry_price = float(case.decision_price)

    points: List[StatePoint] = []

    for minutes in CHECKPOINTS:
        point = measure_checkpoint(
            rows5,
            start_index,
            case.direction,
            entry_price,
            minutes,
        )

        if point is not None:
            points.append(point)

    if not points:
        return None

    return StatePath(
        symbol=case.symbol,
        direction=case.direction,
        opposite_time=case.opposite_time,
        official_time=case.official_time,
        warning_lead=case.warning_lead,
        points=points,
    )


def path_label(path: StatePath) -> str:
    labels = ["OPPOSITE_DETECTED"]

    previous = None

    for point in path.points:
        if point.state != previous:
            labels.append(point.state)
            previous = point.state

    return " -> ".join(labels)

def process_symbol(symbol: str) -> List[StatePath]:
    rows5 = v128.v125.base.load_rows(symbol, "5m")
    rows30 = v128.v125.base.load_rows(symbol, "30m")

    if not rows5 or not rows30:
        print(f"{symbol}: missing data")
        return []

    transitions = v128.v125.base.build_directional_transitions(symbol, rows30)
    observations = v128.v125.base.build_warning_observations(symbol, rows5)
    episodes = v128.v125.base.cluster_warning_episodes(observations)
    assignments = v128.v125.base.assign_one_episode_per_transition(transitions, episodes)

    paths: List[StatePath] = []

    for transition, episode in assignments:
        lead = (transition.timestamp - episode.first_timestamp).total_seconds() / 60.0
        assignment = v128.v125.base.Assignment(transition, episode, lead)
        case = v128.evaluate_assignment(rows5, assignment)

        if case is None:
            continue

        path = build_state_path(rows5, case)
        if path is not None:
            paths.append(path)

    print(f"{symbol}: transitions={len(transitions)} assignments={len(assignments)} trajectory_cases={len(paths)}")
    return paths


def main() -> None:
    symbols = ("NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ")
    all_paths: List[StatePath] = []

    print("=" * 72)
    print("V5.6.12.11 - TRAJECTORY STATE MACHINE")
    print("RESEARCH ONLY - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 72)

    for symbol in symbols:
        try:
            paths = process_symbol(symbol)
            all_paths.extend(paths)
        except Exception as exc:
            print(f"{symbol}: ERROR {exc}")

    print()
    print(f"TOTAL TRAJECTORY CASES = {len(all_paths)}")
    print()

    for path in all_paths:
        print(
            f"{path.symbol} {path.direction} "
            f"opposite={path.opposite_time} "
            f"official={path.official_time} "
            f"lead={path.warning_lead:.1f}m"
        )
        print(f"  PATH: {path_label(path)}")

        for point in path.points:
            print(
                f"  +{point.minutes:>2}m "
                f"{point.state:<18} "
                f"ret={point.return_pct:+.3f}% "
                f"fav={point.favorable_ratio:.1%} "
                f"adv={point.adverse_ratio:.1%} "
                f"consec={point.consecutive_adverse}"
            )

    print()
    print("=" * 72)
    print("CHECKPOINT SUMMARY")
    print("=" * 72)

    for minutes in CHECKPOINTS:
        points = [
            point
            for path in all_paths
            for point in path.points
            if point.minutes == minutes
        ]

        if not points:
            continue

        avg_return = sum(point.return_pct for point in points) / len(points)
        recovering = sum(point.state == "RECOVERING" for point in points)
        neutral = sum(point.state == "NEUTRAL" for point in points)
        deteriorating = sum(point.state == "DETERIORATING" for point in points)
        persistent = sum(point.state == "PERSISTENT_FAILURE" for point in points)

        print(
            f"+{minutes:>2}m N={len(points):>2} "
            f"AVG={avg_return:+.3f}% "
            f"REC={recovering} "
            f"NEUT={neutral} "
            f"DET={deteriorating} "
            f"PERSIST={persistent}"
        )

    print()
    print("=" * 90)
    print("GLOBAL CLASSIFICATION VALIDATION")
    print("=" * 90)

    results = []

    for path in all_paths:
        classification = classify_path(path)

        row = {
            "symbol": path.symbol,
            "direction": path.direction,
            "classification": classification,
        }

        for minutes in (15, 30, 45, 60):
            value = next((point.return_pct for point in path.points if point.minutes == minutes), None)
            row[minutes] = value
            row[f"label_{minutes}"] = outcome_label(value)

        results.append(row)

    classifications = (
        "HOLD",
        "WARNING",
        "EXIT_CANDIDATE",
        "REVERSAL_CONFIRMED",
    )

    for classification in classifications:
        subset = [
            r for r in results
            if r["classification"] == classification
        ]

        print()
        print(f"{classification}: N={len(subset)}")

        for minutes in (15, 30, 45, 60):
            values = [
                r[minutes]
                for r in subset
                if r[minutes] is not None
            ]

            if not values:
                continue

            favorable = sum(
                r[f"label_{minutes}"] == "FAVORABLE"
                for r in subset
            )

            adverse = sum(
                r[f"label_{minutes}"] == "ADVERSE"
                for r in subset
            )

            neutral = sum(
                r[f"label_{minutes}"] == "NEUTRAL"
                for r in subset
            )

            avg = sum(values) / len(values)

            print(
                f"  +{minutes}m N={len(values):2d} "
                f"AVG={avg:+.3f}% "
                f"FAV={favorable:2d} "
                f"ADV={adverse:2d} "
                f"NEU={neutral:2d}"
            )




    run_v131_causal_validation(all_paths)
    run_v132_fixed_horizon_validation(all_paths)
    run_v133_exit_reversal_validation(all_paths)
    run_v134_recovery_failure_validation(all_paths)
    run_v135_trajectory_shape_validation(all_paths)
    run_v136_trajectory_shape_validation(all_paths)
    run_v137_post_state_validation(all_paths)
    trajectory_events = run_v138_state_sequence_validation(all_paths)

    return all_paths, trajectory_events

def classify_path(path: StatePath) -> str:
    states = [point.state for point in path.points]
    persistent_count = states.count("PERSISTENT_FAILURE")
    has_recovery = "RECOVERING" in states
    final_state = states[-1] if states else "NEUTRAL"

    if persistent_count >= 2 and final_state == "PERSISTENT_FAILURE":
        return "REVERSAL_CONFIRMED"

    if persistent_count >= 1:
        return "EXIT_CANDIDATE"

    if final_state == "DETERIORATING":
        return "WARNING"

    if has_recovery or final_state == "NEUTRAL":
        return "HOLD"

    return "WARNING"


def classify_prefix(path: StatePath, minutes: int) -> str:
    prefix = [point for point in path.points if point.minutes <= minutes]

    if not prefix:
        return "WARNING"

    states = [point.state for point in prefix]
    persistent_count = states.count("PERSISTENT_FAILURE")
    has_recovery = "RECOVERING" in states
    final_state = states[-1]

    if persistent_count >= 2 and final_state == "PERSISTENT_FAILURE":
        return "REVERSAL_CONFIRMED"

    if persistent_count >= 1:
        return "EXIT_CANDIDATE"

    if final_state == "DETERIORATING":
        return "WARNING"

    if has_recovery or final_state == "NEUTRAL":
        return "HOLD"

    return "WARNING"


def outcome_label(return_pct: Optional[float]) -> str:
    if return_pct is None:
        return "UNKNOWN"

    if return_pct >= 0.25:
        return "FAVORABLE"

    if return_pct <= -0.25:
        return "ADVERSE"

    return "NEUTRAL"

def run_v131_causal_validation(paths):
    print()
    print("=" * 90)
    print("V13.1 - CAUSAL / LIVE-TIMING VALIDATION")
    print("Only information available at each checkpoint is used.")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (10, 15, 20, 25, 30, 45, 60)

    results = []

    for path in paths:
        if not path.points:
            continue

        for minutes in checkpoints:
            point = next(
                (p for p in path.points if p.minutes == minutes),
                None,
            )

            if point is None:
                continue

            state = classify_prefix(path, minutes)

            future_points = [
                p for p in path.points
                if p.minutes > minutes
            ]

            if not future_points:
                continue

            final_point = future_points[-1]

            results.append({
                "symbol": path.symbol,
                "direction": path.direction,
                "opposite_time": path.opposite_time,
                "official_time": path.official_time,
                "decision_minutes": minutes,
                "decision_state": state,
                "decision_return": point.return_pct,
                "future_60_return": final_point.return_pct,
            })

    print()
    print("DECISION-POINT SUMMARY")
    print("-" * 90)

    for minutes in checkpoints:
        subset = [
            r for r in results
            if r["decision_minutes"] == minutes
        ]

        if not subset:
            continue

        print()
        print(f"+{minutes}m  N={len(subset)}")

        for state in (
            "HOLD",
            "WARNING",
            "EXIT_CANDIDATE",
            "REVERSAL_CONFIRMED",
        ):
            rows = [
                r for r in subset
                if r["decision_state"] == state
            ]

            if not rows:
                continue

            values = [
                r["decision_return"]
                for r in rows
                if r["decision_return"] is not None
            ]

            if not values:
                continue

            favorable = sum(v >= 0.25 for v in values)
            adverse = sum(v <= -0.25 for v in values)
            neutral = len(values) - favorable - adverse

            avg = sum(values) / len(values)

            print(
                f"  {state:20s} "
                f"N={len(values):2d} "
                f"AVG={avg:+.3f}% "
                f"FAV={favorable:2d} "
                f"ADV={adverse:2d} "
                f"NEU={neutral:2d}"
            )

    print()
    print("=" * 90)
    print("FIRST EXIT / REVERSAL DECISION")
    print("=" * 90)

    first_decisions = []

    for path in paths:
        for minutes in checkpoints:
            state = classify_prefix(path, minutes)

            if state in (
                "EXIT_CANDIDATE",
                "REVERSAL_CONFIRMED",
            ):
                point = next(
                    (p for p in path.points if p.minutes == minutes),
                    None,
                )

                if point is not None:
                    first_decisions.append({
                        "symbol": path.symbol,
                        "direction": path.direction,
                        "minutes": minutes,
                        "state": state,
                        "return": point.return_pct,
                    })
                    break

    if not first_decisions:
        print("No causal exit decisions detected.")
        return

    for row in first_decisions:
        print(
            f"{row['symbol']:5s} "
            f"{row['direction']:5s} "
            f"+{row['minutes']:2d}m "
            f"{row['state']:20s} "
            f"return={row['return']:+.3f}%"
        )

    print()
    print(
        f"FIRST CAUSAL EXIT/REVERSAL DECISIONS = "
        f"{len(first_decisions)}"
    )

    avg = sum(r["return"] for r in first_decisions) / len(first_decisions)

    print(f"AVERAGE DECISION RETURN = {avg:+.3f}%")


def run_v132_fixed_horizon_validation(paths):
    print()
    print("=" * 90)
    print("V13.2 - FIXED 60-MINUTE FORWARD-HORIZON VALIDATION")
    print("Decision uses only information available at the decision checkpoint.")
    print("Outcome is measured exactly 60 minutes AFTER that decision.")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (10, 15, 20, 25, 30, 45, 60)
    results = []

    # Cache 5m data once per symbol.
    rows_cache = {}

    for path in paths:
        if not path.points:
            continue

        if path.symbol not in rows_cache:
            rows_cache[path.symbol] = v128.v125.base.load_rows(
                path.symbol, "5m"
            )

        rows5 = rows_cache[path.symbol]

        if not rows5:
            continue

        start_index = close_index(rows5, path.opposite_time)

        if start_index is None:
            continue

        for minutes in checkpoints:
            decision_point = next(
                (p for p in path.points if p.minutes == minutes),
                None,
            )

            if decision_point is None:
                continue

            decision_time = (
                path.opposite_time + timedelta(minutes=minutes)
            )

            future_time = decision_time + timedelta(minutes=60)

            future_index = close_index(rows5, future_time)

            if future_index is None:
                continue

            decision_index = close_index(rows5, decision_time)

            if decision_index is None:
                continue

            decision_price = price_from_row(rows5[decision_index])
            future_price = price_from_row(rows5[future_index])

            forward_return = signed_return(
                path.direction,
                decision_price,
                future_price,
            )

            state = classify_prefix(path, minutes)

            results.append({
                "symbol": path.symbol,
                "direction": path.direction,
                "decision_minutes": minutes,
                "decision_state": state,
                "decision_return": decision_point.return_pct,
                "forward_60_return": forward_return,
            })

    print()
    print("FIXED-HORIZON DECISION SUMMARY")
    print("-" * 90)

    for minutes in checkpoints:
        subset = [
            r for r in results
            if r["decision_minutes"] == minutes
        ]

        if not subset:
            continue

        print()
        print(f"+{minutes}m  N={len(subset)}")

        for state in (
            "HOLD",
            "WARNING",
            "EXIT_CANDIDATE",
            "REVERSAL_CONFIRMED",
        ):
            rows = [
                r for r in subset
                if r["decision_state"] == state
            ]

            if not rows:
                continue

            values = [
                r["forward_60_return"]
                for r in rows
                if r["forward_60_return"] is not None
            ]

            if not values:
                continue

            favorable = sum(v >= 0.25 for v in values)
            adverse = sum(v <= -0.25 for v in values)
            neutral = len(values) - favorable - adverse

            avg = sum(values) / len(values)

            print(
                f"  {state:20s} "
                f"N={len(values):2d} "
                f"AVG_60M={avg:+.3f}% "
                f"FAV={favorable:2d} "
                f"ADV={adverse:2d} "
                f"NEU={neutral:2d}"
            )

    print()
    print("=" * 90)
    print("FIRST CAUSAL EXIT / REVERSAL — FIXED 60-MINUTE OUTCOME")
    print("=" * 90)

    first_decisions = []

    for path in paths:
        for minutes in checkpoints:
            state = classify_prefix(path, minutes)

            if state not in (
                "EXIT_CANDIDATE",
                "REVERSAL_CONFIRMED",
            ):
                continue

            if path.symbol not in rows_cache:
                rows_cache[path.symbol] = v128.v125.base.load_rows(
                    path.symbol, "5m"
                )

            rows5 = rows_cache[path.symbol]

            decision_index = close_index(
                rows5,
                path.opposite_time + timedelta(minutes=minutes),
            )

            future_index = close_index(
                rows5,
                path.opposite_time + timedelta(minutes=minutes + 60),
            )

            if decision_index is None or future_index is None:
                continue

            decision_price = price_from_row(rows5[decision_index])
            future_price = price_from_row(rows5[future_index])

            forward_return = signed_return(
                path.direction,
                decision_price,
                future_price,
            )

            first_decisions.append({
                "symbol": path.symbol,
                "direction": path.direction,
                "minutes": minutes,
                "state": state,
                "forward_return": forward_return,
            })

            break

    if not first_decisions:
        print("No causal exit/reversal decisions with fixed horizon.")
        return

    for row in first_decisions:
        outcome = outcome_label(row["forward_return"])

        print(
            f"{row['symbol']:5s} "
            f"{row['direction']:5s} "
            f"+{row['minutes']:2d}m "
            f"{row['state']:20s} "
            f"NEXT_60M={row['forward_return']:+.3f}% "
            f"{outcome}"
        )

    print()
    print(
        f"FIRST CAUSAL EXIT/REVERSAL DECISIONS = "
        f"{len(first_decisions)}"
    )

    avg = (
        sum(r["forward_return"] for r in first_decisions)
        / len(first_decisions)
    )

    improved = sum(
        r["forward_return"] < 0
        for r in first_decisions
    )

    print(f"AVERAGE NEXT-60M RETURN = {avg:+.3f}%")
    print(
        f"EXIT WOULD HAVE AVOIDED ADVERSE MOVE = "
        f"{improved}/{len(first_decisions)}"
    )


def run_v133_exit_reversal_validation(paths):
    print()
    print("=" * 90)
    print("V13.3 - EXIT CANDIDATE / REVERSAL CONFIRMATION VALIDATION")
    print("Decision uses only information available at the decision checkpoint.")
    print("Tests whether deterioration recovers or continues into the opposite trend.")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (10, 15, 20, 25, 30, 45, 60)
    rows_cache = {}
    first_decisions = []

    for path in paths:
        if not path.points:
            continue

        if path.symbol not in rows_cache:
            rows_cache[path.symbol] = v128.v125.base.load_rows(
                path.symbol, "5m"
            )

        rows5 = rows_cache[path.symbol]

        if not rows5:
            continue

        for minutes in checkpoints:
            state = classify_prefix(path, minutes)

            if state not in (
                "EXIT_CANDIDATE",
                "REVERSAL_CONFIRMED",
            ):
                continue

            decision_time = (
                path.opposite_time + timedelta(minutes=minutes)
            )

            decision_index = close_index(rows5, decision_time)

            if decision_index is None:
                continue

            decision_price = price_from_row(rows5[decision_index])

            horizon_results = {}

            for horizon in (15, 30, 60):
                future_time = (
                    decision_time + timedelta(minutes=horizon)
                )

                future_index = close_index(rows5, future_time)

                if future_index is None:
                    continue

                future_price = price_from_row(rows5[future_index])

                horizon_results[horizon] = signed_return(
                    path.direction,
                    decision_price,
                    future_price,
                )

            if not horizon_results:
                continue

            first_decisions.append({
                "symbol": path.symbol,
                "direction": path.direction,
                "minutes": minutes,
                "state": state,
                "returns": horizon_results,
            })

            break

    print()
    print("FIRST EXIT / REVERSAL DECISIONS")
    print("-" * 90)

    if not first_decisions:
        print("No qualifying decisions with complete forward horizons.")
        return

    for row in first_decisions:
        values = row["returns"]

        parts = []
        for horizon in (15, 30, 60):
            if horizon in values:
                parts.append(
                    f"{horizon}M={values[horizon]:+.3f}%"
                )

        print(
            f"{row['symbol']:5s} "
            f"{row['direction']:5s} "
            f"+{row['minutes']:2d}m "
            f"{row['state']:20s} "
            + " ".join(parts)
        )

    print()
    print("CLASSIFICATION OUTCOME SUMMARY")
    print("-" * 90)

    for state in (
        "EXIT_CANDIDATE",
        "REVERSAL_CONFIRMED",
    ):
        subset = [
            row for row in first_decisions
            if row["state"] == state
        ]

        if not subset:
            continue

        print()
        print(f"{state}")

        for horizon in (15, 30, 60):
            values = [
                row["returns"][horizon]
                for row in subset
                if horizon in row["returns"]
            ]

            if not values:
                continue

            favorable = sum(v >= 0.25 for v in values)
            adverse = sum(v <= -0.25 for v in values)
            neutral = len(values) - favorable - adverse
            avg = sum(values) / len(values)

            print(
                f"  NEXT {horizon:2d}M: "
                f"N={len(values):2d} "
                f"AVG={avg:+.3f}% "
                f"FAV={favorable:2d} "
                f"ADV={adverse:2d} "
                f"NEU={neutral:2d}"
            )

    print()
    print("=" * 90)
    print("V13.3 INTERPRETATION DATA")
    print("=" * 90)

    exit_rows = [
        row for row in first_decisions
        if row["state"] == "EXIT_CANDIDATE"
    ]

    reversal_rows = [
        row for row in first_decisions
        if row["state"] == "REVERSAL_CONFIRMED"
    ]

    print(
        f"FIRST EXIT_CANDIDATE DECISIONS = {len(exit_rows)}"
    )
    print(
        f"FIRST REVERSAL_CONFIRMED DECISIONS = {len(reversal_rows)}"
    )

    for label, subset in (
        ("EXIT_CANDIDATE", exit_rows),
        ("REVERSAL_CONFIRMED", reversal_rows),
    ):
        if not subset:
            continue

        adverse_60 = sum(
            row["returns"].get(60, 0.0) <= -0.25
            for row in subset
            if 60 in row["returns"]
        )

        favorable_60 = sum(
            row["returns"].get(60, 0.0) >= 0.25
            for row in subset
            if 60 in row["returns"]
        )

        print(
            f"{label}: "
            f"60M_ADVERSE={adverse_60} "
            f"60M_FAVORABLE={favorable_60}"
        )


def run_v134_recovery_failure_validation(paths):
    print()
    print("=" * 90)
    print("V13.4 - RECOVERY VS CONTINUED FAILURE VALIDATION")
    print("Starts at the first causal EXIT_CANDIDATE.")
    print("Examines the following 15m / 30m / 45m / 60m trajectory.")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (15, 30, 45, 60)
    rows_cache = {}
    candidates = []

    for path in paths:
        if not path.points:
            continue

        if path.symbol not in rows_cache:
            rows_cache[path.symbol] = v128.v125.base.load_rows(
                path.symbol, "5m"
            )

        rows5 = rows_cache[path.symbol]

        if not rows5:
            continue

        first_candidate = None

        for minutes in (10, 15, 20, 25, 30, 45, 60):
            state = classify_prefix(path, minutes)

            if state == "EXIT_CANDIDATE":
                first_candidate = minutes
                break

        if first_candidate is None:
            continue

        decision_time = (
            path.opposite_time
            + timedelta(minutes=first_candidate)
        )

        decision_index = close_index(rows5, decision_time)

        if decision_index is None:
            continue

        decision_price = price_from_row(rows5[decision_index])

        trajectory = []

        for horizon in checkpoints:
            future_time = (
                decision_time
                + timedelta(minutes=horizon)
            )

            future_index = close_index(rows5, future_time)

            if future_index is None:
                continue

            future_price = price_from_row(rows5[future_index])

            forward_return = signed_return(
                path.direction,
                decision_price,
                future_price,
            )

            trajectory.append({
                "minutes": horizon,
                "return": forward_return,
            })

        if not trajectory:
            continue

        candidates.append({
            "symbol": path.symbol,
            "direction": path.direction,
            "candidate_minutes": first_candidate,
            "trajectory": trajectory,
        })

    print()
    print("EXIT_CANDIDATE TRAJECTORIES")
    print("-" * 90)

    for row in candidates:
        parts = []

        for point in row["trajectory"]:
            parts.append(
                f"+{point['minutes']}M="
                f"{point['return']:+.3f}%"
            )

        print(
            f"{row['symbol']:5s} "
            f"{row['direction']:5s} "
            f"candidate@+{row['candidate_minutes']:2d}m "
            + " ".join(parts)
        )

    print()
    print("=" * 90)
    print("V13.4 TRAJECTORY CLASSIFICATION")
    print("=" * 90)

    classified = []

    for row in candidates:
        values = [
            point["return"]
            for point in row["trajectory"]
        ]

        if not values:
            continue

        start = values[0]
        final = values[-1]
        minimum = min(values)
        maximum = max(values)

        # Recovery:
        # final outcome is positive and the trajectory recovered
        # from a materially adverse point.
        if final >= 0.25 and minimum <= -0.10:
            classification = "RECOVERY"

        # Continued failure:
        # final outcome is materially adverse and the trajectory
        # remains below the starting decision point.
        elif final <= -0.25 and final <= start:
            classification = "CONTINUED_FAILURE"

        # Mixed:
        # substantial movement in both directions without a
        # decisive final outcome.
        elif (
            maximum >= 0.25
            and minimum <= -0.25
        ):
            classification = "MIXED"

        else:
            classification = "NEUTRAL"

        classified.append({
            **row,
            "classification": classification,
        })

        print(
            f"{row['symbol']:5s} "
            f"{row['direction']:5s} "
            f"candidate@+{row['candidate_minutes']:2d}m "
            f"{classification:18s} "
            f"START={start:+.3f}% "
            f"FINAL={final:+.3f}% "
            f"MIN={minimum:+.3f}% "
            f"MAX={maximum:+.3f}%"
        )

    print()
    print("CLASSIFICATION SUMMARY")
    print("-" * 90)

    for classification in (
        "RECOVERY",
        "CONTINUED_FAILURE",
        "MIXED",
        "NEUTRAL",
    ):
        subset = [
            row
            for row in classified
            if row["classification"] == classification
        ]

        if not subset:
            continue

        final_values = [
            row["trajectory"][-1]["return"]
            for row in subset
        ]

        average = (
            sum(final_values) / len(final_values)
        )

        print(
            f"{classification:18s} "
            f"N={len(subset):2d} "
            f"AVG_FINAL_60M={average:+.3f}%"
        )

    print()
    print("=" * 90)
    print(
        f"TOTAL FIRST EXIT_CANDIDATE TRAJECTORIES = "
        f"{len(classified)}"
    )
    print("=" * 90)


def run_v135_trajectory_shape_validation(paths):
    print()
    print("=" * 90)
    print("V13.5 - EARLIEST TRAJECTORY SHAPE VALIDATION")
    print("Starts at the first causal EXIT_CANDIDATE.")
    print("Uses 5-minute trajectory points to separate recovery from continued failure.")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (5, 10, 15, 20, 25, 30, 45, 60)
    rows_cache = {}
    candidates = []

    for path in paths:
        if not path.points:
            continue

        if path.symbol not in rows_cache:
            rows_cache[path.symbol] = v128.v125.base.load_rows(
                path.symbol, "5m"
            )

        rows5 = rows_cache[path.symbol]

        if not rows5:
            continue

        first_candidate = None

        for minutes in (10, 15, 20, 25, 30, 45, 60):
            state = classify_prefix(path, minutes)

            if state == "EXIT_CANDIDATE":
                first_candidate = minutes
                break

        if first_candidate is None:
            continue

        decision_time = (
            path.opposite_time
            + timedelta(minutes=first_candidate)
        )

        decision_index = close_index(rows5, decision_time)

        if decision_index is None:
            continue

        decision_price = price_from_row(rows5[decision_index])

        trajectory = []

        for minutes in checkpoints:
            future_time = (
                decision_time
                + timedelta(minutes=minutes)
            )

            future_index = close_index(rows5, future_time)

            if future_index is None:
                continue

            future_price = price_from_row(rows5[future_index])

            forward_return = signed_return(
                path.direction,
                decision_price,
                future_price,
            )

            trajectory.append({
                "minutes": minutes,
                "return": forward_return,
            })

        if trajectory:
            candidates.append({
                "symbol": path.symbol,
                "direction": path.direction,
                "candidate_minutes": first_candidate,
                "trajectory": trajectory,
            })

    print()
    print("5-MINUTE TRAJECTORY SHAPES")
    print("-" * 90)

    classified = []

    for row in candidates:
        points = row["trajectory"]

        if not points:
            continue

        values = [p["return"] for p in points]

        classification = "UNRESOLVED"
        separation = None

        # Look for the earliest point where the trajectory has
        # clearly separated into continued adverse movement
        # or sustained recovery.
        for i in range(1, len(values)):
            previous = values[i - 1]
            current = values[i]

            if (
                current <= -0.25
                and current < previous
                and all(
                    values[j] <= values[j - 1]
                    for j in range(1, i + 1)
                )
            ):
                classification = "CONTINUED_FAILURE"
                separation = points[i]["minutes"]
                break

            if (
                current >= 0.25
                and current > previous
                and all(
                    values[j] >= values[j - 1]
                    for j in range(1, i + 1)
                )
            ):
                classification = "RECOVERY"
                separation = points[i]["minutes"]
                break

        if separation is None:
            # A trajectory can recover without being monotonically
            # increasing, or fail without being monotonically decreasing.
            # Mark these as unresolved rather than forcing a label.
            classification = "UNRESOLVED"

        classified.append({
            **row,
            "classification": classification,
            "separation_minutes": separation,
        })

        final_return = values[-1]

        print(
            f"{row['symbol']:5s} "
            f"{row['direction']:5s} "
            f"candidate@+{row['candidate_minutes']:2d}m "
            f"{classification:20s} "
            f"EARLIEST="
            f"{'+' + str(separation) + 'm' if separation is not None else '---':>5s} "
            f"FINAL={final_return:+.3f}% "
            f"PATH="
            + " ".join(
                f"+{p['minutes']}:{p['return']:+.3f}%"
                for p in points
            )
        )

    print()
    print("V13.5 SUMMARY")
    print("-" * 90)

    for classification in (
        "RECOVERY",
        "CONTINUED_FAILURE",
        "UNRESOLVED",
    ):
        subset = [
            row
            for row in classified
            if row["classification"] == classification
        ]

        if not subset:
            continue

        final_values = [
            row["trajectory"][-1]["return"]
            for row in subset
        ]

        average = sum(final_values) / len(final_values)

        separation_values = [
            row["separation_minutes"]
            for row in subset
            if row["separation_minutes"] is not None
        ]

        if separation_values:
            avg_separation = (
                sum(separation_values)
                / len(separation_values)
            )
            separation_text = (
                f"AVG_EARLIEST={avg_separation:.1f}m"
            )
        else:
            separation_text = "AVG_EARLIEST=---"

        print(
            f"{classification:20s} "
            f"N={len(subset):2d} "
            f"AVG_FINAL_60M={average:+.3f}% "
            f"{separation_text}"
        )

    print()
    print(
        f"TOTAL FIRST EXIT_CANDIDATE TRAJECTORIES = "
        f"{len(classified)}"
    )
    print("=" * 90)



def run_v136_trajectory_shape_validation(paths):
    """
    V13.6 - TRAJECTORY SHAPE / STABILIZATION VALIDATION

    Starts at the first causal EXIT_CANDIDATE.
    Uses only information available at each 5-minute checkpoint.

    Research only:
      - NO ORDERS
      - NO DB WRITES
      - NO PRODUCTION ENGINE CHANGES

    Unlike V13.5, trajectory does not have to be monotonic.

    The purpose is to distinguish:
        continued deterioration
        stabilization / mixed behavior
        recovery

    from the actual shape of the path.
    """
    print()
    print("=" * 90)
    print("V13.6 - TRAJECTORY SHAPE / STABILIZATION VALIDATION")
    print("Starts at the first causal EXIT_CANDIDATE.")
    print("Uses non-monotonic 5-minute trajectory shape.")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (5, 10, 15, 20, 25, 30, 45, 60)

    def classify_shape(points):
        """
        Classify using information available through the current checkpoint.

        The classifier deliberately does NOT require a monotonic path.

        Features:
          current             latest return
          minimum             deepest adverse point so far
          maximum             best favorable point so far
          recovery_from_low  improvement from worst point
          recent_move        latest 5m change
          prior_recovery     whether the path has already started recovering
        """
        if not points:
            return "UNRESOLVED"

        current = points[-1]["return_pct"]
        minimum = min(x["return_pct"] for x in points)
        maximum = max(x["return_pct"] for x in points)

        recovery_from_low = current - minimum

        recent_move = 0.0
        if len(points) >= 2:
            recent_move = current - points[-2]["return_pct"]

        # Count recent improving and deteriorating steps.
        improving = 0
        deteriorating = 0

        for i in range(1, len(points)):
            delta = points[i]["return_pct"] - points[i - 1]["return_pct"]
            if delta > 0:
                improving += 1
            elif delta < 0:
                deteriorating += 1

        # CONTINUED FAILURE:
        # adverse excursion is meaningful, the current point is still adverse,
        # and the path is not recovering from its worst point.
        if (
            current <= -0.25
            and recovery_from_low < 0.10
            and recent_move <= 0.02
        ):
            return "CONTINUED_FAILURE"

        # RECOVERY:
        # A recovery can contain temporary pullbacks.
        # Require meaningful recovery from the adverse extreme and
        # evidence that improvement has persisted.
        if (
            recovery_from_low >= 0.30
            and current >= 0.10
            and recent_move >= -0.05
            and improving >= deteriorating
        ):
            return "RECOVERY"

        # STABILIZING:
        # The worst point is no longer expanding and the latest movement
        # is improving, but recovery is not yet strong enough.
        if (
            recovery_from_low >= 0.15
            and recent_move >= 0.0
            and improving >= deteriorating
        ):
            return "STABILIZING"

        return "UNRESOLVED"

    rows_out = []

    for path in paths:
        symbol = path.symbol
        direction = path.direction

        # Use the same causal candidate extraction as V13.5.
        # EXIT_CANDIDATE is a classification produced by classify_prefix(),
        # not a literal StatePoint.state value.
        candidate_minutes = None

        for minutes in (10, 15, 20, 25, 30, 45, 60):
            state = classify_prefix(path, minutes)

            if state == "EXIT_CANDIDATE":
                candidate_minutes = minutes
                break

        if candidate_minutes is None:
            continue

        # Rebuild the FULL 5-minute trajectory from the causal candidate.
        # This gives V13.6 the same trajectory basis used by V13.5.
        rows5 = v128.v125.base.load_rows(symbol, "5m")

        decision_time = path.opposite_time + timedelta(minutes=candidate_minutes)

        candidate_idx = close_index(rows5, decision_time)
        if candidate_idx is None:
            continue

        candidate_price = price_from_row(rows5[candidate_idx])

        trajectory = []

        for minutes in (5, 10, 15, 20, 25, 30, 45, 60):
            target_time = decision_time + timedelta(minutes=minutes)
            idx = close_index(rows5, target_time)
            if idx is None:
                continue

            price = price_from_row(rows5[idx])

            if direction == "LONG":
                return_pct = ((price - candidate_price) / candidate_price) * 100.0
            else:
                return_pct = ((candidate_price - price) / candidate_price) * 100.0

            trajectory.append({
                "minutes": minutes,
                "return_pct": return_pct,
            })

        if not trajectory:
            continue

        # The first candidate point is the reference point.
        # Therefore +5m below means five minutes after the candidate.
        trajectory = [
            x for x in trajectory
            if x["minutes"] in checkpoints
        ]

        if not trajectory:
            continue

        print(
            f"{symbol:5s} {direction:5s} "
            f"candidate@+{candidate_minutes}m "
            f"PATH=" +
            " ".join(
                f"+{x['minutes']}:{x['return_pct']:+.3f}%"
                for x in trajectory
            )
        )

        previous_class = None

        for j in range(1, len(trajectory) + 1):
            visible = trajectory[:j]
            cls = classify_shape(visible)

            if cls != previous_class:
                if cls in (
                    "RECOVERY",
                    "CONTINUED_FAILURE",
                    "STABILIZING",
                ):
                    rows_out.append({
                        "symbol": symbol,
                        "direction": direction,
                        "candidate": candidate_minutes,
                        "checkpoint": visible[-1]["minutes"],
                        "classification": cls,
                    })

                    print(
                        f"  +{visible[-1]['minutes']:>2}m "
                        f"{cls}"
                    )

                    previous_class = cls

        final_class = classify_shape(trajectory)

        print(
            f"  FINAL_SHAPE={final_class}"
        )

    print()
    print("=" * 90)
    print("V13.6 SUMMARY")
    print("-" * 90)

    for cls in (
        "CONTINUED_FAILURE",
        "STABILIZING",
        "RECOVERY",
    ):
        subset = [
            x for x in rows_out
            if x["classification"] == cls
        ]

        if subset:
            avg_cp = (
                sum(x["checkpoint"] for x in subset)
                / len(subset)
            )

            print(
                f"{cls:20s} "
                f"N={len(subset):2d} "
                f"AVG_EARLIEST={avg_cp:.1f}m"
            )
        else:
            print(
                f"{cls:20s} "
                f"N= 0 "
                f"AVG_EARLIEST=---"
            )

    print(
        f"TOTAL CLASSIFICATION EVENTS = {len(rows_out)}"
    )
    print("=" * 90)


def run_v137_post_state_validation(paths):
    """
    V13.7 - POST-STATE OUTCOME VALIDATION

    Validates what actually happens AFTER V13.6 first recognizes:
        CONTINUED_FAILURE
        STABILIZING
        RECOVERY

    The V13.6 state is determined only from information available
    through that checkpoint.

    The following 60 minutes are strictly future evaluation.

    Research only:
      - NO ORDERS
      - NO DB WRITES
      - NO PRODUCTION ENGINE CHANGES
    """

    print()
    print("=" * 90)
    print("V13.7 - POST-STATE OUTCOME VALIDATION")
    print("What happens during the 60 minutes AFTER first V13.6 state recognition")
    print("Research only - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 90)

    checkpoints = (5, 10, 15, 30, 45, 60)

    def classify_shape(points):
        if not points:
            return "UNRESOLVED"

        current = points[-1]["return_pct"]
        minimum = min(x["return_pct"] for x in points)

        recovery_from_low = current - minimum

        recent_move = 0.0
        if len(points) >= 2:
            recent_move = (
                current - points[-2]["return_pct"]
            )

        improving = 0
        deteriorating = 0

        for prev, cur in zip(points, points[1:]):
            delta = cur["return_pct"] - prev["return_pct"]

            if delta > 0:
                improving += 1
            elif delta < 0:
                deteriorating += 1

        if (
            current <= -0.25
            and recovery_from_low < 0.10
            and recent_move <= 0.02
        ):
            return "CONTINUED_FAILURE"

        if (
            recovery_from_low >= 0.30
            and current >= 0.10
            and recent_move >= -0.05
            and improving >= deteriorating
        ):
            return "RECOVERY"

        if (
            recovery_from_low >= 0.15
            and recent_move >= 0.0
            and improving >= deteriorating
        ):
            return "STABILIZING"

        return "UNRESOLVED"

    def outcome_label(value):
        if value is None:
            return "UNKNOWN"

        if value >= 0.25:
            return "FAVORABLE"

        if value <= -0.25:
            return "ADVERSE"

        return "NEUTRAL"

    events = []

    for path in paths:

        if not path.points:
            continue

        symbol = path.symbol
        direction = path.direction

        # Find the FIRST causal EXIT_CANDIDATE.
        candidate_minutes = None

        for minutes in (10, 15, 20, 25, 30, 45, 60):
            state = classify_prefix(path, minutes)

            if state == "EXIT_CANDIDATE":
                candidate_minutes = minutes
                break

        if candidate_minutes is None:
            continue

        rows5 = v128.v125.base.load_rows(symbol, "5m")

        decision_time = (
            path.opposite_time
            + timedelta(minutes=candidate_minutes)
        )

        candidate_idx = close_index(rows5, decision_time)

        if candidate_idx is None:
            continue

        candidate_price = price_from_row(rows5[candidate_idx])

        trajectory = []

        for minutes in (5, 10, 15, 20, 25, 30, 45, 60):

            target_time = (
                decision_time
                + timedelta(minutes=minutes)
            )

            idx = close_index(rows5, target_time)

            if idx is None:
                continue

            price = price_from_row(rows5[idx])

            if direction == "LONG":
                return_pct = (
                    (price - candidate_price)
                    / candidate_price
                ) * 100.0
            else:
                return_pct = (
                    (candidate_price - price)
                    / candidate_price
                ) * 100.0

            trajectory.append({
                "minutes": minutes,
                "return_pct": return_pct,
            })

        if len(trajectory) < 2:
            continue

        previous = None

        for j in range(1, len(trajectory) + 1):

            visible = trajectory[:j]

            classification = classify_shape(visible)

            if classification == previous:
                continue

            if classification not in (
                "CONTINUED_FAILURE",
                "STABILIZING",
                "RECOVERY",
            ):
                continue

            checkpoint = visible[-1]["minutes"]

            future = [
                x for x in trajectory
                if x["minutes"] > checkpoint
            ]

            if not future:
                continue

            # Strictly future outcome.
            final_60 = None
            for x in future:
                if x["minutes"] == checkpoint + 60:
                    final_60 = x["return_pct"]
                    break

            # If +60 is not available, use the furthest available
            # future point, but mark it as the available horizon.
            if final_60 is None:
                final_60 = future[-1]["return_pct"]

            future_values = [
                x["return_pct"]
                for x in future
            ]

            mfe = max(future_values)
            mae = min(future_values)

            row = {
                "symbol": symbol,
                "direction": direction,
                "candidate_minutes": candidate_minutes,
                "state_checkpoint": checkpoint,
                "classification": classification,
                "final_60": final_60,
                "mfe": mfe,
                "mae": mae,
                "outcome": outcome_label(final_60),
            }

            events.append(row)

            print(
                f"{symbol:5s} "
                f"{direction:5s} "
                f"STATE=+{checkpoint:2d}m "
                f"{classification:20s} "
                f"NEXT60={final_60:+.3f}% "
                f"MFE={mfe:+.3f}% "
                f"MAE={mae:+.3f}% "
                f"{row['outcome']}"
            )

            previous = classification

    print()
    print("=" * 90)
    print("V13.7 SUMMARY BY FIRST RECOGNIZED STATE")
    print("=" * 90)

    for classification in (
        "CONTINUED_FAILURE",
        "STABILIZING",
        "RECOVERY",
    ):

        subset = [
            x for x in events
            if x["classification"] == classification
        ]

        if not subset:
            print(
                f"{classification:20s} "
                f"N= 0"
            )
            continue

        favorable = sum(
            x["outcome"] == "FAVORABLE"
            for x in subset
        )

        adverse = sum(
            x["outcome"] == "ADVERSE"
            for x in subset
        )

        neutral = sum(
            x["outcome"] == "NEUTRAL"
            for x in subset
        )

        avg_final = (
            sum(x["final_60"] for x in subset)
            / len(subset)
        )

        avg_mfe = (
            sum(x["mfe"] for x in subset)
            / len(subset)
        )

        avg_mae = (
            sum(x["mae"] for x in subset)
            / len(subset)
        )

        print(
            f"{classification:20s} "
            f"N={len(subset):2d} "
            f"FAV={favorable:2d} "
            f"ADV={adverse:2d} "
            f"NEU={neutral:2d} "
            f"AVG60={avg_final:+.3f}% "
            f"AVG_MFE={avg_mfe:+.3f}% "
            f"AVG_MAE={avg_mae:+.3f}%"
        )

    print()
    print("=" * 90)
    print("V13.7 DIRECTIONAL VALIDATION")
    print("=" * 90)

    for direction in ("LONG", "SHORT"):

        subset = [
            x for x in events
            if x["direction"] == direction
        ]

        if not subset:
            print(f"{direction:5s} N=0")
            continue

        favorable = sum(
            x["outcome"] == "FAVORABLE"
            for x in subset
        )

        adverse = sum(
            x["outcome"] == "ADVERSE"
            for x in subset
        )

        neutral = sum(
            x["outcome"] == "NEUTRAL"
            for x in subset
        )

        avg_final = (
            sum(x["final_60"] for x in subset)
            / len(subset)
        )

        print(
            f"{direction:5s} "
            f"N={len(subset):2d} "
            f"FAV={favorable:2d} "
            f"ADV={adverse:2d} "
            f"NEU={neutral:2d} "
            f"AVG60={avg_final:+.3f}%"
        )

    print()
    print("=" * 90)
    print(
        f"TOTAL V13.7 POST-STATE EVENTS = {len(events)}"
    )
    print("=" * 90)



def run_v138_state_sequence_validation(paths):
    """
    V13.9.1 — STATE-SEQUENCE OUTCOME VALIDATION

    Same V13.8/V13.9 causal sequence recognition.

    V13.9.1 fixes measurement only:
      • sequence completion is identified causally
      • exact 15m / 30m / 60m forward returns are measured
      • MFE / MAE use the complete 5m path, not sparse checkpoints
      • no engine or trading-rule changes
    """

    print("\n" + "=" * 90)
    print("V13.9.1 — STATE-SEQUENCE OUTCOME VALIDATION")
    print("=" * 90)

    CHECKS = (5, 10, 15, 20, 25, 30, 45, 60)
    CANDIDATES = (10, 15, 20, 25, 30, 45, 60)

    meaningful_states = {
        "CONTINUED_FAILURE",
        "STABILIZING",
        "RECOVERY",
    }

    def classify_shape(points):
        if not points:
            return "UNRESOLVED", None

        current = points[-1]["return_pct"]
        minimum = min(p["return_pct"] for p in points)
        recovery_from_low = current - minimum

        recent_move = (
            points[-1]["return_pct"] - points[-2]["return_pct"]
            if len(points) >= 2 else 0.0
        )

        improving = 0
        deteriorating = 0

        for prev, cur in zip(points, points[1:]):
            if cur["return_pct"] > prev["return_pct"]:
                improving += 1
            elif cur["return_pct"] < prev["return_pct"]:
                deteriorating += 1

        if (
            current <= -0.25
            and recovery_from_low < 0.10
            and recent_move <= 0.02
        ):
            return "CONTINUED_FAILURE", current

        if (
            recovery_from_low >= 0.30
            and current >= 0.10
            and recent_move >= -0.05
            and improving >= deteriorating
        ):
            return "RECOVERY", current

        if (
            recovery_from_low >= 0.15
            and recent_move >= 0.0
            and improving >= deteriorating
        ):
            return "STABILIZING", current

        return "UNRESOLVED", current

    def directional_return(direction, entry_price, price):
        if entry_price is None or price is None or entry_price == 0:
            return None

        if direction == "LONG":
            return ((price - entry_price) / entry_price) * 100.0

        return ((entry_price - price) / entry_price) * 100.0

    events = []

    for path in paths:
        direction = path.direction
        symbol = path.symbol

        # ------------------------------------------------------------
        # 1. Find the FIRST causal EXIT_CANDIDATE exactly as before.
        # ------------------------------------------------------------
        candidate_minutes = None

        for minutes in CANDIDATES:
            state = classify_prefix(path, minutes)

            if state == "EXIT_CANDIDATE":
                candidate_minutes = minutes
                break

        if candidate_minutes is None:
            continue

        # ------------------------------------------------------------
        # 2. Load the complete 5m data.
        # ------------------------------------------------------------
        rows5 = v128.v125.base.load_rows(symbol, "5m")

        decision_time = (
            path.opposite_time
            + timedelta(minutes=candidate_minutes)
        )

        candidate_idx = close_index(rows5, decision_time)

        if candidate_idx is None:
            continue

        candidate_price = price_from_row(rows5[candidate_idx])

        if candidate_price is None or candidate_price == 0:
            continue

        # ------------------------------------------------------------
        # 3. Build the complete 5m trajectory.
        # ------------------------------------------------------------
        trajectory = []

        for row in rows5:
            close_time = row.timestamp + timedelta(minutes=5)

            if close_time <= decision_time:
                continue

            minutes_from_candidate = (
                close_time - decision_time
            ).total_seconds() / 60.0

            if minutes_from_candidate > 60:
                break

            price = price_from_row(row)

            ret = directional_return(
                direction,
                candidate_price,
                price,
            )

            if ret is None:
                continue

            trajectory.append({
                "time": close_time,
                "minutes": minutes_from_candidate,
                "return_pct": ret,
                "price": price,
            })

        if not trajectory:
            continue

        # ------------------------------------------------------------
        # 4. Reconstruct the V13.6 shape sequence.
        # ------------------------------------------------------------
        checkpoint_points = []

        for minutes in CHECKS:
            eligible = [
                p for p in trajectory
                if p["minutes"] <= minutes
            ]

            if not eligible:
                continue

            # Use the latest 5m observation available at this checkpoint.
            checkpoint_points.append({
                "minutes": minutes,
                "return_pct": eligible[-1]["return_pct"],
            })

        states = []

        for i in range(len(checkpoint_points)):
            state, _ = classify_shape(
                checkpoint_points[:i + 1]
            )

            states.append(state)

        meaningful = [
            state for state in states
            if state in meaningful_states
        ]

        compressed = []

        for state in meaningful:
            if not compressed or compressed[-1] != state:
                compressed.append(state)

        if len(compressed) < 2:
            continue

        target_sequence = tuple(compressed)

        # ------------------------------------------------------------
        # 5. Find the EXACT checkpoint where the complete sequence
        #    first exists.
        #
        #    This is causal: only states observed up to that checkpoint
        #    are allowed to create the sequence.
        # ------------------------------------------------------------
        completion_minutes = None

        for i in range(len(checkpoint_points)):
            prefix_states = []

            for j in range(i + 1):
                state = classify_shape(
                    checkpoint_points[:j + 1]
                )[0]

                if state in meaningful_states:
                    if (
                        not prefix_states
                        or prefix_states[-1] != state
                    ):
                        prefix_states.append(state)

            if tuple(prefix_states) == target_sequence:
                completion_minutes = checkpoint_points[i]["minutes"]
                break

        if completion_minutes is None:
            continue

        # We need at least some data after completion.
        completion_time = (
            decision_time
            + timedelta(minutes=completion_minutes)
        )

        # ------------------------------------------------------------
        # 6. Exact 15m / 30m / 60m outcomes from the COMPLETE 5m path.
        # ------------------------------------------------------------
        horizon_results = {}

        for horizon in (15, 30, 60):
            target_time = (
                completion_time
                + timedelta(minutes=horizon)
            )

            future = [
                p for p in trajectory
                if p["time"] <= target_time
            ]

            if not future:
                continue

            # Require the requested horizon to actually exist.
            last = future[-1]

            if abs(
                (last["time"] - target_time).total_seconds()
            ) > 1:
                continue

            returns = [
                p["return_pct"]
                for p in future
            ]

            horizon_results[horizon] = {
                "return_pct": last["return_pct"],
                "mfe_pct": max(returns),
                "mae_pct": min(returns),
                "outcome": outcome_label(last["return_pct"]),
            }

        # ------------------------------------------------------------
        # 7. Need at least one complete forward horizon.
        # ------------------------------------------------------------
        if not horizon_results:
            continue

        event = {
            "symbol": symbol,
            "direction": direction,
            "candidate_minutes": candidate_minutes,
            "completion_minutes": completion_minutes,
            "completion_time": completion_time,
            "sequence": " -> ".join(target_sequence),
            "sequence_length": len(target_sequence),
            "horizons": horizon_results,
        }

        events.append(event)

        print(
            f"{symbol:5s} {direction:5s} "
            f"CANDIDATE +{candidate_minutes:>2.0f}m "
            f"COMPLETE +{completion_minutes:>2.0f}m "
            f"| {event['sequence']}"
        )

        for horizon in (15, 30, 60):
            result = horizon_results.get(horizon)

            if result is None:
                print(
                    f"  {horizon:>2}m: NO DATA"
                )
                continue

            print(
                f"  {horizon:>2}m: "
                f"RET={result['return_pct']:+.3f}% "
                f"MFE={result['mfe_pct']:+.3f}% "
                f"MAE={result['mae_pct']:+.3f}% "
                f"{result['outcome']}"
            )

    # ================================================================
    # SUMMARY BY SEQUENCE
    # ================================================================
    print("\nV13.9.1 SUMMARY BY COMPLETE SEQUENCE")

    sequences = sorted(
        set(event["sequence"] for event in events)
    )

    for sequence in sequences:
        group = [
            event for event in events
            if event["sequence"] == sequence
        ]

        print(
            f"\n{sequence} N={len(group)}"
        )

        for horizon in (15, 30, 60):
            values = [
                event["horizons"][horizon]
                for event in group
                if horizon in event["horizons"]
            ]

            if not values:
                continue

            favorable = sum(
                x["outcome"] == "FAVORABLE"
                for x in values
            )

            adverse = sum(
                x["outcome"] == "ADVERSE"
                for x in values
            )

            neutral = sum(
                x["outcome"] == "NEUTRAL"
                for x in values
            )

            avg_ret = sum(
                x["return_pct"] for x in values
            ) / len(values)

            avg_mfe = sum(
                x["mfe_pct"] for x in values
            ) / len(values)

            avg_mae = sum(
                x["mae_pct"] for x in values
            ) / len(values)

            print(
                f"  {horizon:>2}m "
                f"N={len(values)} "
                f"FAV={favorable} "
                f"ADV={adverse} "
                f"NEU={neutral} "
                f"AVG_RET={avg_ret:+.3f}% "
                f"AVG_MFE={avg_mfe:+.3f}% "
                f"AVG_MAE={avg_mae:+.3f}%"
            )

    # ================================================================
    # SUMMARY BY DIRECTION
    # ================================================================
    print("\nV13.9.1 DIRECTIONAL VALIDATION")

    for direction in ("LONG", "SHORT"):
        group = [
            event for event in events
            if event["direction"] == direction
        ]

        if not group:
            continue

        print(
            f"\n{direction} N={len(group)}"
        )

        for horizon in (15, 30, 60):
            values = [
                event["horizons"][horizon]
                for event in group
                if horizon in event["horizons"]
            ]

            if not values:
                continue

            favorable = sum(
                x["outcome"] == "FAVORABLE"
                for x in values
            )

            adverse = sum(
                x["outcome"] == "ADVERSE"
                for x in values
            )

            neutral = sum(
                x["outcome"] == "NEUTRAL"
                for x in values
            )

            avg_ret = sum(
                x["return_pct"] for x in values
            ) / len(values)

            print(
                f"  {horizon:>2}m "
                f"N={len(values)} "
                f"FAV={favorable} "
                f"ADV={adverse} "
                f"NEU={neutral} "
                f"AVG_RET={avg_ret:+.3f}%"
            )

    print(
        f"\nTOTAL V13.9.1 SEQUENCE EVENTS = {len(events)}"
    )
    print("=" * 90)

    return events



# ============================================================
# V13.10 — EXIT vs HOLD AT TRAJECTORY STATE
# ============================================================
#
# RESEARCH ONLY.
# Does NOT modify the trading engine.
#
# Question:
# After an OPPOSITE transition is detected and the post-transition
# trajectory is classified, would EXIT or HOLD have produced the
# better outcome?
#
# States examined:
#   RECOVERY
#   STABILIZING
#   CONTINUED_FAILURE
#
# Horizons:
#   +15m
#   +30m
#   +45m
#   +60m
#
# Decision:
#   EXIT = return stops at the decision point
#   HOLD = remain in original trade direction and measure
#          subsequent directional return
#
# ============================================================

from collections import defaultdict


def _v1310_directional_return(direction, entry_price, price):
    if entry_price is None or price is None or entry_price == 0:
        return None

    raw = (price - entry_price) / entry_price * 100.0

    if direction == "SHORT":
        raw = -raw

    return raw


def _v1310_price_at_or_after(rows, target_time):
    """
    Return the first 5m close at or after target_time.
    Candle timestamps represent candle start, so close is +5m.
    """
    best = None

    for row in rows:
        close_time = row.timestamp + timedelta(minutes=5)

        if close_time < target_time:
            continue

        price = price_from_row(row)

        if price is None or price == 0:
            continue

        best = (close_time, price)
        break

    return best


def _v1310_build_cases(events):
    """
    Build V13.10 decision cases directly from the actual V13.9.1
    trajectory-event dictionaries.

    V13.9.1 already performed the causal trajectory analysis.
    V13.10 must NOT rebuild or reinterpret that analysis.

    Each event contains:
        symbol
        direction
        candidate_minutes
        completion_minutes
        sequence
        sequence_length
        horizons

    The first complete trajectory event is the decision case.
    """

    cases = []

    for event in events:
        if not isinstance(event, dict):
            continue

        symbol = event.get("symbol")
        direction = event.get("direction")
        sequence = event.get("sequence")
        candidate_minutes = event.get("candidate_minutes")
        completion_minutes = event.get("completion_minutes")
        horizons = event.get("horizons")

        if direction not in ("LONG", "SHORT"):
            continue

        if not symbol or not sequence:
            continue

        if not isinstance(horizons, dict) or not horizons:
            continue

        # ------------------------------------------------------------
        # Determine the trajectory state represented by the sequence.
        # We use the actual V13.9.1 sequence, without inventing
        # another classifier.
        # ------------------------------------------------------------
        states = [
            "RECOVERY",
            "STABILIZING",
            "CONTINUED_FAILURE",
        ]

        sequence_states = [
            state
            for state in states
            if state in sequence
        ]

        if not sequence_states:
            continue

        # The final recognized state is the state at completion.
        state = sequence_states[-1]

        cases.append({
            "symbol": symbol,
            "direction": direction,
            "candidate_minutes": candidate_minutes,
            "completion_minutes": completion_minutes,
            "completion_time": event.get("completion_time"),
            "sequence": sequence,
            "sequence_length": event.get("sequence_length"),
            "state": state,
            "horizons": horizons,
            "event": event,
        })

    return cases

def run_v1310_exit_vs_hold_validation(paths):

    print()
    print("=" * 78)
    print("V13.10 — EXIT vs HOLD AT TRAJECTORY STATE")
    print("=" * 78)
    print()
    print("RESEARCH ONLY — NO ENGINE CHANGES")
    print()

    cases = _v1310_build_cases(paths)

    print(f"TRAJECTORY DECISION CASES: {len(cases)}")
    print()

    if not cases:
        print("NO VALID V13.10 CASES FOUND.")
        print()
        print("V13.10 STOPPED — no production code changed.")
        return

    horizons = (15, 30, 45, 60)

    # --------------------------------------------------------
    # Results:
    # state -> direction -> horizon
    # --------------------------------------------------------
    stats = defaultdict(list)

    detailed = []

    for case in cases:

        symbol = case["symbol"]
        direction = case["direction"]
        state = case["state"]
        completion_time = case["completion_time"]

        rows5 = v128.v125.base.load_rows(symbol, "5m")

        decision = _v1310_price_at_or_after(
            rows5,
            completion_time,
        )

        if decision is None:
            continue

        decision_time, decision_price = decision

        case_record = {
            "symbol": symbol,
            "direction": direction,
            "state": state,
            "decision_time": decision_time,
            "decision_price": decision_price,
            "completion_time": completion_time,
            "candidate_minutes": case["candidate_minutes"],
            "completion_minutes": case["completion_minutes"],
            "sequence": case["sequence"],
            "horizons": {},
        }

        for horizon in horizons:

            target_time = decision_time + timedelta(minutes=horizon)

            future = _v1310_price_at_or_after(
                rows5,
                target_time,
            )

            if future is None:
                continue

            future_time, future_price = future

            hold_return = _v1310_directional_return(
                direction,
                decision_price,
                future_price,
            )

            if hold_return is None:
                continue

            # EXIT at the decision point means:
            # after exiting, the original trade has zero further
            # exposure. Therefore subsequent incremental return
            # is 0.0%.
            exit_return = 0.0

            advantage = exit_return - hold_return

            outcome = (
                "EXIT_BETTER"
                if advantage > 0.10
                else
                "HOLD_BETTER"
                if advantage < -0.10
                else
                "TIE"
            )

            record = {
                "hold_return": hold_return,
                "exit_return": exit_return,
                "exit_advantage": advantage,
                "outcome": outcome,
            }

            case_record["horizons"][horizon] = record

            stats[(state, direction, horizon)].append(
                record
            )

        detailed.append(case_record)

    # --------------------------------------------------------
    # MAIN SUMMARY
    # --------------------------------------------------------

    print("-" * 78)
    print("STATE × DIRECTION × HORIZON")
    print("-" * 78)

    for state in (
        "RECOVERY",
        "STABILIZING",
        "CONTINUED_FAILURE",
    ):

        for direction in ("LONG", "SHORT"):

            found_any = False

            for horizon in horizons:

                rows = stats.get(
                    (state, direction, horizon),
                    [],
                )

                if not rows:
                    continue

                found_any = True

                avg_hold = (
                    sum(x["hold_return"] for x in rows)
                    / len(rows)
                )

                exit_better = sum(
                    1
                    for x in rows
                    if x["outcome"] == "EXIT_BETTER"
                )

                hold_better = sum(
                    1
                    for x in rows
                    if x["outcome"] == "HOLD_BETTER"
                )

                ties = len(rows) - exit_better - hold_better

                print(
                    f"{state:18s} "
                    f"{direction:5s} "
                    f"+{horizon:02d}m "
                    f"N={len(rows):2d} "
                    f"HOLD={avg_hold:+.3f}% "
                    f"EXIT={exit_better:2d} "
                    f"HOLD_WIN={hold_better:2d} "
                    f"TIE={ties:2d}"
                )

            if found_any:
                print()

    # --------------------------------------------------------
    # STATE-ONLY SUMMARY
    # --------------------------------------------------------

    print()
    print("-" * 78)
    print("STATE-ONLY DECISION VALUE")
    print("-" * 78)

    for state in (
        "RECOVERY",
        "STABILIZING",
        "CONTINUED_FAILURE",
    ):

        for horizon in horizons:

            rows = []

            for direction in ("LONG", "SHORT"):
                rows.extend(
                    stats.get(
                        (state, direction, horizon),
                        [],
                    )
                )

            if not rows:
                continue

            avg_hold = (
                sum(x["hold_return"] for x in rows)
                / len(rows)
            )

            exit_better = sum(
                x["outcome"] == "EXIT_BETTER"
                for x in rows
            )

            hold_better = sum(
                x["outcome"] == "HOLD_BETTER"
                for x in rows
            )

            ties = len(rows) - exit_better - hold_better

            exit_rate = (
                exit_better / len(rows) * 100.0
            )

            hold_rate = (
                hold_better / len(rows) * 100.0
            )

            print(
                f"{state:18s} "
                f"+{horizon:02d}m "
                f"N={len(rows):2d} "
                f"AVG_HOLD={avg_hold:+.3f}% "
                f"EXIT_BETTER={exit_better:2d}"
                f"({exit_rate:4.1f}%) "
                f"HOLD_BETTER={hold_better:2d}"
                f"({hold_rate:4.1f}%) "
                f"TIE={ties:2d}"
            )

        print()

    # --------------------------------------------------------
    # DIRECTION SUMMARY
    # --------------------------------------------------------

    print()
    print("-" * 78)
    print("DIRECTION SUMMARY")
    print("-" * 78)

    for direction in ("LONG", "SHORT"):

        for horizon in horizons:

            rows = []

            for state in (
                "RECOVERY",
                "STABILIZING",
                "CONTINUED_FAILURE",
            ):
                rows.extend(
                    stats.get(
                        (state, direction, horizon),
                        [],
                    )
                )

            if not rows:
                continue

            avg_hold = (
                sum(x["hold_return"] for x in rows)
                / len(rows)
            )

            exit_better = sum(
                x["outcome"] == "EXIT_BETTER"
                for x in rows
            )

            hold_better = sum(
                x["outcome"] == "HOLD_BETTER"
                for x in rows
            )

            print(
                f"{direction:5s} "
                f"+{horizon:02d}m "
                f"N={len(rows):2d} "
                f"AVG_HOLD={avg_hold:+.3f}% "
                f"EXIT_BETTER={exit_better:2d} "
                f"HOLD_BETTER={hold_better:2d}"
            )

        print()

    # --------------------------------------------------------
    # INDIVIDUAL CASES
    # --------------------------------------------------------

    print()
    print("-" * 78)
    print("INDIVIDUAL DECISION CASES")
    print("-" * 78)

    for case in detailed:

        available = case["horizons"]

        if not available:
            continue

        print(
            f"{case['symbol']:5s} "
            f"{case['direction']:5s} "
            f"{case['state']:18s} "
            f"{case['decision_time']}"
        )

        for horizon in horizons:

            result = available.get(horizon)

            if result is None:
                continue

            print(
                f"    +{horizon:02d}m "
                f"HOLD={result['hold_return']:+.3f}% "
                f"{result['outcome']}"
            )

    # --------------------------------------------------------
    # RESEARCH CONCLUSION
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("V13.10 RESEARCH INTERPRETATION")
    print("=" * 78)
    print()
    print(
        "The purpose is NOT to declare an EXIT rule."
    )
    print(
        "The purpose is to determine whether post-transition"
    )
    print(
        "trajectory state contains useful information about"
    )
    print(
        "whether the original trade should be preserved."
    )
    print()
    print(
        "Important:"
    )
    print(
        "  RECOVERY should generally favor HOLD."
    )
    print(
        "  CONTINUED_FAILURE should increasingly favor EXIT."
    )
    print(
        "  STABILIZING is the difficult middle state."
    )
    print()
    print(
        "No production engine changes were made."
    )
    print("=" * 78)
    print()


# ============================================================
# V13.10 ENTRYPOINT
# ============================================================

# V13.10 is launched by the original entrypoint above.
# No second __main__ block is required here.

# ============================================================
# V13.14 — SEQUENCE INFORMATION GAIN AUDIT
# RESEARCH ONLY — NO ORDERS — NO PRODUCTION ENGINE CHANGES
#
# Question:
# Does the complete chronological state history contain
# predictive information that the current/final state alone
# does not contain?
#
# Method:
# At each checkpoint, identify:
#   1. CURRENT STATE = latest state at that checkpoint
#   2. CHRONOLOGICAL SEQUENCE = all state changes up to that
#      checkpoint, with consecutive duplicates compressed
#
# Then compare future returns from that checkpoint:
#   +15m, +30m, +45m, +60m
#
# The critical comparison is WITHIN THE SAME CURRENT STATE.
# ============================================================

def run_v1314_sequence_information_gain_audit(all_paths):
    meaningful = {
        "NEUTRAL",
        "RECOVERING",
        "DETERIORATING",
        "PERSISTENT_FAILURE",
    }

    checkpoints = (10, 15, 20, 25, 30, 45, 60)
    future_horizons = (15, 30, 45, 60)

    print()
    print("=" * 110)
    print("V13.14 — SEQUENCE INFORMATION GAIN AUDIT")
    print("RESEARCH ONLY — CURRENT STATE VS COMPLETE CHRONOLOGICAL HISTORY")
    print("=" * 110)

    # --------------------------------------------------------
    # Cache 5m rows by symbol so repeated paths do not reload.
    # --------------------------------------------------------
    rows_cache = {}

    def get_rows(symbol):
        if symbol not in rows_cache:
            rows_cache[symbol] = v128.v125.base.load_rows(symbol, "5m")
        return rows_cache[symbol]

    def checkpoint_index(rows, start_index, minutes):
        target_time = (
            val(rows[start_index], "timestamp", "time", "datetime", "date")
            + timedelta(minutes=minutes)
        )
        return close_index(rows, target_time)

    def future_return(path, checkpoint_minutes, horizon_minutes):

        """

        Calculate signed future return directly from StatePoint.return_pct.


        StatePoint.return_pct is measured from the original opposite-transition

        price. We reconstruct the price ratio between the checkpoint and the

        future target without reloading market rows.


        This avoids the broken row-loading path that previously caused every

        future-return observation to be discarded.

        """

        checkpoint = next(

            (p for p in path.points if p.minutes == checkpoint_minutes),

            None,

        )

        if checkpoint is None:

            return None


        target_minutes = checkpoint_minutes + horizon_minutes

        target = next(

            (p for p in path.points if p.minutes == target_minutes),

            None,

        )

        if target is None:

            return None


        try:

            checkpoint_return = float(checkpoint.return_pct) / 100.0

            target_return = float(target.return_pct) / 100.0

        except (TypeError, ValueError):

            return None


        if path.direction == "SHORT":

            # For SHORT:

            # return_pct = -(P - P0) / P0 * 100

            # therefore P / P0 = 1 - return_pct / 100.

            checkpoint_ratio = 1.0 - checkpoint_return

            target_ratio = 1.0 - target_return


            if checkpoint_ratio == 0.0:

                return None


            return -(target_ratio / checkpoint_ratio - 1.0) * 100.0


        # For LONG:

        # return_pct = (P - P0) / P0 * 100

        # therefore P / P0 = 1 + return_pct / 100.

        checkpoint_ratio = 1.0 + checkpoint_return

        target_ratio = 1.0 + target_return


        if checkpoint_ratio == 0.0:

            return None


        return (target_ratio / checkpoint_ratio - 1.0) * 100.0



    def sequence_to_checkpoint(path, checkpoint):
        sequence_points = []
        last_state = None

        for point in path.points:
            if point.minutes > checkpoint:
                continue

            if point.state not in meaningful:
                continue

            if point.state != last_state:
                sequence_points.append(
                    (point.state, point.minutes)
                )
                last_state = point.state

        return sequence_points

    def sequence_text(sequence_points):
        if not sequence_points:
            return "NONE"

        return " -> ".join(
            state for state, _minutes in sequence_points
        )

    # --------------------------------------------------------
    # Build observations.
    #
    # Each observation is one path at one checkpoint.
    # Future returns are measured FROM THAT CHECKPOINT,
    # not from the original opposite-detection point.
    # --------------------------------------------------------
    observations = []

    for path in all_paths:
        rows = get_rows(path.symbol)

        start_index = close_index(
            rows,
            path.opposite_time,
        )

        if start_index is None:
            continue

        for checkpoint in checkpoints:
            point = next(
                (
                    p
                    for p in path.points
                    if p.minutes == checkpoint
                ),
                None,
            )

            if point is None:
                continue

            sequence_points = sequence_to_checkpoint(
                path,
                checkpoint,
            )

            if not sequence_points:
                continue

            current_state = sequence_points[-1][0]

            checkpoint_idx = checkpoint_index(
                rows,
                start_index,
                checkpoint,
            )

            if checkpoint_idx is None:
                continue

            future_returns = {}

            for horizon in future_horizons:
                value = future_return(
                    path,
                    checkpoint,
                    horizon,
                )

                if value is not None:
                    future_returns[horizon] = value

            if not future_returns:
                continue

            observations.append(
                {
                    "symbol": path.symbol,
                    "direction": path.direction,
                    "checkpoint": checkpoint,
                    "current_state": current_state,
                    "sequence": tuple(
                        state
                        for state, _minutes in sequence_points
                    ),
                    "sequence_text": sequence_text(
                        sequence_points
                    ),
                    "returns": future_returns,
                }
            )

    print()
    print(f"TOTAL OBSERVATIONS : {len(observations)}")

    # --------------------------------------------------------
    # Helper statistics.
    # --------------------------------------------------------
    def stats(values):
        if not values:
            return {
                "n": 0,
                "avg": None,
                "fav": 0,
                "adv": 0,
                "neutral": 0,
            }

        return {
            "n": len(values),
            "avg": sum(values) / len(values),
            "fav": sum(1 for x in values if x > 0),
            "adv": sum(1 for x in values if x < 0),
            "neutral": sum(1 for x in values if x == 0),
        }

    # --------------------------------------------------------
    # Main audit.
    #
    # Baseline = current state alone.
    # Sequence = exact chronological sequence.
    #
    # We first show all state groups, then exact sequence
    # groups nested inside each current state.
    # --------------------------------------------------------
    for checkpoint in checkpoints:
        checkpoint_obs = [
            x
            for x in observations
            if x["checkpoint"] == checkpoint
        ]

        if not checkpoint_obs:
            continue

        print()
        print("=" * 110)
        print(
            f"CHECKPOINT +{checkpoint}M"
        )
        print("=" * 110)

        states = sorted(
            set(x["current_state"] for x in checkpoint_obs)
        )

        for state in states:
            state_obs = [
                x
                for x in checkpoint_obs
                if x["current_state"] == state
            ]

            print()
            print(
                f"CURRENT STATE = {state}"
                f"   N={len(state_obs)}"
            )
            print("-" * 110)

            for horizon in future_horizons:
                values = [
                    x["returns"][horizon]
                    for x in state_obs
                    if horizon in x["returns"]
                ]

                s = stats(values)

                if s["n"]:
                    print(
                        f"  NEXT +{horizon:2d}M  "
                        f"N={s['n']:2d}  "
                        f"AVG={s['avg']:+.3f}%  "
                        f"FAV={s['fav']:2d}  "
                        f"ADV={s['adv']:2d}"
                    )

            # ----------------------------------------------
            # Exact chronological sequences within this
            # current state.
            # ----------------------------------------------
            sequence_groups = {}

            for item in state_obs:
                key = item["sequence"]
                sequence_groups.setdefault(key, []).append(item)

            print()
            print("  CHRONOLOGICAL SEQUENCES WITHIN CURRENT STATE")
            print("  " + "-" * 90)

            for sequence, group in sorted(
                sequence_groups.items(),
                key=lambda item: (
                    -len(item[1]),
                    item[0],
                ),
            ):
                repeated = len(group) >= 2

                print(
                    f"  N={len(group):2d}"
                    f"  {'REPEATED' if repeated else 'SINGLE '}"
                    f"  {sequence_text([(s, 0) for s in sequence])}"
                )

                for horizon in future_horizons:
                    values = [
                        x["returns"][horizon]
                        for x in group
                        if horizon in x["returns"]
                    ]

                    s = stats(values)

                    if not s["n"]:
                        continue

                    print(
                        f"       +{horizon:2d}M:"
                        f" N={s['n']:2d}"
                        f" AVG={s['avg']:+.3f}%"
                        f" FAV={s['fav']:2d}"
                        f" ADV={s['adv']:2d}"
                    )

            # ----------------------------------------------
            # Information-gain-style comparison.
            #
            # Only repeated exact sequences are used here.
            # This prevents a sequence occurring once from
            # pretending to provide validated predictive power.
            # ----------------------------------------------
            repeated_items = [
                x
                for x in state_obs
                if len(sequence_groups[x["sequence"]]) >= 2
            ]

            repeated_sequences = {
                x["sequence"]
                for x in repeated_items
            }

            print()
            print("  REPEATED-SEQUENCE INFORMATION TEST")
            print(
                f"  repeated sequence groups : "
                f"{len(repeated_sequences)}"
            )
            print(
                f"  observations in repeated "
                f"sequences                 : "
                f"{len(repeated_items)}"
            )

            if not repeated_items:
                print(
                    "  RESULT: insufficient repeated-sequence "
                    "data for this current state."
                )
                continue

            for horizon in future_horizons:
                state_values = [
                    x["returns"][horizon]
                    for x in state_obs
                    if horizon in x["returns"]
                ]

                repeated_values = [
                    x["returns"][horizon]
                    for x in repeated_items
                    if horizon in x["returns"]
                ]

                if not state_values or not repeated_values:
                    continue

                state_avg = (
                    sum(state_values) / len(state_values)
                )
                repeated_avg = (
                    sum(repeated_values)
                    / len(repeated_values)
                )

                print(
                    f"  +{horizon:2d}M:"
                    f" STATE_AVG={state_avg:+.3f}%"
                    f" REPEATED_SEQUENCE_AVG="
                    f"{repeated_avg:+.3f}%"
                    f" DELTA="
                    f"{repeated_avg - state_avg:+.3f}%"
                )

    print()
    print("=" * 110)
    print("V13.14 INTERPRETATION RULE")
    print("=" * 110)
    print(
        "A chronological sequence is NOT considered predictive "
        "merely because its average differs from another state."
    )
    print(
        "The critical evidence is different outcomes among "
        "different histories that arrive at the SAME current state."
    )
    print(
        "Exact sequences occurring only once are displayed for "
        "research context but are NOT treated as validated evidence."
    )
    print(
        "NO AI MODEL TRAINED."
    )
    print(
        "NO PRODUCTION CODE CHANGED."
    )
    print("=" * 110)



# V13.15 — SEQUENCE MOTIF INFORMATION AUDIT
# RESEARCH ONLY - NO ORDERS - NO PRODUCTION ENGINE CHANGES
#
# QUESTION:
# When CURRENT STATE is the same, does a reusable chronological
# sequence motif contain information about subsequent price behavior
# that CURRENT STATE alone does not contain?
#
# Unlike V13.14, this audit does NOT require the entire sequence to
# repeat exactly. It tests reusable chronological motifs.
#
# Examples:
#   DETERIORATING -> RECOVERING
#   DETERIORATING -> RECOVERING -> DETERIORATING
#   RECOVERING -> NEUTRAL -> DETERIORATING
#   RECOVERY AFTER DETERIORATION
#   RETURN TO DETERIORATION
#   PERSISTENT_FAILURE HISTORY
#
# IMPORTANT:
#   - Research only.
#   - No trading decisions.
#   - No production KISS changes.
#   - No AI model training.
#   - Future returns are measured from the checkpoint price.

def run_v1316_deduplicated_motif_audit(all_paths):
    print()
    print("=" * 110)
    print("V13.16 — DEDUPLICATED SEQUENCE MOTIF AUDIT")
    print("=" * 110)
    print("QUESTION: Does chronological motif history add information beyond CURRENT STATE?")
    print("RESEARCH ONLY — NO ORDERS — NO PRODUCTION ENGINE CHANGES")
    print()

    meaningful = {
        "NEUTRAL",
        "RECOVERING",
        "DETERIORATING",
        "PERSISTENT_FAILURE",
    }

    checkpoints = (10, 15, 20, 25, 30, 45, 60)
    horizons = (15, 30, 45, 60)

    def future_return(path, checkpoint_minutes, horizon_minutes):
        """
        Calculate signed future return from StatePoint.return_pct.

        return_pct is measured from the original opposite-transition price.
        Reconstruct the price ratio between the checkpoint and future target.
        """
        checkpoint = next(
            (p for p in path.points if p.minutes == checkpoint_minutes),
            None,
        )
        if checkpoint is None:
            return None

        target_minutes = checkpoint_minutes + horizon_minutes
        target = next(
            (p for p in path.points if p.minutes == target_minutes),
            None,
        )
        if target is None:
            return None

        try:
            checkpoint_return = float(checkpoint.return_pct) / 100.0
            target_return = float(target.return_pct) / 100.0
        except (TypeError, ValueError):
            return None

        if path.direction == "SHORT":
            checkpoint_ratio = 1.0 - checkpoint_return
            target_ratio = 1.0 - target_return
            if checkpoint_ratio == 0.0:
                return None
            return -(target_ratio / checkpoint_ratio - 1.0) * 100.0

        checkpoint_ratio = 1.0 + checkpoint_return
        target_ratio = 1.0 + target_return
        if checkpoint_ratio == 0.0:
            return None
        return (target_ratio / checkpoint_ratio - 1.0) * 100.0

    # Reusable chronological motifs.
    #
    # A motif is considered present if these states occur in this
    # chronological order within the history available at the checkpoint.
    #
    # Consecutive duplicate states are compressed, but re-entry into
    # a state remains visible.
    # Canonical motifs only.
    #
    # V13.15 contained two duplicate aliases:
    #   RECOVERY AFTER DETERIORATION
    #       == DETERIORATING -> RECOVERING
    #
    #   RETURN TO DETERIORATION
    #       == DETERIORATING -> RECOVERING -> DETERIORATING
    #
    # V13.16 removes those aliases so the same underlying trajectory
    # cannot be counted twice merely because it had two names.
    motifs = {
        "DETERIORATING -> RECOVERING": (
            "DETERIORATING",
            "RECOVERING",
        ),
        "DETERIORATING -> RECOVERING -> DETERIORATING": (
            "DETERIORATING",
            "RECOVERING",
            "DETERIORATING",
        ),
        "RECOVERING -> NEUTRAL -> DETERIORATING": (
            "RECOVERING",
            "NEUTRAL",
            "DETERIORATING",
        ),
        "PERSISTENT_FAILURE HISTORY": (
            "PERSISTENT_FAILURE",
        ),
    }

    def compressed_history(path, minutes):
        states = []
        last_state = None

        for point in path.points:
            if point.minutes > minutes:
                break

            if point.state not in meaningful:
                continue

            if point.state != last_state:
                states.append(point.state)
                last_state = point.state

        return tuple(states)

    def contains_motif(history, motif):
        if not motif:
            return False

        n = len(motif)

        if n == 1:
            return motif[0] in history

        for i in range(len(history) - n + 1):
            if history[i:i + n] == motif:
                return True

        return False

    def current_state(path, minutes):
        state = None

        for point in path.points:
            if point.minutes > minutes:
                break

            if point.state in meaningful:
                state = point.state

        return state

    def checkpoint_price(path, minutes):
        candidates = [
            point
            for point in path.points
            if point.minutes == minutes
        ]

        if candidates:
            point = candidates[-1]
            return point.return_pct, point

        return None, None

    # Cache rows once per symbol/date/direction where possible.
    #
    # The existing StatePoint data already provides the trajectory.
    # For future-return measurement we attempt to use the existing
    # project helpers. If they are unavailable for a particular path,
    # that observation is skipped rather than fabricated.
    observations = []

    for path in all_paths:
        for minutes in checkpoints:
            state = current_state(path, minutes)

            if state is None:
                continue

            history = compressed_history(path, minutes)

            for motif_name, motif in motifs.items():
                present = contains_motif(history, motif)

                if not present:
                    continue

                observations.append(
                    {
                        "symbol": path.symbol,
                        "direction": path.direction,
                        "opposite_time": path.opposite_time,
                        "checkpoint": minutes,
                        "current_state": state,
                        "history": history,
                        "motif": motif_name,
                    }
                )

    print(f"TOTAL MOTIF OBSERVATIONS : {len(observations)}")

    # A trajectory case is one underlying path:
    # symbol + direction + opposite-transition timestamp.
    #
    # Checkpoints are NOT treated as independent cases. This count is
    # reported separately so repeated checkpoints from the same path
    # cannot be mistaken for additional trajectories.
    unique_cases = {
        (
            obs["symbol"],
            obs["direction"],
            obs["opposite_time"],
        )
        for obs in observations
    }

    unique_symbols = {
        obs["symbol"]
        for obs in observations
    }

    unique_long_cases = {
        (
            obs["symbol"],
            obs["direction"],
            obs["opposite_time"],
        )
        for obs in observations
        if obs["direction"] == "LONG"
    }

    unique_short_cases = {
        (
            obs["symbol"],
            obs["direction"],
            obs["opposite_time"],
        )
        for obs in observations
        if obs["direction"] == "SHORT"
    }

    print()
    print("V13.16 UNIQUE TRAJECTORY CASE AUDIT")
    print("-" * 110)
    print(f"UNIQUE TRAJECTORY CASES : {len(unique_cases)}")
    print(f"UNIQUE SYMBOLS          : {len(unique_symbols)}")
    print(f"UNIQUE LONG CASES       : {len(unique_long_cases)}")
    print(f"UNIQUE SHORT CASES      : {len(unique_short_cases)}")
    print("CHECKPOINT OBSERVATIONS ARE NOT TREATED AS INDEPENDENT CASES")
    print("-" * 110)

    print()

    def avg(values):
        return sum(values) / len(values) if values else None

    # The central comparison:
    #
    # For every motif, compare observations WITH the motif against
    # ALL observations having the SAME CURRENT STATE at the same
    # checkpoint. This prevents a motif result from simply reflecting
    # that it occurred more often in one state than another.
    #
    # Only observations for which the existing trajectory data can
    # support the requested future horizon are included.

    for checkpoint in checkpoints:
        print()
        print("=" * 110)
        print(f"CHECKPOINT +{checkpoint}m")
        print("=" * 110)

        checkpoint_obs = [
            obs
            for obs in observations
            if obs["checkpoint"] == checkpoint
        ]

        if not checkpoint_obs:
            print("NO MOTIF OBSERVATIONS")
            continue

        states = sorted(
            {
                obs["current_state"]
                for obs in checkpoint_obs
            }
        )

        for state in states:
            state_obs = [
                obs
                for obs in checkpoint_obs
                if obs["current_state"] == state
            ]

            print()
            print(f"CURRENT STATE = {state}")
            print(f"STATE OBSERVATIONS = {len(state_obs)}")
            print("-" * 110)

            for horizon in horizons:
                baseline_values = []

                for path in all_paths:
                    if current_state(path, checkpoint) != state:
                        continue

                    value = future_return(
                        path,
                        checkpoint,
                        horizon,
                    )

                    if value is not None:
                        baseline_values.append(value)

                if baseline_values:
                    print(
                        f"  +{horizon}m STATE BASELINE "
                        f"N={len(baseline_values)} "
                        f"AVG={avg(baseline_values):+.3f}%"
                    )
                else:
                    print(
                        f"  +{horizon}m STATE BASELINE N=0"
                    )

            print()
            print("  MOTIFS PRESENT WITHIN THIS CURRENT STATE")
            print("  " + "-" * 106)

            for motif_name in motifs:
                motif_obs = [
                    obs
                    for obs in state_obs
                    if obs["motif"] == motif_name
                ]

                if not motif_obs:
                    continue

                print()
                print(
                    f"  MOTIF: {motif_name}"
                )
                print(
                    f"  OBSERVATIONS: {len(motif_obs)}"
                )

                for horizon in horizons:
                    motif_values = []

                    for obs in motif_obs:
                        for path in all_paths:
                            if (
                                path.symbol != obs["symbol"]
                                or path.direction != obs["direction"]
                                or path.opposite_time != obs["opposite_time"]
                            ):
                                continue

                            value = future_return(
                                path,
                                checkpoint,
                                horizon,
                            )

                            if value is not None:
                                motif_values.append(value)

                            break

                    if not motif_values:
                        print(
                            f"    +{horizon}m "
                            f"N=0"
                        )
                        continue

                    motif_avg = avg(motif_values)

                    baseline_values = []

                    for path in all_paths:
                        if current_state(path, checkpoint) != state:
                            continue

                        value = future_return(
                            path,
                            checkpoint,
                            horizon,
                        )

                        if value is not None:
                            baseline_values.append(value)

                    baseline_avg = avg(baseline_values)

                    delta = (
                        motif_avg - baseline_avg
                        if baseline_avg is not None
                        else None
                    )

                    print(
                        f"    +{horizon}m "
                        f"MOTIF_N={len(motif_values)} "
                        f"MOTIF_AVG={motif_avg:+.3f}% "
                        f"STATE_N={len(baseline_values)} "
                        f"STATE_AVG="
                        f"{baseline_avg:+.3f}% "
                        f"DELTA="
                        f"{delta:+.3f}%"
                        if delta is not None
                        else
                        f"    +{horizon}m "
                        f"MOTIF_N={len(motif_values)} "
                        f"MOTIF_AVG={motif_avg:+.3f}% "
                        f"STATE_N={len(baseline_values)}"
                    )

    print()
    print("=" * 110)
    print("V13.16 MOTIF PRESENCE BY CURRENT STATE")
    print("=" * 110)

    for checkpoint in checkpoints:
        checkpoint_obs = [
            obs
            for obs in observations
            if obs["checkpoint"] == checkpoint
        ]

        if not checkpoint_obs:
            continue

        print()
        print(f"+{checkpoint}m")

        for state in sorted(
            {
                obs["current_state"]
                for obs in checkpoint_obs
            }
        ):
            state_obs = [
                obs
                for obs in checkpoint_obs
                if obs["current_state"] == state
            ]

            counts = {}

            for obs in state_obs:
                counts[obs["motif"]] = (
                    counts.get(obs["motif"], 0) + 1
                )

            print(
                f"  {state:22s} N={len(state_obs)}"
            )

            for motif_name, count in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            ):
                print(
                    f"    {count:3d}x {motif_name}"
                )

    print()
    print("=" * 110)
    print("V13.16 INTERPRETATION RULE")
    print("=" * 110)
    print(
        "A motif is interesting only when it repeatedly appears within "
        "the SAME CURRENT STATE and shows a persistent difference in "
        "subsequent returns versus the CURRENT-STATE baseline."
    )
    print(
        "A single observation, a single symbol, or a single horizon "
        "does NOT validate a motif."
    )
    print(
        "No motif from this audit becomes an entry, hold, warning, "
        "or exit rule."
    )
    print(
        "V13.16 is research only. NO PRODUCTION CODE CHANGED."
    )
    print("=" * 110)


# ============================================================
# V13.11 — STATE-SEQUENCE DECISION ANALYSIS
# ============================================================
# RESEARCH ONLY — NO PRODUCTION ENGINE CHANGES
#
# Question:
# Does the POST-TRANSITION TRAJECTORY SEQUENCE contain more
# decision information than the final trajectory state alone?
#
# V13.9.1 already produced the causal trajectory sequence.
# V13.11 does NOT rebuild or reinterpret that analysis.
#
# It compares the ACTUAL sequence against:
#   EXIT NOW
#   HOLD 15m
#   HOLD 30m
#   HOLD 45m
#   HOLD 60m
# ============================================================

def _v1311_sequence_category(sequence):
    """
    Normalize the actual V13.9.1 sequence into a readable
    sequence category without changing its meaning.
    """
    if not sequence:
        return None

    sequence = str(sequence).strip()

    if " -> " in sequence:
        return sequence

    return sequence


def _v1311_build_cases(events):
    """
    Build V13.11 cases directly from V13.9.1 trajectory events.

    IMPORTANT:
    The complete sequence is preserved.

    V13.11 does NOT reduce the sequence to the final state.
    """
    cases = []

    for event in events:
        if not isinstance(event, dict):
            continue

        symbol = event.get("symbol")
        direction = event.get("direction")
        sequence = event.get("sequence")
        candidate_minutes = event.get("candidate_minutes")
        completion_minutes = event.get("completion_minutes")
        completion_time = event.get("completion_time")
        horizons = event.get("horizons")

        if direction not in ("LONG", "SHORT"):
            continue

        if not symbol or not sequence:
            continue

        if completion_time is None:
            continue

        if not isinstance(horizons, dict) or not horizons:
            continue

        cases.append({
            "symbol": symbol,
            "direction": direction,
            "candidate_minutes": candidate_minutes,
            "completion_minutes": completion_minutes,
            "completion_time": completion_time,
            "sequence": _v1311_sequence_category(sequence),
            "sequence_length": event.get("sequence_length"),
            "horizons": horizons,
            "event": event,
        })

    return cases


def run_v1311_sequence_decision_validation(events):
    """
    V13.11 research:

    Compare EXIT NOW vs HOLD after the causal trajectory
    completion, grouped by the COMPLETE post-transition
    state sequence.

    No production trading logic is changed.
    """

    print()
    print("=" * 78)
    print("V13.11 — STATE-SEQUENCE DECISION ANALYSIS")
    print("=" * 78)
    print()
    print("RESEARCH ONLY — NO ENGINE CHANGES")
    print()

    cases = _v1311_build_cases(events)

    print(f"SEQUENCE DECISION CASES: {len(cases)}")
    print()

    if not cases:
        print("NO VALID V13.11 CASES FOUND.")
        print()
        print("V13.11 STOPPED — no production code changed.")
        return

    horizons = (15, 30, 45, 60)

    stats = defaultdict(list)

    for case in cases:

        symbol = case["symbol"]
        direction = case["direction"]
        sequence = case["sequence"]
        completion_time = case["completion_time"]

        rows5 = v128.v125.base.load_rows(symbol, "5m")

        decision = _v1310_price_at_or_after(
            rows5,
            completion_time,
        )

        if decision is None:
            continue

        decision_time, decision_price = decision

        print("-" * 78)
        print(
            f"{symbol} {direction} "
            f"{sequence} "
            f"{decision_time}"
        )

        for horizon in horizons:

            target_time = decision_time + timedelta(minutes=horizon)

            future = _v1310_price_at_or_after(
                rows5,
                target_time,
            )

            if future is None:
                continue

            future_time, future_price = future

            hold_return = _v1310_directional_return(
                direction,
                decision_price,
                future_price,
            )

            if hold_return > 0.10:
                outcome = "HOLD_BETTER"
            elif hold_return < -0.10:
                outcome = "EXIT_BETTER"
            else:
                outcome = "TIE"

            stats[(sequence, direction, horizon)].append(
                hold_return
            )

            print(
                f" +{horizon:02d}m "
                f"HOLD={hold_return:+.3f}% "
                f"{outcome}"
            )

    # --------------------------------------------------------
    # Sequence summary
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("V13.11 SEQUENCE SUMMARY")
    print("=" * 78)
    print()

    for key in sorted(stats.keys(), key=str):

        sequence, direction, horizon = key
        values = stats[key]

        if not values:
            continue

        avg_return = sum(values) / len(values)

        exit_better = sum(
            1 for value in values
            if value < -0.10
        )

        hold_better = sum(
            1 for value in values
            if value > 0.10
        )

        ties = len(values) - exit_better - hold_better

        print(
            f"{sequence} | "
            f"{direction} | "
            f"+{horizon:02d}m | "
            f"N={len(values)} | "
            f"AVG={avg_return:+.3f}% | "
            f"EXIT_BETTER={exit_better} | "
            f"HOLD_BETTER={hold_better} | "
            f"TIE={ties}"
        )

    # --------------------------------------------------------
    # Research interpretation
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("V13.11 RESEARCH INTERPRETATION")
    print("=" * 78)
    print()

    print(
        "The question is NOT which sequence should become"
    )
    print(
        "a trading rule."
    )
    print()
    print(
        "The question is whether the COMPLETE trajectory"
    )
    print(
        "sequence contains useful decision information that"
    )
    print(
        "would be lost by looking only at the final state."
    )
    print()
    print(
        "Examples:"
    )
    print(
        "  STABILIZING -> RECOVERY"
    )
    print(
        "  CONTINUED_FAILURE -> STABILIZING -> RECOVERY"
    )
    print(
        "  STABILIZING -> CONTINUED_FAILURE"
    )
    print()
    print(
        "V13.11 does not change production trading logic."
    )
    print("=" * 78)
    print()



# ============================================================
# V13.12 — classify_prefix() AUDIT
# ============================================================
# READ-ONLY DIAGNOSTIC
#
# Purpose:
#   Show exactly what classify_prefix() returns at every
#   candidate checkpoint for every trajectory path.
#
# IMPORTANT:
#   This does NOT change classify_prefix().
#   This does NOT change candidate selection.
#   This does NOT change trading logic.
#
# We are measuring why paths do or do not reach
# EXIT_CANDIDATE.
# ============================================================

def run_v1312_classify_prefix_audit(all_paths):
    CANDIDATES = (10, 15, 20, 25, 30, 45, 60)

    print()
    print("=" * 110)
    print("V13.12 — classify_prefix() AUDIT")
    print("READ-ONLY DIAGNOSTIC — NO RECOGNITION LOGIC CHANGED")
    print("=" * 110)

    total_paths = len(all_paths)
    candidate_found = 0
    no_candidate = 0

    candidate_counts = {
        minutes: 0
        for minutes in CANDIDATES
    }

    classification_counts = {}

    print()
    print("PER-PATH CLASSIFICATION")
    print("-" * 110)

    for path in all_paths:

        symbol = path.symbol
        direction = path.direction

        persistent_positions = [
            point.minutes
            for point in path.points
            if point.state == "PERSISTENT_FAILURE"
        ]

        results = []

        first_exit_candidate = None
        first_reversal_confirmed = None

        for minutes in CANDIDATES:

            classification = classify_prefix(
                path,
                minutes,
            )

            prefix = [
                point
                for point in path.points
                if point.minutes <= minutes
            ]

            prefix_states = [
                point.state
                for point in prefix
            ]

            persistent_count = prefix_states.count(
                "PERSISTENT_FAILURE"
            )

            final_state = (
                prefix_states[-1]
                if prefix_states
                else "NONE"
            )

            results.append(
                (
                    minutes,
                    classification,
                    persistent_count,
                    final_state,
                )
            )

            classification_counts[classification] = (
                classification_counts.get(classification, 0) + 1
            )

            if (
                classification == "EXIT_CANDIDATE"
                and first_exit_candidate is None
            ):
                first_exit_candidate = minutes

            if (
                classification == "REVERSAL_CONFIRMED"
                and first_reversal_confirmed is None
            ):
                first_reversal_confirmed = minutes

        if first_exit_candidate is not None:
            candidate_found += 1
            candidate_counts[first_exit_candidate] += 1
        else:
            no_candidate += 1

        print()
        print(
            f"{symbol:5s} {direction:5s} "
            f"points={len(path.points):2d} "
            f"PERSISTENT_FAILURE@"
            f"{persistent_positions if persistent_positions else 'NONE'}"
        )

        for minutes, classification, pf_count, final_state in results:
            print(
                f"  +{minutes:2d}m "
                f"{classification:20s} "
                f"PF={pf_count} "
                f"FINAL={final_state}"
            )

        if first_exit_candidate is not None:
            print(
                f"  FIRST EXIT_CANDIDATE = "
                f"+{first_exit_candidate}m"
            )
        else:
            print(
                "  FIRST EXIT_CANDIDATE = NONE"
            )

        if first_reversal_confirmed is not None:
            print(
                f"  FIRST REVERSAL_CONFIRMED = "
                f"+{first_reversal_confirmed}m"
            )

        print(
            "  RAW STATES = "
            + " -> ".join(
                f"+{point.minutes}m:{point.state}"
                for point in path.points
            )
        )

    print()
    print("=" * 110)
    print("V13.12 SUMMARY")
    print("=" * 110)

    print(f"total_paths       : {total_paths}")
    print(f"candidate_found   : {candidate_found}")
    print(f"no_candidate      : {no_candidate}")

    print()
    print("FIRST EXIT_CANDIDATE BY CHECKPOINT")
    print("-" * 110)

    for minutes in CANDIDATES:
        print(
            f"+{minutes:2d}m : "
            f"{candidate_counts[minutes]}"
        )

    print()
    print("ALL classify_prefix() RESULTS")
    print("-" * 110)

    for classification in sorted(classification_counts.keys()):
        print(
            f"{classification:20s} : "
            f"{classification_counts[classification]}"
        )

    print()
    print("=" * 110)
    print("V13.12 AUDIT COMPLETE")
    print("NO PRODUCTION CODE CHANGED")
    print("=" * 110)



# ============================================================
# V13.11 ENTRYPOINT
# ============================================================


# ============================================================
# V13.13 — ALL-TRAJECTORY SEQUENCE AUDIT
# READ-ONLY: inspect all StatePath trajectories before the
# classify_prefix() EXIT_CANDIDATE gate.
# NO PRODUCTION CODE CHANGED.
# ============================================================

def run_v1313_all_trajectory_sequence_audit(all_paths):
    meaningful = {
        "NEUTRAL",
        "RECOVERING",
        "DETERIORATING",
        "PERSISTENT_FAILURE",
    }

    print()
    print("=" * 110)
    print("V13.13 — ALL-TRAJECTORY SEQUENCE AUDIT")
    print("READ-ONLY — BYPASSES classify_prefix() CANDIDATE GATE")
    print("=" * 110)

    total_paths = len(all_paths)
    no_meaningful = 0
    one_state = 0
    multi_state = 0
    candidate_multi_state = 0
    noncandidate_multi_state = 0
    sequence_counts = {}

    for path in all_paths:
        # Preserve chronological state changes.
        # Consecutive duplicate states are compressed.
        # A state that reappears later is preserved.
        #
        # Example:
        # DETERIORATING -> RECOVERING -> DETERIORATING
        # remains exactly that sequence.
        sequence_points = []
        last_state = None

        for point in path.points:
            if point.state not in meaningful:
                continue

            if point.state != last_state:
                sequence_points.append(
                    (point.state, point.minutes)
                )
                last_state = point.state

        sequence = tuple(
            state for state, minutes in sequence_points
        )

        existing_candidate = None
        for minutes in (10, 15, 20, 25, 30, 45, 60):
            if classify_prefix(path, minutes) == "EXIT_CANDIDATE":
                existing_candidate = minutes
                break

        if not sequence:
            no_meaningful += 1
            category = "NO_MEANINGFUL_STATE"
        elif len(sequence) == 1:
            one_state += 1
            category = "ONE_MEANINGFUL_STATE"
        else:
            multi_state += 1
            sequence_counts[sequence] = sequence_counts.get(sequence, 0) + 1

            if existing_candidate is not None:
                candidate_multi_state += 1
                category = "MULTI_STATE + CANDIDATE"
            else:
                noncandidate_multi_state += 1
                category = "MULTI_STATE + NO_CANDIDATE"

        print()
        print(
            f"{path.symbol:5s} {path.direction:5s} "
            f"{category:28s} "
            f"EXISTING_CANDIDATE="
            f"{'+' + str(existing_candidate) + 'm' if existing_candidate is not None else 'NONE'}"
        )

        print(
            "  SEQUENCE = "
            + (
                " -> ".join(
                    f"{state}@+{minutes}m"
                    for state, minutes in sequence_points
                )
                if sequence_points
                else "NONE"
            )
        )

        print(
            "  RAW STATES = "
            + " -> ".join(
                f"+{point.minutes}m:{point.state}"
                for point in path.points
            )
        )

    print()
    print("=" * 110)
    print("V13.13 SUMMARY")
    print("=" * 110)
    print(f"total_paths                   : {total_paths}")
    print(f"no_meaningful_state           : {no_meaningful}")
    print(f"one_meaningful_state          : {one_state}")
    print(f"multi_state                   : {multi_state}")
    print(f"multi_state_with_candidate    : {candidate_multi_state}")
    print(f"multi_state_without_candidate : {noncandidate_multi_state}")

    print()
    print("UNIQUE MULTI-STATE SEQUENCES")
    print("-" * 110)

    if sequence_counts:
        for sequence, count in sorted(
            sequence_counts.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(f"{count:3d}x  " + " -> ".join(sequence))
    else:
        print("NONE")

    print()
    print("=" * 110)
    print("V13.13 AUDIT COMPLETE")
    print("NO PRODUCTION CODE CHANGED")
    print("=" * 110)


if __name__ == "__main__":
    result = main()

    if isinstance(result, tuple):
        all_paths, trajectory_events = result
    else:
        all_paths = result
        trajectory_events = None

    run_v1312_classify_prefix_audit(all_paths)
    run_v1313_all_trajectory_sequence_audit(all_paths)
    run_v1314_sequence_information_gain_audit(all_paths)
    run_v1316_deduplicated_motif_audit(all_paths)

    if trajectory_events is not None:
        run_v1311_sequence_decision_validation(
            trajectory_events
        )
    else:
        print()
        print("V13.11: trajectory events were not returned.")
        print("No production code changed.")
