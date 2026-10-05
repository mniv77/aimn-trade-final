"""
AIMn / KISS V13.17 COMPANION RESEARCH

PF PREDECESSOR STATE-CONTROLLED AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
After controlling for:

    1. direction
    2. state at +30m

does RECOVERY_FAILED_BY_30M show a different rate of later
PERSISTENT_FAILURE?

PREDICTOR
---------
RECOVERY_FAILED_BY_30M

This comes only from StatePoints at or before +30m:

    RECOVERING
        followed later by
    DETERIORATING

OUTCOME
-------
PF AFTER +30m AND BY +60m

ELIGIBILITY
-----------
Cases reaching PF at or before +30m are excluded.

CONTROL STRATA
--------------
(direction, state_at_30m)

A stratum is directly comparable only when BOTH groups exist:

    RECOVERY_FAILED_BY_30M
    NO_RECOVERY_FAILURE_BY_30M

IMPORTANT
---------
This is a descriptive association test.

It does NOT establish causality.

It does NOT create an entry, warning, rescue, hold, or exit rule.

NO PRODUCTION CODE CHANGED.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_pf_predecessor_enrichment_landmark_audit
    as landmark
)


DIRECTIONS = (
    "LONG",
    "SHORT",
)

STATES = (
    landmark.RECOVERING,
    landmark.NEUTRAL,
    landmark.DETERIORATING,
)


def safe_rate(
    numerator: int,
    denominator: int,
):
    if denominator == 0:
        return None

    return numerator / denominator


def load_cases():
    """
    Reuse the existing +30m landmark audit.

    This guarantees that:
        - case definition stays unchanged
        - PF exclusions stay unchanged
        - recovery-failure definition stays unchanged
        - outcome definition stays unchanged
    """

    return list(
        landmark.build_cases()
    )


def eligible_cases(
    cases: Sequence[object],
):
    return [
        case
        for case in cases
        if case.eligible
    ]


def build_strata(
    cases: Sequence[object],
):
    strata = defaultdict(list)

    for case in eligible_cases(cases):

        key = (
            case.direction,
            case.landmark_state,
        )

        strata[key].append(case)

    return dict(strata)


def print_header() -> None:

    print()
    print("=" * 120)
    print(
        "V13.17 PF PREDECESSOR STATE-CONTROLLED AUDIT"
    )
    print("=" * 120)

    print()
    print(
        "PREDICTOR:"
    )
    print(
        "  RECOVERY_FAILED_BY_30M"
    )

    print()
    print(
        "OUTCOME:"
    )
    print(
        "  PF AFTER +30M AND BY +60M"
    )

    print()
    print(
        "CONTROLS:"
    )
    print(
        "  DIRECTION"
    )
    print(
        "  STATE AT +30M"
    )

    print()
    print(
        "Cases reaching PF by +30m are excluded."
    )

    print(
        "No future information is used for predictor assignment."
    )

    print(
        "No production code changed."
    )


def print_population(
    cases: Sequence[object],
) -> None:

    all_cases = list(cases)
    eligible = eligible_cases(
        all_cases
    )

    excluded = [
        case
        for case in all_cases
        if not case.eligible
    ]

    later_pf = [
        case
        for case in eligible
        if case.outcome == landmark.LATE_PF
    ]

    no_pf = [
        case
        for case in eligible
        if case.outcome == landmark.NO_PF
    ]

    print()
    print("=" * 120)
    print(
        "ELIGIBLE +30M POPULATION"
    )
    print("=" * 120)

    print()
    print(
        f"TOTAL CASES        = {len(all_cases)}"
    )

    print(
        f"EXCLUDED EARLY PF  = {len(excluded)}"
    )

    print(
        f"ELIGIBLE CASES     = {len(eligible)}"
    )

    print(
        f"LATER PF BY +60M   = {len(later_pf)}"
    )

    print(
        f"NO PF BY +60M      = {len(no_pf)}"
    )


def print_direction_population(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 120)
    print(
        "DIRECTION + STATE POPULATION"
    )
    print("=" * 120)

    eligible = eligible_cases(
        cases
    )

    for direction in DIRECTIONS:

        print()
        print(
            f"DIRECTION = {direction}"
        )

        direction_cases = [
            case
            for case in eligible
            if case.direction == direction
        ]

        if not direction_cases:

            print(
                "  NO ELIGIBLE CASES"
            )

            continue

        for state in STATES:

            group = [
                case
                for case in direction_cases
                if case.landmark_state == state
            ]

            if not group:
                continue

            failed = [
                case
                for case in group
                if case.recovery_failed_by_30m
            ]

            clean = [
                case
                for case in group
                if not case.recovery_failed_by_30m
            ]

            later_pf = sum(
                case.outcome == landmark.LATE_PF
                for case in group
            )

            print(
                f"  STATE={state:<22} "
                f"CASES={len(group)} "
                f"FAILED={len(failed)} "
                f"CLEAN={len(clean)} "
                f"LATER_PF={later_pf}"
            )


def analyze_stratum(
    direction: str,
    state: str,
    cases: Sequence[object],
) -> Dict[str, object]:

    failed = [
        case
        for case in cases
        if case.recovery_failed_by_30m
    ]

    clean = [
        case
        for case in cases
        if not case.recovery_failed_by_30m
    ]

    failed_pf = sum(
        case.outcome == landmark.LATE_PF
        for case in failed
    )

    clean_pf = sum(
        case.outcome == landmark.LATE_PF
        for case in clean
    )

    failed_no_pf = sum(
        case.outcome == landmark.NO_PF
        for case in failed
    )

    clean_no_pf = sum(
        case.outcome == landmark.NO_PF
        for case in clean
    )

    failed_rate = safe_rate(
        failed_pf,
        len(failed),
    )

    clean_rate = safe_rate(
        clean_pf,
        len(clean),
    )

    if (
        failed_rate is not None
        and clean_rate is not None
    ):

        delta = (
            failed_rate
            - clean_rate
        )

        comparable = True

    else:

        delta = None
        comparable = False

    return {
        "direction": direction,
        "state": state,
        "failed": failed,
        "clean": clean,
        "failed_pf": failed_pf,
        "clean_pf": clean_pf,
        "failed_no_pf": failed_no_pf,
        "clean_no_pf": clean_no_pf,
        "failed_rate": failed_rate,
        "clean_rate": clean_rate,
        "delta": delta,
        "comparable": comparable,
    }


def print_stratum_result(
    result: Dict[str, object],
) -> None:

    direction = result["direction"]
    state = result["state"]
    failed = result["failed"]
    clean = result["clean"]

    print()
    print(
        "-" * 120
    )

    print(
        f"STRATUM: "
        f"{direction} +30M_STATE={state}"
    )

    print(
        "-" * 120
    )

    print()

    print(
        "  RECOVERY_FAILED_BY_30M"
    )

    print(
        f"    CASES             = "
        f"{len(failed)}"
    )

    print(
        f"    LATER PF BY +60M  = "
        f"{result['failed_pf']}"
    )

    print(
        f"    NO PF BY +60M     = "
        f"{result['failed_no_pf']}"
    )

    if result["failed_rate"] is None:

        print(
            "    LATER PF RATE     = NA"
        )

    else:

        print(
            f"    LATER PF RATE     = "
            f"{result['failed_rate']:.4f}"
        )

    print()
    print(
        "  NO_RECOVERY_FAILURE_BY_30M"
    )

    print(
        f"    CASES             = "
        f"{len(clean)}"
    )

    print(
        f"    LATER PF BY +60M  = "
        f"{result['clean_pf']}"
    )

    print(
        f"    NO PF BY +60M     = "
        f"{result['clean_no_pf']}"
    )

    if result["clean_rate"] is None:

        print(
            "    LATER PF RATE     = NA"
        )

    else:

        print(
            f"    LATER PF RATE     = "
            f"{result['clean_rate']:.4f}"
        )

    print()

    if result["comparable"]:

        print(
            f"  WITHIN-STRATUM RATE DELTA "
            f"(FAILED - CLEAN) = "
            f"{result['delta']:+.4f}"
        )

        print(
            "  STATUS = COMPARABLE DESCRIPTIVELY"
        )

    else:

        print(
            "  WITHIN-STRATUM RATE DELTA = NA"
        )

        print(
            "  STATUS = NOT COMPARABLE"
        )

    print()

    ordered = sorted(
        list(failed) + list(clean),
        key=lambda case: (
            case.outcome,
            case.symbol,
            case.direction,
        ),
    )

    print(
        "  EXACT CASES:"
    )

    for case in ordered:

        predictor = (
            "FAILED"
            if case.recovery_failed_by_30m
            else "CLEAN"
        )

        first_pf = (
            f"+{case.first_pf_minutes}m"
            if case.first_pf_minutes
            is not None
            else "NONE"
        )

        print(
            f"    {case.symbol:<6} "
            f"{predictor:<6} "
            f"OUTCOME={case.outcome:<18} "
            f"FIRST_PF={first_pf}"
        )


def run_strata(
    cases: Sequence[object],
):
    strata = build_strata(
        cases
    )

    results = []

    print()
    print("=" * 120)
    print(
        "DIRECTION + +30M STATE CONTROLLED COMPARISONS"
    )
    print("=" * 120)

    for direction in DIRECTIONS:

        for state in STATES:

            key = (
                direction,
                state,
            )

            group = strata.get(
                key,
                [],
            )

            if not group:
                continue

            result = analyze_stratum(
                direction,
                state,
                group,
            )

            results.append(
                result
            )

            print_stratum_result(
                result
            )

    return results


def print_control_summary(
    results: Sequence[Dict[str, object]],
) -> None:

    print()
    print("=" * 120)
    print(
        "CONTROL SUMMARY"
    )
    print("=" * 120)

    comparable = [
        result
        for result in results
        if result["comparable"]
    ]

    not_comparable = [
        result
        for result in results
        if not result["comparable"]
    ]

    print()
    print(
        f"TOTAL NONEMPTY STRATA = "
        f"{len(results)}"
    )

    print(
        f"COMPARABLE STRATA     = "
        f"{len(comparable)}"
    )

    print(
        f"NONCOMPARABLE STRATA  = "
        f"{len(not_comparable)}"
    )

    if comparable:

        print()
        print(
            "COMPARABLE STRATA:"
        )

        for result in comparable:

            print(
                f"  {result['direction']:<5} "
                f"{result['state']:<22} "
                f"FAILED_N={len(result['failed'])} "
                f"CLEAN_N={len(result['clean'])} "
                f"DELTA={result['delta']:+.4f}"
            )

    if not_comparable:

        print()
        print(
            "NONCOMPARABLE STRATA:"
        )

        for result in not_comparable:

            print(
                f"  {result['direction']:<5} "
                f"{result['state']:<22} "
                f"FAILED_N={len(result['failed'])} "
                f"CLEAN_N={len(result['clean'])}"
            )


def print_direction_summary(
    cases: Sequence[object],
) -> None:

    eligible = eligible_cases(
        cases
    )

    print()
    print("=" * 120)
    print(
        "DIRECTION-CONTROLLED SUMMARY "
        "(WITHOUT STATE POOLING)"
    )
    print("=" * 120)

    for direction in DIRECTIONS:

        group = [
            case
            for case in eligible
            if case.direction == direction
        ]

        if not group:
            continue

        failed = [
            case
            for case in group
            if case.recovery_failed_by_30m
        ]

        clean = [
            case
            for case in group
            if not case.recovery_failed_by_30m
        ]

        failed_pf = sum(
            case.outcome == landmark.LATE_PF
            for case in failed
        )

        clean_pf = sum(
            case.outcome == landmark.LATE_PF
            for case in clean
        )

        failed_rate = safe_rate(
            failed_pf,
            len(failed),
        )

        clean_rate = safe_rate(
            clean_pf,
            len(clean),
        )

        print()
        print(
            f"DIRECTION = {direction}"
        )

        print(
            f"  FAILED "
            f"N={len(failed)} "
            f"PF={failed_pf} "
            f"RATE="
            f"{'NA' if failed_rate is None else f'{failed_rate:.4f}'}"
        )

        print(
            f"  CLEAN  "
            f"N={len(clean)} "
            f"PF={clean_pf} "
            f"RATE="
            f"{'NA' if clean_rate is None else f'{clean_rate:.4f}'}"
        )


def print_interpretation(
    cases: Sequence[object],
    results: Sequence[Dict[str, object]],
) -> None:

    comparable = [
        result
        for result in results
        if result["comparable"]
    ]

    print()
    print("=" * 120)
    print(
        "V13.17 STATE-CONTROLLED PF PREDECESSOR "
        "— INTERPRETATION"
    )
    print("=" * 120)

    print()

    print(
        f"COMPARABLE DIRECTION+STATE STRATA = "
        f"{len(comparable)}"
    )

    if comparable:

        print()

        for result in comparable:

            print(
                f"{result['direction']} / "
                f"{result['state']}: "
                f"FAILED_N={len(result['failed'])}, "
                f"CLEAN_N={len(result['clean'])}, "
                f"DELTA={result['delta']:+.4f}"
            )

        print()
        print(
            "These are within-stratum descriptive "
            "comparisons only."
        )

    else:

        print()
        print(
            "No direction+state stratum contains both "
            "predictor groups."
        )

        print(
            "Therefore the current population cannot "
            "test whether recovery-failure history adds "
            "information beyond direction and +30m state."
        )

    print()

    print(
        "The +30m predictor is measured before the "
        "post-+30m outcome."
    )

    print(
        "No future information is used to define "
        "RECOVERY_FAILED_BY_30M."
    )

    print(
        "The sample remains small."
    )

    print(
        "No result becomes an entry, warning, rescue, "
        "hold, or exit rule."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print_header()

    cases = load_cases()

    print()
    print(
        f"TOTAL BUILT CASES = {len(cases)}"
    )

    print_population(
        cases
    )

    print_direction_population(
        cases
    )

    print_direction_summary(
        cases
    )

    results = run_strata(
        cases
    )

    print_control_summary(
        results
    )

    print_interpretation(
        cases,
        results,
    )

    print()
    print("=" * 120)
    print(
        "V13.17 PF PREDECESSOR STATE-CONTROLLED "
        "AUDIT COMPLETE"
    )
    print("=" * 120)


if __name__ == "__main__":
    main()
