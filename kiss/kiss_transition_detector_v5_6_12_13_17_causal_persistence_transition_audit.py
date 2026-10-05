"""
AIMn / KISS V13.17
CAUSAL POST-FIRST-DETERIORATION PERSISTENCE TRANSITION AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING
NO THRESHOLD PROMOTION

PURPOSE
-------
Study the trajectory AFTER FIRST DETERIORATING.

Unlike the earlier persistence audit, this audit explicitly separates:

    1. FIRST NEGATIVE RETURN-CHANGE INTERVAL
    2. SECOND CONSECUTIVE NEGATIVE INTERVAL
    3. THIRD CONSECUTIVE NEGATIVE INTERVAL
    4. FIRST POSITIVE REVERSAL
    5. POSITIVE PERSISTENCE AFTER REVERSAL
    6. STATE AT THE REVERSAL
    7. EVENTUAL OUTCOME

IMPORTANT
---------
All feature observations are constructed only from information available
AT OR BEFORE that checkpoint.

The eventual outcome is reported separately as a research label.

No future return is used to construct an earlier feature.

TIME LABELING
-------------
All elapsed times are measured from FIRST D:

    D+5
    D+10
    D+15
    ...

We do NOT manufacture D+30 / D+45 / D+60 when those observations
do not actually exist.

CASE POPULATION
---------------
Uses the existing V13.17 case-aware research path builder.

EXPECTED POPULATION
-------------------
28 unique trajectory cases
8 symbols
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    build_v1317_research_paths,
)


# ======================================================================
# CONSTANTS
# ======================================================================

EPS = 1e-12

STATE_D = "DETERIORATING"
STATE_PF = "PERSISTENT_FAILURE"


# ======================================================================
# HELPERS
# ======================================================================

def sign_of(value: float) -> str:
    if value > EPS:
        return "+"
    if value < -EPS:
        return "-"
    return "0"


def outcome_of(path) -> str:
    """
    Existing V13.17 research outcome classification.

    A case is considered LATER_PF_BY_60 if a PF checkpoint exists
    after the trajectory begins and the case reaches PF by the final
    research horizon.

    Otherwise NO_PF_BY_60.
    """
    for point in path.points:
        if point.state == STATE_PF:
            return "LATER_PF_BY_60"

    return "NO_PF_BY_60"


def first_d_index(path) -> Optional[int]:
    for i, point in enumerate(path.points):
        if point.state == STATE_D:
            return i
    return None


def pct(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{value:+.6f}"


def elapsed_label(first_d_minutes: int, point_minutes: int) -> str:
    delta = point_minutes - first_d_minutes
    return f"D+{delta}m"


def eventual_counts(records: List[dict]) -> Counter:
    return Counter(r["outcome"] for r in records)


def print_counts(title: str, records: List[dict]) -> None:
    counts = eventual_counts(records)
    n = len(records)

    print()
    print("-" * 110)
    print(title)
    print("-" * 110)
    print(f"N = {n}")

    if n == 0:
        return

    for outcome in ("LATER_PF_BY_60", "NO_PF_BY_60"):
        c = counts.get(outcome, 0)
        rate = c / n if n else 0.0
        print(f"  {outcome:<20} {c:>3} / {n:<3} = {rate:>7.3%}")


# ======================================================================
# CASE RECORD
# ======================================================================

@dataclass
class CaseAnalysis:
    case_no: int
    symbol: str
    direction: str
    outcome: str
    first_d_minutes: int
    first_d_return: float
    first_d_state: str

    first_negative: Optional[dict]
    second_negative: Optional[dict]
    third_negative: Optional[dict]

    first_positive: Optional[dict]

    positive_run_max: int
    negative_run_max: int

    positive_persistence_2: bool
    positive_persistence_3: bool


# ======================================================================
# BUILD ONE CASE
# ======================================================================

def analyze_case(case_no: int, path) -> CaseAnalysis:

    d_idx = first_d_index(path)

    if d_idx is None:
        return CaseAnalysis(
            case_no=case_no,
            symbol=path.symbol,
            direction=path.direction,
            outcome=outcome_of(path),
            first_d_minutes=-1,
            first_d_return=0.0,
            first_d_state="NONE",
            first_negative=None,
            second_negative=None,
            third_negative=None,
            first_positive=None,
            positive_run_max=0,
            negative_run_max=0,
            positive_persistence_2=False,
            positive_persistence_3=False,
        )

    d_point = path.points[d_idx]

    # --------------------------------------------------------------
    # Post-D observations.
    #
    # Each observation is computed from the CURRENT and PREVIOUS
    # available checkpoint only.
    #
    # Therefore the sign at checkpoint i is causal at checkpoint i.
    # --------------------------------------------------------------

    observations = []

    for i in range(d_idx + 1, len(path.points)):

        previous = path.points[i - 1]
        current = path.points[i]

        delta_return = current.return_pct - previous.return_pct

        observations.append(
            {
                "index": i,
                "minutes": current.minutes,
                "elapsed": current.minutes - d_point.minutes,
                "state": current.state,
                "return_pct": current.return_pct,
                "delta_return": delta_return,
                "sign": sign_of(delta_return),
            }
        )

    # --------------------------------------------------------------
    # Persistence runs
    # --------------------------------------------------------------

    negative_run = 0
    positive_run = 0

    first_negative = None
    second_negative = None
    third_negative = None

    first_positive = None

    max_negative_run = 0
    max_positive_run = 0

    positive_run_at_first_reversal = 0

    for obs in observations:

        if obs["sign"] == "-":

            negative_run += 1
            positive_run = 0

            max_negative_run = max(
                max_negative_run,
                negative_run,
            )

            if negative_run == 1 and first_negative is None:
                first_negative = {
                    **obs,
                    "negative_run": negative_run,
                }

            elif negative_run == 2 and second_negative is None:
                second_negative = {
                    **obs,
                    "negative_run": negative_run,
                }

            elif negative_run == 3 and third_negative is None:
                third_negative = {
                    **obs,
                    "negative_run": negative_run,
                }

        elif obs["sign"] == "+":

            positive_run += 1
            negative_run = 0

            max_positive_run = max(
                max_positive_run,
                positive_run,
            )

            if first_positive is None:
                first_positive = {
                    **obs,
                    "positive_run": positive_run,
                }

        else:

            positive_run = 0
            negative_run = 0

    # --------------------------------------------------------------
    # Positive persistence.
    #
    # We specifically ask:
    #
    #   Did the first positive reversal continue for >=2?
    #   Did it continue for >=3?
    #
    # This is measured from the first positive reversal forward.
    # --------------------------------------------------------------

    positive_persistence_2 = False
    positive_persistence_3 = False

    if first_positive is not None:

        start_index = first_positive["index"]

        run = 0

        for obs in observations:

            if obs["index"] < start_index:
                continue

            if obs["sign"] == "+":
                run += 1
            else:
                break

        positive_run_at_first_reversal = run

        positive_persistence_2 = run >= 2
        positive_persistence_3 = run >= 3

    return CaseAnalysis(
        case_no=case_no,
        symbol=path.symbol,
        direction=path.direction,
        outcome=outcome_of(path),
        first_d_minutes=d_point.minutes,
        first_d_return=d_point.return_pct,
        first_d_state=d_point.state,
        first_negative=first_negative,
        second_negative=second_negative,
        third_negative=third_negative,
        first_positive=first_positive,
        positive_run_max=max_positive_run,
        negative_run_max=max_negative_run,
        positive_persistence_2=positive_persistence_2,
        positive_persistence_3=positive_persistence_3,
    )


# ======================================================================
# PRINT CASES
# ======================================================================

def print_case_detail(case: CaseAnalysis) -> None:

    print()
    print("=" * 110)
    print(
        f"CASE #{case.case_no:02d}  "
        f"{case.symbol:<5} "
        f"{case.direction:<5} "
        f"{case.outcome}"
    )
    print("=" * 110)

    if case.first_d_minutes < 0:
        print("FIRST D = NONE")
        return

    print(
        f"FIRST D = +{case.first_d_minutes}m "
        f"return={case.first_d_return:+.6f}"
    )

    def show(label: str, obs: Optional[dict]):

        if obs is None:
            print(f"{label:<28} NONE")
            return

        print(
            f"{label:<28} "
            f"{elapsed_label(case.first_d_minutes, obs['minutes']):<8} "
            f"state={obs['state']:<20} "
            f"dRETURN={obs['delta_return']:+.6f}"
        )

    show("FIRST NEGATIVE", case.first_negative)
    show("SECOND NEGATIVE", case.second_negative)
    show("THIRD NEGATIVE", case.third_negative)
    show("FIRST POSITIVE REVERSAL", case.first_positive)

    print(
        f"MAX NEGATIVE RUN           = {case.negative_run_max}"
    )
    print(
        f"MAX POSITIVE RUN           = {case.positive_run_max}"
    )
    print(
        f"POSITIVE PERSISTENCE >=2   = "
        f"{case.positive_persistence_2}"
    )
    print(
        f"POSITIVE PERSISTENCE >=3   = "
        f"{case.positive_persistence_3}"
    )


# ======================================================================
# EVENT-BASED COHORTS
# ======================================================================

def build_event_records(
    analyses: List[CaseAnalysis],
    event_name: str,
) -> List[dict]:

    records = []

    for case in analyses:

        if event_name == "FIRST_NEGATIVE":
            obs = case.first_negative

        elif event_name == "SECOND_NEGATIVE":
            obs = case.second_negative

        elif event_name == "THIRD_NEGATIVE":
            obs = case.third_negative

        elif event_name == "FIRST_POSITIVE":
            obs = case.first_positive

        else:
            raise ValueError(event_name)

        if obs is None:
            continue

        records.append(
            {
                "case_no": case.case_no,
                "symbol": case.symbol,
                "direction": case.direction,
                "outcome": case.outcome,
                "state": obs["state"],
                "elapsed": obs["elapsed"],
                "delta_return": obs["delta_return"],
            }
        )

    return records


# ======================================================================
# EVENT TABLE
# ======================================================================

def print_event_table(
    title: str,
    records: List[dict],
) -> None:

    print()
    print("=" * 110)
    print(title)
    print("=" * 110)

    if not records:
        print("NO CASES")
        return

    print(
        f"{'CASE':>4} "
        f"{'SYMBOL':<6} "
        f"{'DIR':<6} "
        f"{'OUTCOME':<18} "
        f"{'ELAPSED':>8} "
        f"{'STATE':<22} "
        f"{'dRETURN':>12}"
    )

    print("-" * 110)

    for r in records:

        print(
            f"{r['case_no']:>4} "
            f"{r['symbol']:<6} "
            f"{r['direction']:<6} "
            f"{r['outcome']:<18} "
            f"{r['elapsed']:>7}m "
            f"{r['state']:<22} "
            f"{r['delta_return']:>+12.6f}"
        )


# ======================================================================
# DIRECTION CONTROL
# ======================================================================

def direction_summary(
    records: List[dict],
    title: str,
) -> None:

    print()
    print("=" * 110)
    print(title)
    print("=" * 110)

    for direction in ("LONG", "SHORT"):

        subset = [
            r for r in records
            if r["direction"] == direction
        ]

        print_counts(
            f"{direction}",
            subset,
        )


# ======================================================================
# SYMBOL CONTROL
# ======================================================================

def symbol_summary(
    records: List[dict],
    title: str,
) -> None:

    print()
    print("=" * 110)
    print(title)
    print("=" * 110)

    symbols = sorted(
        set(r["symbol"] for r in records)
    )

    print(
        f"{'SYMBOL':<8} "
        f"{'N':>4} "
        f"{'PF':>5} "
        f"{'NO_PF':>6} "
        f"{'PF_RATE':>9}"
    )

    print("-" * 110)

    for symbol in symbols:

        subset = [
            r for r in records
            if r["symbol"] == symbol
        ]

        pf = sum(
            r["outcome"] == "LATER_PF_BY_60"
            for r in subset
        )

        no_pf = sum(
            r["outcome"] == "NO_PF_BY_60"
            for r in subset
        )

        n = len(subset)

        rate = pf / n if n else 0.0

        print(
            f"{symbol:<8} "
            f"{n:>4} "
            f"{pf:>5} "
            f"{no_pf:>6} "
            f"{rate:>8.1%}"
        )


# ======================================================================
# PERSISTENCE SUMMARY
# ======================================================================

def persistence_summary(
    analyses: List[CaseAnalysis],
) -> None:

    print()
    print("=" * 110)
    print("PERSISTENCE THRESHOLD SUMMARY")
    print("=" * 110)

    for outcome in (
        "LATER_PF_BY_60",
        "NO_PF_BY_60",
    ):

        subset = [
            c for c in analyses
            if c.outcome == outcome
            and c.first_d_minutes >= 0
        ]

        n = len(subset)

        print()
        print(f"{outcome}  N={n}")

        for threshold in (1, 2, 3):

            negative = sum(
                c.negative_run_max >= threshold
                for c in subset
            )

            positive = sum(
                c.positive_run_max >= threshold
                for c in subset
            )

            print(
                f"  negative run >= {threshold}: "
                f"{negative}/{n}"
            )

            print(
                f"  positive run >= {threshold}: "
                f"{positive}/{n}"
            )


# ======================================================================
# FIRST POSITIVE REVERSAL STATE
# ======================================================================

def reversal_state_summary(
    analyses: List[CaseAnalysis],
) -> None:

    print()
    print("=" * 110)
    print("FIRST POSITIVE REVERSAL — STATE AT REVERSAL")
    print("=" * 110)

    groups = defaultdict(list)

    for case in analyses:

        if case.first_positive is None:
            continue

        key = (
            case.outcome,
            case.first_positive["state"],
        )

        groups[key].append(case)

    for outcome in (
        "LATER_PF_BY_60",
        "NO_PF_BY_60",
    ):

        print()
        print(outcome)

        for state in (
            "DETERIORATING",
            "NEUTRAL",
            "RECOVERING",
            "PERSISTENT_FAILURE",
        ):

            subset = groups.get(
                (outcome, state),
                [],
            )

            if subset:
                print(
                    f"  {state:<22} "
                    f"N={len(subset)} "
                    f"cases="
                    f"{','.join(str(c.case_no) for c in subset)}"
                )


# ======================================================================
# POSITIVE PERSISTENCE
# ======================================================================

def positive_persistence_summary(
    analyses: List[CaseAnalysis],
) -> None:

    print()
    print("=" * 110)
    print("FIRST POSITIVE REVERSAL PERSISTENCE")
    print("=" * 110)

    for threshold in (1, 2, 3):

        print()
        print(
            f"POSITIVE RUN >= {threshold}"
        )

        for outcome in (
            "LATER_PF_BY_60",
            "NO_PF_BY_60",
        ):

            subset = [
                c for c in analyses
                if c.first_positive is not None
            ]

            subset = [
                c for c in subset
                if c.outcome == outcome
            ]

            if threshold == 1:
                hits = len(subset)

            elif threshold == 2:
                hits = sum(
                    c.positive_persistence_2
                    for c in subset
                )

            else:
                hits = sum(
                    c.positive_persistence_3
                    for c in subset
                )

            n = len(subset)

            print(
                f"  {outcome:<18} "
                f"{hits}/{n}"
            )


# ======================================================================
# DIRECTION + PERSISTENCE
# ======================================================================

def direction_persistence_summary(
    analyses: List[CaseAnalysis],
) -> None:

    print()
    print("=" * 110)
    print("DIRECTION-CONTROLLED PERSISTENCE")
    print("=" * 110)

    for direction in ("LONG", "SHORT"):

        print()
        print(f"### {direction}")

        subset = [
            c for c in analyses
            if c.direction == direction
            and c.first_d_minutes >= 0
        ]

        for outcome in (
            "LATER_PF_BY_60",
            "NO_PF_BY_60",
        ):

            group = [
                c for c in subset
                if c.outcome == outcome
            ]

            n = len(group)

            neg2 = sum(
                c.negative_run_max >= 2
                for c in group
            )

            neg3 = sum(
                c.negative_run_max >= 3
                for c in group
            )

            pos2 = sum(
                c.positive_run_max >= 2
                for c in group
            )

            pos3 = sum(
                c.positive_run_max >= 3
                for c in group
            )

            print(
                f"  {outcome:<18} N={n:<3} "
                f"NEG>=2={neg2:<3} "
                f"NEG>=3={neg3:<3} "
                f"POS>=2={pos2:<3} "
                f"POS>=3={pos3:<3}"
            )


# ======================================================================
# SYMBOL + PERSISTENCE
# ======================================================================

def symbol_persistence_summary(
    analyses: List[CaseAnalysis],
) -> None:

    print()
    print("=" * 110)
    print("SYMBOL-CONTROLLED PERSISTENCE")
    print("=" * 110)

    symbols = sorted(
        set(c.symbol for c in analyses)
    )

    print(
        f"{'SYMBOL':<8} "
        f"{'N':>3} "
        f"{'PF':>3} "
        f"{'NO':>3} "
        f"{'NEG2 PF':>8} "
        f"{'NEG2 NO':>8} "
        f"{'NEG3 PF':>8} "
        f"{'NEG3 NO':>8}"
    )

    print("-" * 110)

    for symbol in symbols:

        subset = [
            c for c in analyses
            if c.symbol == symbol
            and c.first_d_minutes >= 0
        ]

        pf = [
            c for c in subset
            if c.outcome == "LATER_PF_BY_60"
        ]

        no_pf = [
            c for c in subset
            if c.outcome == "NO_PF_BY_60"
        ]

        neg2_pf = sum(
            c.negative_run_max >= 2
            for c in pf
        )

        neg2_no = sum(
            c.negative_run_max >= 2
            for c in no_pf
        )

        neg3_pf = sum(
            c.negative_run_max >= 3
            for c in pf
        )

        neg3_no = sum(
            c.negative_run_max >= 3
            for c in no_pf
        )

        print(
            f"{symbol:<8} "
            f"{len(subset):>3} "
            f"{len(pf):>3} "
            f"{len(no_pf):>3} "
            f"{neg2_pf:>8} "
            f"{neg2_no:>8} "
            f"{neg3_pf:>8} "
            f"{neg3_no:>8}"
        )


# ======================================================================
# ACTUAL ELAPSED-TIME CHECK
# ======================================================================

def elapsed_time_summary(
    analyses: List[CaseAnalysis],
) -> None:

    print()
    print("=" * 110)
    print("FIRST NEGATIVE / FIRST POSITIVE — ACTUAL ELAPSED TIME")
    print("=" * 110)

    for outcome in (
        "LATER_PF_BY_60",
        "NO_PF_BY_60",
    ):

        subset = [
            c for c in analyses
            if c.outcome == outcome
            and c.first_d_minutes >= 0
        ]

        neg_times = [
            c.first_negative["elapsed"]
            for c in subset
            if c.first_negative is not None
        ]

        pos_times = [
            c.first_positive["elapsed"]
            for c in subset
            if c.first_positive is not None
        ]

        print()
        print(outcome)

        if neg_times:
            print(
                f"  first negative elapsed: "
                f"{neg_times}"
            )
        else:
            print(
                "  first negative elapsed: NONE"
            )

        if pos_times:
            print(
                f"  first positive elapsed: "
                f"{pos_times}"
            )
        else:
            print(
                "  first positive elapsed: NONE"
            )


# ======================================================================
# MAIN
# ======================================================================

def main() -> None:

    print("=" * 110)
    print("AIMn / KISS V13.17")
    print("CAUSAL POST-FIRST-DETERIORATION PERSISTENCE TRANSITION AUDIT")
    print("=" * 110)
    print()
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print("NO THRESHOLD PROMOTION")
    print()
    print(
        "FEATURES are constructed only from information available "
        "at each checkpoint."
    )
    print(
        "EVENTUAL OUTCOME is reported separately."
    )
    print()

    paths = build_v1317_research_paths()

    print()
    print(
        f"TOTAL TRAJECTORY CASES = {len(paths)}"
    )

    analyses: List[CaseAnalysis] = []

    for case_no, path in enumerate(paths, start=1):

        case = analyze_case(
            case_no,
            path,
        )

        analyses.append(case)

        print_case_detail(case)

    # --------------------------------------------------------------
    # Event cohorts
    # --------------------------------------------------------------

    first_negative = build_event_records(
        analyses,
        "FIRST_NEGATIVE",
    )

    second_negative = build_event_records(
        analyses,
        "SECOND_NEGATIVE",
    )

    third_negative = build_event_records(
        analyses,
        "THIRD_NEGATIVE",
    )

    first_positive = build_event_records(
        analyses,
        "FIRST_POSITIVE",
    )

    # --------------------------------------------------------------
    # Print event tables
    # --------------------------------------------------------------

    print_event_table(
        "FIRST NEGATIVE RETURN-CHANGE INTERVAL",
        first_negative,
    )

    print_event_table(
        "SECOND CONSECUTIVE NEGATIVE RETURN-CHANGE INTERVAL",
        second_negative,
    )

    print_event_table(
        "THIRD CONSECUTIVE NEGATIVE RETURN-CHANGE INTERVAL",
        third_negative,
    )

    print_event_table(
        "FIRST POSITIVE RETURN-CHANGE REVERSAL",
        first_positive,
    )

    # --------------------------------------------------------------
    # Outcome counts
    # --------------------------------------------------------------

    print_counts(
        "EVENT: FIRST NEGATIVE",
        first_negative,
    )

    print_counts(
        "EVENT: SECOND CONSECUTIVE NEGATIVE",
        second_negative,
    )

    print_counts(
        "EVENT: THIRD CONSECUTIVE NEGATIVE",
        third_negative,
    )

    print_counts(
        "EVENT: FIRST POSITIVE REVERSAL",
        first_positive,
    )

    # --------------------------------------------------------------
    # Persistence
    # --------------------------------------------------------------

    persistence_summary(
        analyses,
    )

    positive_persistence_summary(
        analyses,
    )

    # --------------------------------------------------------------
    # Reversal state
    # --------------------------------------------------------------

    reversal_state_summary(
        analyses,
    )

    # --------------------------------------------------------------
    # Direction
    # --------------------------------------------------------------

    direction_persistence_summary(
        analyses,
    )

    direction_summary(
        first_negative,
        "FIRST NEGATIVE — DIRECTION CONTROL",
    )

    direction_summary(
        second_negative,
        "SECOND NEGATIVE — DIRECTION CONTROL",
    )

    direction_summary(
        third_negative,
        "THIRD NEGATIVE — DIRECTION CONTROL",
    )

    direction_summary(
        first_positive,
        "FIRST POSITIVE — DIRECTION CONTROL",
    )

    # --------------------------------------------------------------
    # Symbol
    # --------------------------------------------------------------

    symbol_persistence_summary(
        analyses,
    )

    symbol_summary(
        first_negative,
        "FIRST NEGATIVE — SYMBOL CONTROL",
    )

    symbol_summary(
        second_negative,
        "SECOND NEGATIVE — SYMBOL CONTROL",
    )

    symbol_summary(
        third_negative,
        "THIRD NEGATIVE — SYMBOL CONTROL",
    )

    symbol_summary(
        first_positive,
        "FIRST POSITIVE — SYMBOL CONTROL",
    )

    # --------------------------------------------------------------
    # Actual elapsed time
    # --------------------------------------------------------------

    elapsed_time_summary(
        analyses,
    )

    # --------------------------------------------------------------
    # Final research interpretation
    # --------------------------------------------------------------

    print()
    print("=" * 110)
    print("RESEARCH INTERPRETATION")
    print("=" * 110)

    print(
        """
1. FIRST D is the beginning of the post-deterioration observation window.

2. FIRST NEGATIVE, SECOND NEGATIVE, and THIRD NEGATIVE are causal
   trajectory observations. Each is known only after the corresponding
   completed checkpoint occurs.

3. A positive return-change interval is an inflection observation only.
   It is NOT automatically recovery.

4. Positive persistence is measured separately because a single positive
   interval can be temporary.

5. Eventual PF / NO_PF is a future research label. It must NOT be mixed
   into the causal feature construction.

6. Direction-controlled results are required because LONG and SHORT
   trajectories can have different behavior.

7. Symbol-controlled results are required because a pooled pattern can
   otherwise be dominated by one or two symbols.

8. Actual elapsed time from FIRST D is used. Late FIRST-D cases are
   therefore not mislabeled as D+30 / D+45 / D+60.

9. This audit does NOT establish a trading rule.

10. The next decision should depend on whether persistence separation
    remains visible after direction and symbol controls.
"""
    )


if __name__ == "__main__":
    main()
