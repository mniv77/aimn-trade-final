"""
AIMn / KISS V13.17 COMPANION RESEARCH
PERSISTENT FAILURE DIRECTION-CONTROLLED PREDECESSOR AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
After controlling for trade direction, does the trajectory immediately
preceding FIRST PERSISTENT_FAILURE show different post-PF behavior?

PRIMARY COHORT A
----------------
DIRECT_FROM_DETERIORATING

    DETERIORATING -> PERSISTENT_FAILURE

PRIMARY COHORT B
----------------
RECOVERY_FAILED_THEN_DETERIORATING

    RECOVERING -> ... -> DETERIORATING -> PERSISTENT_FAILURE

DIRECTION CONTROL
-----------------
LONG is compared only with LONG.
SHORT is compared only with SHORT.

This is required because the previous pooled audit showed that:

    DIRECT_FROM_DETERIORATING
        = 5 LONG / 1 SHORT

    RECOVERY_FAILED_THEN_DETERIORATING
        = 1 LONG / 3 SHORT

Therefore, pooled differences could be caused by direction composition.

IMPORTANT
---------
Only the PRIMARY cohorts are compared.

DIRECT_FROM_NEUTRAL and OTHER_OR_UNKNOWN are excluded.

One FIRST PF onset is used per unique trajectory case.

Future returns are measured FROM THE FIRST PF ONSET checkpoint.

Only exact StatePoints are used.

No future information is used to determine cohort membership.

NO FUTURE LEAKAGE
-----------------
Cohort assignment depends only on the trajectory BEFORE first PF.

The future-return measurement occurs only after the cohort has already
been assigned.

SAMPLE-SIZE RULE
----------------
The audit does NOT force a comparison when a direction has fewer than
one case in either cohort.

When both cohorts exist, the audit reports:

    N
    AVG
    MEDIAN
    POSITIVE
    NEGATIVE

for:

    +5m
    +10m
    +15m
    +20m
    +30m

A simple descriptive delta is also shown:

    FAILED_RECOVERY - DIRECT

This delta is descriptive only.

It is NOT a statistical test.

It is NOT a trading rule.

NO PRODUCTION CODE CHANGED.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Dict, List, Sequence

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_persistent_failure_cohort_return_audit
    as cohort_audit
)


DIRECT = (
    cohort_audit.DIRECT
)

FAILED_RECOVERY = (
    cohort_audit.FAILED_RECOVERY
)

HORIZONS = (
    5,
    10,
    15,
    20,
    30,
)

DIRECTIONS = (
    "LONG",
    "SHORT",
)


def values_at_horizon(
    cases: Sequence[object],
    horizon: int,
) -> List[float]:

    values: List[float] = []

    for case in cases:

        future_returns = getattr(
            case,
            "future_returns",
            {},
        )

        value = future_returns.get(
            horizon
        )

        if value is None:
            continue

        values.append(
            float(value)
        )

    return values


def stats(
    values: Sequence[float],
) -> Dict[str, object]:

    if not values:

        return {
            "n": 0,
            "avg": None,
            "median": None,
            "positive": 0,
            "negative": 0,
            "zero": 0,
        }

    positive = sum(
        value > 0
        for value in values
    )

    negative = sum(
        value < 0
        for value in values
    )

    zero = sum(
        value == 0
        for value in values
    )

    return {
        "n": len(values),
        "avg": mean(values),
        "median": median(values),
        "positive": positive,
        "negative": negative,
        "zero": zero,
    }


def print_header() -> None:

    print()
    print("=" * 115)
    print(
        "V13.17 PERSISTENT FAILURE "
        "DIRECTION-CONTROLLED PREDECESSOR AUDIT"
    )
    print("=" * 115)

    print()
    print(
        "PRIMARY COHORT A:"
    )
    print(
        "  DIRECT_FROM_DETERIORATING"
    )

    print()
    print(
        "PRIMARY COHORT B:"
    )
    print(
        "  RECOVERY_FAILED_THEN_DETERIORATING"
    )

    print()
    print(
        "CONTROL:"
    )
    print(
        "  LONG compared only with LONG"
    )
    print(
        "  SHORT compared only with SHORT"
    )

    print()
    print(
        "Future returns are measured FROM FIRST PF ONSET."
    )

    print(
        "No future information is used for cohort assignment."
    )

    print(
        "No production code changed."
    )


def load_cases():

    cases = cohort_audit.build_cases()

    return list(cases)


def print_population(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 115)
    print(
        "DIRECTION-CONTROLLED POPULATION"
    )
    print("=" * 115)

    print()

    for direction in DIRECTIONS:

        print(
            f"DIRECTION = {direction}"
        )

        for cohort in (
            DIRECT,
            FAILED_RECOVERY,
        ):

            cohort_cases = [
                case
                for case in cases
                if (
                    getattr(case, "direction", "")
                    == direction
                    and getattr(case, "cohort", "")
                    == cohort
                )
            ]

            print(
                f"  {cohort:<42} = "
                f"{len(cohort_cases)}"
            )

        direct_count = sum(
            1
            for case in cases
            if (
                getattr(case, "direction", "")
                == direction
                and getattr(case, "cohort", "")
                == DIRECT
            )
        )

        failed_count = sum(
            1
            for case in cases
            if (
                getattr(case, "direction", "")
                == direction
                and getattr(case, "cohort", "")
                == FAILED_RECOVERY
            )
        )

        comparable = (
            direct_count > 0
            and failed_count > 0
        )

        print(
            f"  WITHIN-DIRECTION COMPARISON AVAILABLE = "
            f"{comparable}"
        )

        if not comparable:

            print(
                "  REASON = one or both primary cohorts "
                "have zero cases in this direction"
            )


def print_direction_summary(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 115)
    print(
        "DIRECTION-CONTROLLED RETURN SUMMARY"
    )
    print("=" * 115)

    for direction in DIRECTIONS:

        print()
        print(
            f"DIRECTION = {direction}"
        )

        direct_cases = [
            case
            for case in cases
            if (
                getattr(case, "direction", "")
                == direction
                and getattr(case, "cohort", "")
                == DIRECT
            )
        ]

        failed_cases = [
            case
            for case in cases
            if (
                getattr(case, "direction", "")
                == direction
                and getattr(case, "cohort", "")
                == FAILED_RECOVERY
            )
        ]

        print()
        print(
            f"  DIRECT_FROM_DETERIORATING "
            f"N_CASES = {len(direct_cases)}"
        )

        print(
            f"  RECOVERY_FAILED_THEN_DETERIORATING "
            f"N_CASES = {len(failed_cases)}"
        )

        if not direct_cases or not failed_cases:

            print()
            print(
                "  STATUS = NOT COMPARABLE"
            )

            print(
                "  This direction does not contain both "
                "primary cohorts."
            )

            continue

        print()
        print(
            "  WITHIN-DIRECTION FUTURE RETURNS"
        )

        for horizon in HORIZONS:

            direct_values = values_at_horizon(
                direct_cases,
                horizon,
            )

            failed_values = values_at_horizon(
                failed_cases,
                horizon,
            )

            direct_stats = stats(
                direct_values
            )

            failed_stats = stats(
                failed_values
            )

            direct_avg = direct_stats["avg"]
            failed_avg = failed_stats["avg"]

            if (
                direct_avg is None
                or failed_avg is None
            ):

                delta = None

            else:

                delta = (
                    float(failed_avg)
                    - float(direct_avg)
                )

            print()
            print(
                f"  +{horizon}m"
            )

            print(
                f"    DIRECT "
                f"N={direct_stats['n']} "
                f"AVG="
                f"{'NA' if direct_avg is None else f'{direct_avg:+.6f}%'} "
                f"MEDIAN="
                f"{'NA' if direct_stats['median'] is None else f'{direct_stats['median']:+.6f}%'} "
                f"POS={direct_stats['positive']} "
                f"NEG={direct_stats['negative']}"
            )

            print(
                f"    FAILED "
                f"N={failed_stats['n']} "
                f"AVG="
                f"{'NA' if failed_avg is None else f'{failed_avg:+.6f}%'} "
                f"MEDIAN="
                f"{'NA' if failed_stats['median'] is None else f'{failed_stats['median']:+.6f}%'} "
                f"POS={failed_stats['positive']} "
                f"NEG={failed_stats['negative']}"
            )

            print(
                f"    DELTA (FAILED - DIRECT) = "
                f"{'NA' if delta is None else f'{delta:+.6f}%'}"
            )


def print_case_matrix(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 115)
    print(
        "DIRECTION-CONTROLLED EXACT CASE MATRIX"
    )
    print("=" * 115)

    for direction in DIRECTIONS:

        direction_cases = [
            case
            for case in cases
            if getattr(case, "direction", "")
            == direction
        ]

        if not direction_cases:
            continue

        print()
        print(
            f"DIRECTION = {direction}"
        )

        for cohort in (
            DIRECT,
            FAILED_RECOVERY,
        ):

            cohort_cases = [
                case
                for case in direction_cases
                if getattr(case, "cohort", "")
                == cohort
            ]

            if not cohort_cases:

                continue

            print()
            print(
                f"  COHORT = {cohort}"
            )

            ordered = sorted(
                cohort_cases,
                key=lambda case: (
                    getattr(
                        case,
                        "onset_minutes",
                        0,
                    ),
                    getattr(
                        case,
                        "symbol",
                        "",
                    ),
                ),
            )

            for case in ordered:

                print()
                print(
                    f"    {getattr(case, 'symbol', ''):<6} "
                    f"{direction:<5} "
                    f"PF_ONSET=+"
                    f"{getattr(case, 'onset_minutes', None)}m "
                    f"GROUP="
                    f"{getattr(case, 'timing_group', '')}"
                )

                print(
                    f"      ONSET_RETURN="
                    f"{getattr(case, 'onset_return_pct', None)}"
                )

                future_returns = getattr(
                    case,
                    "future_returns",
                    {},
                )

                for horizon in HORIZONS:

                    value = future_returns.get(
                        horizon
                    )

                    if value is None:

                        print(
                            f"      +{horizon}m = NA"
                        )

                    else:

                        print(
                            f"      +{horizon}m = "
                            f"{value:+.6f}%"
                        )


def print_timing_crosscheck(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 115)
    print(
        "DIRECTION + PF TIMING CROSSCHECK"
    )
    print("=" * 115)

    for direction in DIRECTIONS:

        print()
        print(
            f"DIRECTION = {direction}"
        )

        for cohort in (
            DIRECT,
            FAILED_RECOVERY,
        ):

            group_counts = {}

            for timing_group in (
                "EARLY_PF",
                "LATE_PF",
                "UNKNOWN_TIMING",
            ):

                count = sum(
                    1
                    for case in cases
                    if (
                        getattr(
                            case,
                            "direction",
                            "",
                        )
                        == direction
                        and getattr(
                            case,
                            "cohort",
                            "",
                        )
                        == cohort
                        and getattr(
                            case,
                            "timing_group",
                            "",
                        )
                        == timing_group
                    )
                )

                group_counts[timing_group] = count

            total = sum(
                group_counts.values()
            )

            print(
                f"  {cohort:<42} "
                f"TOTAL={total} "
                f"EARLY={group_counts['EARLY_PF']} "
                f"LATE={group_counts['LATE_PF']} "
                f"UNKNOWN={group_counts['UNKNOWN_TIMING']}"
            )


def print_overall_control_assessment(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 115)
    print(
        "DIRECTION-CONTROLLED ASSESSMENT"
    )
    print("=" * 115)

    print()

    for direction in DIRECTIONS:

        direct_cases = [
            case
            for case in cases
            if (
                getattr(case, "direction", "")
                == direction
                and getattr(case, "cohort", "")
                == DIRECT
            )
        ]

        failed_cases = [
            case
            for case in cases
            if (
                getattr(case, "direction", "")
                == direction
                and getattr(case, "cohort", "")
                == FAILED_RECOVERY
            )
        ]

        print(
            f"{direction}:"
        )

        print(
            f"  DIRECT cases = "
            f"{len(direct_cases)}"
        )

        print(
            f"  FAILED-RECOVERY cases = "
            f"{len(failed_cases)}"
        )

        if not direct_cases or not failed_cases:

            print(
                "  RESULT = NO WITHIN-DIRECTION "
                "COMPARISON POSSIBLE"
            )

        else:

            print(
                "  RESULT = WITHIN-DIRECTION "
                "COMPARISON POSSIBLE"
            )

        print()

    long_direct = [
        case
        for case in cases
        if (
            getattr(case, "direction", "")
            == "LONG"
            and getattr(case, "cohort", "")
            == DIRECT
        )
    ]

    long_failed = [
        case
        for case in cases
        if (
            getattr(case, "direction", "")
            == "LONG"
            and getattr(case, "cohort", "")
            == FAILED_RECOVERY
        )
    ]

    short_direct = [
        case
        for case in cases
        if (
            getattr(case, "direction", "")
            == "SHORT"
            and getattr(case, "cohort", "")
            == DIRECT
        )
    ]

    short_failed = [
        case
        for case in cases
        if (
            getattr(case, "direction", "")
            == "SHORT"
            and getattr(case, "cohort", "")
            == FAILED_RECOVERY
        )
    ]

    if (
        long_direct
        and long_failed
    ):
        print(
            "LONG contains both primary cohorts."
        )
        print(
            "A within-LONG descriptive comparison is possible."
        )
    else:
        print(
            "LONG does not contain both primary cohorts."
        )

    if (
        short_direct
        and short_failed
    ):
        print(
            "SHORT contains both primary cohorts."
        )
        print(
            "A within-SHORT descriptive comparison is possible."
        )
    else:
        print(
            "SHORT does not contain both primary cohorts."
        )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "The presence of a directional comparison does not "
        "make the sample large enough for validation."
    )

    print(
        "A descriptive difference does not establish causality."
    )

    print(
        "No result becomes an entry, warning, rescue, hold, "
        "or exit rule."
    )

    print(
        "No production code changed."
    )


def print_interpretation(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 115)
    print(
        "V13.17 DIRECTION-CONTROLLED PF PREDECESSOR "
        "— INTERPRETATION"
    )
    print("=" * 115)

    print()

    total_primary = len(cases)

    direct_total = sum(
        1
        for case in cases
        if getattr(case, "cohort", "")
        == DIRECT
    )

    failed_total = sum(
        1
        for case in cases
        if getattr(case, "cohort", "")
        == FAILED_RECOVERY
    )

    print(
        f"PRIMARY COHORT CASES = "
        f"{total_primary}"
    )

    print(
        f"DIRECT_FROM_DETERIORATING = "
        f"{direct_total}"
    )

    print(
        f"RECOVERY_FAILED_THEN_DETERIORATING = "
        f"{failed_total}"
    )

    print()

    print(
        "This audit controls direction before comparing "
        "the predecessor cohorts."
    )

    print(
        "Any direction with no cases in one cohort is "
        "not treated as comparable."
    )

    print(
        "Any observed delta is descriptive only."
    )

    print(
        "The current sample remains small."
    )

    print(
        "No result becomes a trading rule."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print_header()

    cases = load_cases()

    print()

    print(
        f"PRIMARY COHORT CASES = "
        f"{len(cases)}"
    )

    print_population(
        cases
    )

    print_direction_summary(
        cases
    )

    print_case_matrix(
        cases
    )

    print_timing_crosscheck(
        cases
    )

    print_overall_control_assessment(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 115)
    print(
        "V13.17 PERSISTENT FAILURE "
        "DIRECTION-CONTROLLED AUDIT COMPLETE"
    )
    print("=" * 115)


if __name__ == "__main__":
    main()
