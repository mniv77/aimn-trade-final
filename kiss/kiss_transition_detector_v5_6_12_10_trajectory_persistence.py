from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import kiss_transition_detector_v5_6_12_8_persistent_reversal as v128

SYMBOLS = ("NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ")
CHECKPOINTS = (5, 10, 15, 20, 25, 30, 45, 60)

from dataclasses import dataclass

@dataclass
class Point:
    minutes: int
    return_pct: float
    favorable_pct: float
    adverse_pct: float
    consecutive_adverse: int
    mae_pct: float
    mfe_pct: float
    move_pct: float
    acceleration_pct: float
    recovering: bool
    persistent: bool

from dataclasses import dataclass

@dataclass
class Point:
    minutes: int
    return_pct: float
    favorable_pct: float
    adverse_pct: float
    consecutive_adverse: int
    mae_pct: float
    mfe_pct: float
    move_pct: float
    acceleration_pct: float
    recovering: bool
    persistent: bool

def val(row, *names):
    for name in names:
        if isinstance(row, dict) and name in row:
            return row[name]
        if hasattr(row, name):
            return getattr(row, name)
    return None

def row_ts(row: Any):
    x = val(row, "timestamp", "time", "datetime", "date")
    return x

def row_close(row: Any):
    x = val(row, "close", "Close", "c")
    return float(x) if x is not None else None

def close_index(rows, target):
    for i, row in enumerate(rows):
        t = row_ts(row)
        if t is not None and t + __import__("datetime").timedelta(minutes=5) == target:
            return i
    return None

def signed_return(direction, start, end):
    if start is None or end is None or start == 0:
        return None
    r = (end / start - 1.0) * 100.0
    return r if direction == "LONG" else -r

def measure(rows, decision_idx, direction, minutes):
    step = minutes // 5
    target_idx = decision_idx + step

    if target_idx >= len(rows):
        return Point(
            minutes, None, None, None, 0,
            None, None, None, None, False, False
        )

    start = row_close(rows[decision_idx])
    end = row_close(rows[target_idx])
    ret = signed_return(direction, start, end)

    if ret is None:
        return Point(
            minutes, None, None, None, 0,
            None, None, None, None, False, False
        )

    moves = []
    for i in range(decision_idx + 1, target_idx + 1):
        a = row_close(rows[i - 1])
        b = row_close(rows[i])
        if a is not None and b is not None:
            moves.append(signed_return(direction, a, b))

    favorable = [x for x in moves if x > 0]
    adverse = [x for x in moves if x < 0]

    fav_pct = (
        len(favorable) / len(moves) * 100.0
        if moves else None
    )
    adv_pct = (
        len(adverse) / len(moves) * 100.0
        if moves else None
    )

    run = 0
    max_run = 0
    for x in moves:
        if x < 0:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0

    cumulative = []
    for i in range(decision_idx, target_idx + 1):
        p = row_close(rows[i])
        if p is not None:
            cumulative.append(
                signed_return(direction, start, p)
            )

    mae = min(cumulative) if cumulative else None
    mfe = max(cumulative) if cumulative else None

    recovering = (
        ret >= 0.10 and
        (fav_pct is not None and fav_pct >= 50.0)
    )

    persistent = (
        ret <= -0.50 and
        (
            max_run >= 3 or
            (adv_pct is not None and adv_pct >= 67.0)
        )
    )

    return Point(
        minutes,
        ret,
        fav_pct,
        adv_pct,
        max_run,
        mae,
        mfe,
        ret,
        None,
        recovering,
        persistent,
    )


def process_symbol(symbol):
    rows5 = v128.v125.base.load_rows(symbol, "5m")
    rows30 = v128.v125.base.load_rows(symbol, "30m")

    transitions = v128.v125.base.build_directional_transitions(
        symbol, rows30
    )
    observations = v128.v125.base.build_warning_observations(
        symbol, rows5
    )
    episodes = v128.v125.base.cluster_warning_episodes(observations)
    pairs = v128.v125.base.assign_one_episode_per_transition(
        transitions, episodes
    )

    cases = []

    for transition, episode in pairs:
        lead = (
            transition.timestamp - episode.first_timestamp
        ).total_seconds() / 60.0

        assignment = v128.v125.base.Assignment(
            transition, episode, lead
        )

        case = v128.evaluate_assignment(rows5, assignment)

        if case is None:
            continue

        if getattr(case, "opposite_time", None) is None:
            continue

        decision_idx = close_index(rows5, case.opposite_time)

        if decision_idx is None:
            continue

        points = []

        for minutes in CHECKPOINTS:
            p = measure(
                rows5,
                decision_idx,
                case.direction,
                minutes,
            )
            points.append(p)

        cases.append((case, points))

    print(
        f"{symbol}: transitions={len(transitions)} "
        f"assignments={len(pairs)} "
        f"trajectory_cases={len(cases)}"
    )

    for case, points in cases:
        print()
        print(
            f"{symbol} {case.direction} "
            f"opposite={case.opposite_time} "
            f"official={case.official_time} "
            f"lead={case.opposite_lead:.1f}m"
        )

        for p in points:
            if p.return_pct is None:
                continue

            print(
                f"  +{p.minutes:>2}m "
                f"ret={p.return_pct:+.3f}% "
                f"fav={p.favorable_pct:5.1f}% "
                f"adv={p.adverse_pct:5.1f}% "
                f"run={p.consecutive_adverse} "
                f"MAE={p.mae_pct:+.3f}% "
                f"MFE={p.mfe_pct:+.3f}% "
                f"recover={p.recovering} "
                f"persist={p.persistent}"
            )

    return cases


def main():
    print()
    print("=" * 72)
    print("KISS V5.6.12.10 — TRAJECTORY / PERSISTENCE")
    print("RESEARCH ONLY")
    print("NO ORDERS / NO DB WRITES / NO ENGINE CHANGES")
    print("=" * 72)

    all_cases = []

    for symbol in SYMBOLS:
        try:
            cases = process_symbol(symbol)
            all_cases.extend(cases)
        except Exception as exc:
            print(f"{symbol}: ERROR: {type(exc).__name__}: {exc}")

    print()
    print("=" * 72)
    print(f"TOTAL TRAJECTORY CASES: {len(all_cases)}")
    print("=" * 72)

    for minutes in CHECKPOINTS:
        points = []

        for case, trajectory in all_cases:
            for p in trajectory:
                if p.minutes == minutes and p.return_pct is not None:
                    points.append(p)

        if not points:
            print(f"+{minutes:>2}m: N=0")
            continue

        avg = sum(p.return_pct for p in points) / len(points)
        recovering = sum(p.recovering for p in points)
        persistent = sum(p.persistent for p in points)

        print(
            f"+{minutes:>2}m: "
            f"N={len(points):>3} "
            f"AVG={avg:+.3f}% "
            f"RECOVERY={recovering:>3} "
            f"PERSISTENT={persistent:>3}"
        )

    print()
    print("V5.6.12.10 COMPLETE")
    print("Research only. No engine changes made.")


if __name__ == "__main__":
    main()
