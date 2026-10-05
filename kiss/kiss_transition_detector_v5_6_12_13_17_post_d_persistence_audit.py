"""
AIMn / KISS V13.17
POST-FIRST-DETERIORATION PERSISTENCE AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING
NO THRESHOLD PROMOTION

PURPOSE
-------
The previous post-D geometry audit showed:

    PF cases:
        often D -> negative return change -> continued deterioration

    NO_PF cases:
        can also have negative return changes first,
        followed by recovery

Therefore simple return-change direction is NOT sufficient.

This audit studies:

    1. First DETERIORATING checkpoint
    2. Return change to every later checkpoint
    3. Fixed-horizon cumulative change
    4. Positive / negative interval counts
    5. Longest consecutive negative run
    6. Longest consecutive positive run
    7. First positive reversal after D
    8. Whether that positive reversal persists
    9. First negative reversal after a positive run
   10. State at each reversal
   11. Comparison with eventual PF / NO_PF outcome

IMPORTANT
---------
All results are DESCRIPTIVE.

A +30 / +45 / +60 result uses future information relative to first D.
It is NOT a real-time trading rule.

The purpose is to discover whether trajectory persistence contains
information worth studying further.

"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple

from kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    StatePath,
    StatePoint,
    build_v1317_research_paths,
)


# ============================================================
# HELPERS
# ============================================================

def pct(x: Optional[float]) -> str:
    if x is None:
        return "NA"
    return f"{x:+.6f}"


def sign(x: float) -> str:
    if x > 0:
        return "+"
    if x < 0:
        return "-"
    return "0"


def first_d_index(points: List[StatePoint]) -> Optional[int]:
    for i, point in enumerate(points):
        if point.state == "DETERIORATING":
            return i
    return None


def eventual_outcome(path: StatePath) -> str:
    """
    Match the V13.17 trajectory outcome concept.

    If the +60 checkpoint is PF, classify as LATER_PF_BY_60.
    Otherwise classify as NO_PF_BY_60.
    """
    if not path.points:
        return "NO_DATA"

    last = path.points[-1]

    if last.state == "PERSISTENT_FAILURE":
        return "LATER_PF_BY_60"

    return "NO_PF_BY_60"


def later_points(
    points: List[StatePoint],
    d_index: int,
) -> List[StatePoint]:
    return points[d_index + 1:]


def return_delta(a: StatePoint, b: StatePoint) -> float:
    return b.return_pct - a.return_pct


def delta_sequence(
    points: List[StatePoint],
    d_index: int,
) -> List[Tuple[StatePoint, float, str]]:
    """
    Return:

        checkpoint
        dRETURN from previous checkpoint
        sign

    beginning immediately after first D.
    """

    result = []

    previous = points[d_index]

    for point in points[d_index + 1:]:
        delta = return_delta(previous, point)
        result.append((point, delta, sign(delta)))
        previous = point

    return result


def longest_run(
    signs: List[str],
    target: str,
) -> int:

    best = 0
    current = 0

    for value in signs:
        if value == target:
            current += 1
            best = max(best, current)
        else:
            current = 0

    return best


def first_run_start(
    deltas: List[Tuple[StatePoint, float, str]],
    target: str,
) -> Optional[int]:

    for i, (_, _, s) in enumerate(deltas):
        if s == target:
            return i

    return None


def fixed_horizon_change(
    points: List[StatePoint],
    d_index: int,
    target_minutes: int,
) -> Optional[float]:

    base = points[d_index]

    for point in points[d_index + 1:]:
        if point.minutes >= target_minutes:
            return point.return_pct - base.return_pct

    return None


def checkpoint_after(
    points: List[StatePoint],
    d_index: int,
    n: int,
) -> Optional[StatePoint]:

    idx = d_index + n

    if idx >= len(points):
        return None

    return points[idx]


# ============================================================
# CASE DETAIL
# ============================================================

def print_case_detail(
    number: int,
    path: StatePath,
) -> None:

    points = path.points
    outcome = eventual_outcome(path)

    d_idx = first_d_index(points)

    print()
    print("=" * 120)
    print(
        f"CASE #{number:02d}  "
        f"{path.symbol:<6} "
        f"{path.direction:<5} "
        f"{outcome}"
    )
    print(
        f"opposite_time={path.opposite_time} "
        f"official_time={path.official_time} "
        f"warning_lead={path.warning_lead}"
    )

    if d_idx is None:
        print("FIRST D = NONE")
        print("No post-D persistence analysis.")
        return

    first_d = points[d_idx]

    print(
        f"FIRST D = +{first_d.minutes}m "
        f"return={pct(first_d.return_pct)} "
        f"state={first_d.state}"
    )

    deltas = delta_sequence(points, d_idx)

    if not deltas:
        print("No checkpoints after first D.")
        return

    print()
    print(
        "MIN     STATE                    RETURN       "
        "dRETURN       SIGN"
    )

    print(
        f"{first_d.minutes:>3}     "
        f"{first_d.state:<24} "
        f"{pct(first_d.return_pct):>10}       --          --"
    )

    for point, delta, s in deltas:
        print(
            f"{point.minutes:>3}     "
            f"{point.state:<24} "
            f"{pct(point.return_pct):>10} "
            f"{pct(delta):>11}      {s}"
        )

    signs = [s for _, _, s in deltas]

    neg_run = longest_run(signs, "-")
    pos_run = longest_run(signs, "+")

    first_pos = first_run_start(deltas, "+")
    first_neg = first_run_start(deltas, "-")

    print()
    print("PERSISTENCE SUMMARY")
    print(f"  delta signs             = {' '.join(signs)}")
    print(f"  longest negative run    = {neg_run}")
    print(f"  longest positive run    = {pos_run}")

    if first_pos is None:
        print("  first positive reversal = NONE")
    else:
        p, d, _ = deltas[first_pos]
        print(
            f"  first positive reversal = +{p.minutes}m "
            f"dRETURN={pct(d)} "
            f"state={p.state}"
        )

    if first_neg is None:
        print("  first negative interval  = NONE")
    else:
        p, d, _ = deltas[first_neg]
        print(
            f"  first negative interval  = +{p.minutes}m "
            f"dRETURN={pct(d)} "
            f"state={p.state}"
        )

    print()
    print("FIXED-HORIZON CHANGE FROM FIRST D")

    for horizon in (30, 45, 60):

        value = fixed_horizon_change(
            points,
            d_idx,
            horizon,
        )

        if value is None:
            print(f"  +{horizon}m = N/A")
        else:
            print(
                f"  +{horizon}m = {pct(value)}"
            )


# ============================================================
# SUMMARY RECORD
# ============================================================

@dataclass
class PersistenceRecord:

    symbol: str
    direction: str
    outcome: str

    first_d_minutes: Optional[int]

    first_positive_minutes: Optional[int]
    first_negative_minutes: Optional[int]

    longest_negative_run: int
    longest_positive_run: int

    cumulative_30: Optional[float]
    cumulative_45: Optional[float]
    cumulative_60: Optional[float]

    positive_intervals: int
    negative_intervals: int

    positive_persist_1: bool
    positive_persist_2: bool
    positive_persist_3: bool

    negative_persist_1: bool
    negative_persist_2: bool
    negative_persist_3: bool


def build_record(path: StatePath) -> PersistenceRecord:

    points = path.points
    outcome = eventual_outcome(path)

    d_idx = first_d_index(points)

    if d_idx is None:

        return PersistenceRecord(
            symbol=path.symbol,
            direction=path.direction,
            outcome=outcome,
            first_d_minutes=None,
            first_positive_minutes=None,
            first_negative_minutes=None,
            longest_negative_run=0,
            longest_positive_run=0,
            cumulative_30=None,
            cumulative_45=None,
            cumulative_60=None,
            positive_intervals=0,
            negative_intervals=0,
            positive_persist_1=False,
            positive_persist_2=False,
            positive_persist_3=False,
            negative_persist_1=False,
            negative_persist_2=False,
            negative_persist_3=False,
        )

    deltas = delta_sequence(points, d_idx)
    signs = [s for _, _, s in deltas]

    first_positive_minutes = None
    first_negative_minutes = None

    for point, _, s in deltas:

        if s == "+" and first_positive_minutes is None:
            first_positive_minutes = point.minutes

        if s == "-" and first_negative_minutes is None:
            first_negative_minutes = point.minutes

    return PersistenceRecord(
        symbol=path.symbol,
        direction=path.direction,
        outcome=outcome,
        first_d_minutes=points[d_idx].minutes,

        first_positive_minutes=first_positive_minutes,
        first_negative_minutes=first_negative_minutes,

        longest_negative_run=longest_run(signs, "-"),
        longest_positive_run=longest_run(signs, "+"),

        cumulative_30=fixed_horizon_change(
            points, d_idx, 30
        ),
        cumulative_45=fixed_horizon_change(
            points, d_idx, 45
        ),
        cumulative_60=fixed_horizon_change(
            points, d_idx, 60
        ),

        positive_intervals=signs.count("+"),
        negative_intervals=signs.count("-"),

        positive_persist_1=(
            longest_run(signs, "+") >= 1
        ),
        positive_persist_2=(
            longest_run(signs, "+") >= 2
        ),
        positive_persist_3=(
            longest_run(signs, "+") >= 3
        ),

        negative_persist_1=(
            longest_run(signs, "-") >= 1
        ),
        negative_persist_2=(
            longest_run(signs, "-") >= 2
        ),
        negative_persist_3=(
            longest_run(signs, "-") >= 3
        ),
    )


# ============================================================
# GROUP SUMMARY
# ============================================================

def average(values: List[float]) -> Optional[float]:

    if not values:
        return None

    return sum(values) / len(values)


def summarize_group(
    records: List[PersistenceRecord],
    label: str,
) -> None:

    print()
    print("-" * 120)
    print(label)
    print("-" * 120)

    print(f"N = {len(records)}")

    if not records:
        return

    neg_runs = [
        r.longest_negative_run
        for r in records
    ]

    pos_runs = [
        r.longest_positive_run
        for r in records
    ]

    pos_counts = [
        r.positive_intervals
        for r in records
    ]

    neg_counts = [
        r.negative_intervals
        for r in records
    ]

    print(
        f"avg longest negative run = "
        f"{average(neg_runs):.3f}"
    )

    print(
        f"avg longest positive run = "
        f"{average(pos_runs):.3f}"
    )

    print(
        f"avg positive intervals    = "
        f"{average(pos_counts):.3f}"
    )

    print(
        f"avg negative intervals    = "
        f"{average(neg_counts):.3f}"
    )

    for name, attr in (
        ("positive persistence 1", "positive_persist_1"),
        ("positive persistence 2", "positive_persist_2"),
        ("positive persistence 3", "positive_persist_3"),
        ("negative persistence 1", "negative_persist_1"),
        ("negative persistence 2", "negative_persist_2"),
        ("negative persistence 3", "negative_persist_3"),
    ):

        count = sum(
            bool(getattr(r, attr))
            for r in records
        )

        print(
            f"{name:<28} "
            f"{count:>2}/{len(records)}"
        )

    for horizon, attr in (
        ("+30", "cumulative_30"),
        ("+45", "cumulative_45"),
        ("+60", "cumulative_60"),
    ):

        values = [
            getattr(r, attr)
            for r in records
            if getattr(r, attr) is not None
        ]

        print(
            f"avg cumulative {horizon:<4} = "
            f"{pct(average(values))}"
        )


# ============================================================
# OUTCOME COMPARISON
# ============================================================

def outcome_comparison(
    records: List[PersistenceRecord],
) -> None:

    pf = [
        r for r in records
        if r.outcome == "LATER_PF_BY_60"
    ]

    no_pf = [
        r for r in records
        if r.outcome == "NO_PF_BY_60"
    ]

    summarize_group(
        pf,
        "LATER_PF_BY_60"
    )

    summarize_group(
        no_pf,
        "NO_PF_BY_60"
    )

    print()
    print("=" * 120)
    print("DIRECT OUTCOME COMPARISON")
    print("=" * 120)

    print()
    print(
        "METRIC                         PF        NO_PF"
    )
    print(
        "--------------------------------------------------------"
    )

    metrics = [
        (
            "N",
            lambda group: len(group),
        ),
        (
            "avg longest negative run",
            lambda group: average(
                [r.longest_negative_run for r in group]
            ),
        ),
        (
            "avg longest positive run",
            lambda group: average(
                [r.longest_positive_run for r in group]
            ),
        ),
        (
            "avg positive intervals",
            lambda group: average(
                [r.positive_intervals for r in group]
            ),
        ),
        (
            "avg negative intervals",
            lambda group: average(
                [r.negative_intervals for r in group]
            ),
        ),
        (
            "positive persistence >=2",
            lambda group: sum(
                r.positive_persist_2
                for r in group
            ),
        ),
        (
            "positive persistence >=3",
            lambda group: sum(
                r.positive_persist_3
                for r in group
            ),
        ),
        (
            "negative persistence >=2",
            lambda group: sum(
                r.negative_persist_2
                for r in group
            ),
        ),
        (
            "negative persistence >=3",
            lambda group: sum(
                r.negative_persist_3
                for r in group
            ),
        ),
        (
            "avg D->+30",
            lambda group: average([
                r.cumulative_30
                for r in group
                if r.cumulative_30 is not None
            ]),
        ),
        (
            "avg D->+45",
            lambda group: average([
                r.cumulative_45
                for r in group
                if r.cumulative_45 is not None
            ]),
        ),
        (
            "avg D->+60",
            lambda group: average([
                r.cumulative_60
                for r in group
                if r.cumulative_60 is not None
            ]),
        ),
    ]

    for name, fn in metrics:

        pf_value = fn(pf)
        no_pf_value = fn(no_pf)

        print(
            f"{name:<30} "
            f"{str(pf_value):>10} "
            f"{str(no_pf_value):>10}"
        )


# ============================================================
# FIRST REVERSAL TIMING
# ============================================================

def reversal_timing(
    records: List[PersistenceRecord],
) -> None:

    print()
    print("=" * 120)
    print("FIRST POSITIVE REVERSAL AFTER FIRST D")
    print("=" * 120)

    for outcome in (
        "LATER_PF_BY_60",
        "NO_PF_BY_60",
    ):

        subset = [
            r for r in records
            if r.outcome == outcome
            and r.first_positive_minutes is not None
        ]

        print()
        print(
            f"{outcome}: "
            f"{len(subset)} cases with positive reversal"
        )

        counter = Counter(
            r.first_positive_minutes
            for r in subset
        )

        for minute in sorted(counter):

            print(
                f"  +{minute:>2}m = "
                f"{counter[minute]}"
            )


# ============================================================
# CASE TABLE
# ============================================================

def case_table(
    records: List[PersistenceRecord],
) -> None:

    print()
    print("=" * 120)
    print("ALL CASE PERSISTENCE TABLE")
    print("=" * 120)

    print(
        "CASE  SYMBOL DIR  OUTCOME        "
        "D    FIRST+  NEG_RUN POS_RUN "
        "D30       D45       D60"
    )

    print("-" * 120)

    for i, r in enumerate(records, 1):

        first_plus = (
            f"{r.first_positive_minutes:>3}"
            if r.first_positive_minutes is not None
            else " --"
        )

        d30 = (
            pct(r.cumulative_30)
            if r.cumulative_30 is not None
            else "      NA"
        )

        d45 = (
            pct(r.cumulative_45)
            if r.cumulative_45 is not None
            else "      NA"
        )

        d60 = (
            pct(r.cumulative_60)
            if r.cumulative_60 is not None
            else "      NA"
        )

        print(
            f"{i:>4}  "
            f"{r.symbol:<6} "
            f"{r.direction:<3} "
            f"{r.outcome:<14} "
            f"{str(r.first_d_minutes):>3} "
            f"{first_plus:>7} "
            f"{r.longest_negative_run:>7} "
            f"{r.longest_positive_run:>7} "
            f"{d30:>9} "
            f"{d45:>9} "
            f"{d60:>9}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 120)
    print(
        "AIMn / KISS V13.17 "
        "POST-FIRST-DETERIORATION PERSISTENCE AUDIT"
    )
    print("=" * 120)

    print()
    print(
        "RESEARCH ONLY"
    )
    print(
        "NO ORDERS | NO PRODUCTION CHANGES | "
        "NO AI TRAINING | NO THRESHOLD PROMOTION"
    )

    print()
    print(
        "QUESTION:"
    )
    print(
        "When deterioration begins, how long does the direction of "
        "return change persist before the trajectory reverses?"
    )

    print()

    paths = build_v1317_research_paths()

    print(
        f"TOTAL TRAJECTORY CASES = {len(paths)}"
    )

    # --------------------------------------------------------
    # Detailed case analysis
    # --------------------------------------------------------

    for i, path in enumerate(paths, 1):
        print_case_detail(i, path)

    # --------------------------------------------------------
    # Records
    # --------------------------------------------------------

    records = [
        build_record(path)
        for path in paths
    ]

    # --------------------------------------------------------
    # Outcome comparison
    # --------------------------------------------------------

    outcome_comparison(records)

    # --------------------------------------------------------
    # Reversal timing
    # --------------------------------------------------------

    reversal_timing(records)

    # --------------------------------------------------------
    # Full table
    # --------------------------------------------------------

    case_table(records)

    # --------------------------------------------------------
    # NO-D cases
    # --------------------------------------------------------

    no_d = [
        r for r in records
        if r.first_d_minutes is None
    ]

    print()
    print("=" * 120)
    print("CASES WITH NO DETERIORATING CHECKPOINT")
    print("=" * 120)

    print(
        f"NO_D_COUNT = {len(no_d)}"
    )

    for r in no_d:
        print(
            f"  {r.symbol} {r.direction} {r.outcome}"
        )

    # --------------------------------------------------------
    # Research conclusion
    # --------------------------------------------------------

    print()
    print("=" * 120)
    print("RESEARCH INTERPRETATION")
    print("=" * 120)

    print(
        """
1. This audit does NOT establish a trading rule.

2. A single positive return change after D is treated only as
   an inflection observation.

3. The important question is whether positive or negative change
   persists across multiple consecutive checkpoints.

4. Fixed-horizon D->+30 / +45 / +60 measurements are descriptive.
   They contain future information and therefore cannot be used
   as causal triggers at first D.

5. PF cases that recover temporarily remain important counterexamples.
   A temporary positive interval does not automatically mean recovery.

6. NO_PF cases that deteriorate repeatedly before recovering are also
   important counterexamples.

7. The next research question should therefore be:

       FIRST D
          |
          +-- negative persistence
          |
          +-- first positive inflection
          |
          +-- positive persistence
          |
          +-- state at inflection
          |
          +-- eventual trajectory

8. Only if the pattern survives direction-controlled and
   symbol-controlled analysis should we investigate whether
   it has operational value.
"""
    )


if __name__ == "__main__":
    main()
