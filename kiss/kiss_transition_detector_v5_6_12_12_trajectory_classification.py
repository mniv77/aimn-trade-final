# V5.6.12.12 - Trajectory Classification
# RESEARCH ONLY - NO ORDERS - NO PRODUCTION ENGINE CHANGES
from __future__ import annotations

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

def first_state_time(path: StatePath, state: str) -> Optional[int]:
    for point in path.points:
        if point.state == state:
            return point.minutes
    return None

def path_return(path: StatePath, minutes: int) -> Optional[float]:
    for point in path.points:
        if point.minutes == minutes:
            return point.return_pct
    return None

if __name__ == "__main__":
    print("=" * 80)
    print("V5.6.12.12 - TRAJECTORY CLASSIFICATION")
    print("RESEARCH ONLY - NO ORDERS - NO PRODUCTION ENGINE CHANGES")
    print("=" * 80)

    symbols = ("NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ")
    all_paths = []
    classification_counts = {}

    for symbol in symbols:
        try:
            paths = process_symbol(symbol)
        except Exception as exc:
            print(f"{symbol}: ERROR {exc}")
            continue

        print()
        print(f"--- {symbol} ---")
        print(f"trajectory_cases={len(paths)}")

        for path in paths:
            classification = classify_path(path)
            all_paths.append((path, classification))
            classification_counts[classification] = classification_counts.get(classification, 0) + 1

            persistent_at = first_state_time(path, "PERSISTENT_FAILURE")
            deteriorating_at = first_state_time(path, "DETERIORATING")
            recovery_at = first_state_time(path, "RECOVERING")
            ret30 = path_return(path, 30)
            ret60 = path_return(path, 60)
            final_state = path.points[-1].state if path.points else "NEUTRAL"

            print(
                f"{path.direction:5s} " 
                f"opposite={path.opposite_time} " 
                f"class={classification:18s} " 
                f"final={final_state:18s} " 
                f"persist={persistent_at!s:>4} " 
                f"det={deteriorating_at!s:>4} " 
                f"rec={recovery_at!s:>4} " 
                f"+30={ret30 if ret30 is not None else 0.0:+.3f}% " 
                f"+60={ret60 if ret60 is not None else 0.0:+.3f}%"
            )

    print()
    print("=" * 80)
    print("CLASSIFICATION SUMMARY")
    print("=" * 80)

    total = len(all_paths)
    print(f"TOTAL TRAJECTORY CASES: {total}")

    for label in ("HOLD", "WARNING", "EXIT_CANDIDATE", "REVERSAL_CONFIRMED"):
        count = classification_counts.get(label, 0)
        pct = (count / total * 100.0) if total else 0.0
        print(f"{label:20s} N={count:3d} ({pct:5.1f}%)")

    print()
    print("=" * 80)
    print("RESEARCH INTERPRETATION")
    print("=" * 80)
    print("HOLD               = recovery/neutral behavior.")
    print("WARNING            = deterioration without confirmed reversal.")
    print("EXIT_CANDIDATE     = persistent failure appears, but recovery remains possible.")
    print("REVERSAL_CONFIRMED = persistent failure repeats and remains persistent.")
    print()
    print("These classifications are RESEARCH HYPOTHESES only.")
    print("They are NOT production trading rules and do NOT place orders.")
    print("=" * 80)
