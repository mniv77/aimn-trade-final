"""
AIMn / KISS V13.17 COMPANION RESEARCH

PF PREDECESSOR SYMBOL-SENSITIVITY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
The direction + state controlled audit found one comparable stratum:

    LONG
    +30m STATE = DETERIORATING

Within that stratum:

    RECOVERY_FAILED_BY_30M
        N=3
        LATER PF=2
        RATE=0.6667

    NO_RECOVERY_FAILURE_BY_30M
        N=5
        LATER PF=1
        RATE=0.2000

    DESCRIPTIVE DELTA
        +0.4667

This audit asks:

    Is that descriptive difference dependent on any one symbol?

METHOD
------
Use the exact same:

    predictor
    outcome
    direction control
    +30m state control

but perform leave-one-symbol-out sensitivity.

PRIMARY STRATUM
---------------
LONG +30m DETERIORATING

For the full stratum and for each symbol removed:

    FAILED N
    FAILED PF
    FAILED RATE

    CLEAN N
    CLEAN PF
    CLEAN RATE

    DELTA = FAILED RATE - CLEAN RATE

IMPORTANT
---------
This does NOT create a statistical test.

This does NOT prove robustness.

With only eight cases in the full stratum, every result remains
descriptive.

No future information is used to define the predictor.

No production code changed.
"""

from __future__ import annotations

from typing import List, Sequence

from kiss import (
    kiss_transition_detector_v5_6_12_13_17_pf_predecessor_enrichment_landmark_audit
    as landmark
)


TARGET_DIRECTION = "LONG"
TARGET_STATE = landmark.DETERIORATING


def safe_rate(
    numerator: int,
    denominator: int,
):
    if denominator == 0:
        return None

    return numerator / denominator


def build_cases():

    return list(
        landmark.build_cases()
    )


def target_cases(
    cases: Sequence[object],
):
    return [
        case
        for case in cases
        if (
            case.eligible
            and case.direction == TARGET_DIRECTION
            and case.landmark_state == TARGET_STATE
        )
    ]


def summarize(
    cases: Sequence[object],
):

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
    else:
        delta = None

    return {
        "failed": failed,
        "clean": clean,
        "failed_pf": failed_pf,
        "clean_pf": clean_pf,
        "failed_rate": failed_rate,
        "clean_rate": clean_rate,
        "delta": delta,
    }


def print_header() -> None:

    print()
    print("=" * 120)
    print(
        "V13.17 PF PREDECESSOR SYMBOL-SENSITIVITY AUDIT"
    )
    print("=" * 120)

    print()
    print(
        "PRIMARY STRATUM:"
    )
    print(
        "  DIRECTION = LONG"
    )
    print(
        "  +30M STATE = DETERIORATING"
    )

    print()
    print(
        "METHOD:"
    )
    print(
        "  Leave one symbol out at a time."
    )

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
        "No future information is used for predictor assignment."
    )

    print(
        "No production code changed."
    )


def print_full_result(
    cases: Sequence[object],
) -> None:

    result = summarize(
        cases
    )

    print()
    print(
        "-" * 120
    )
    print(
        "FULL TARGET STRATUM"
    )
    print(
        "-" * 120
    )

    print(
        f"FAILED N={len(result['failed'])} "
        f"PF={result['failed_pf']} "
        f"RATE="
        f"{'NA' if result['failed_rate'] is None else f'{result['failed_rate']:.4f}'}"
    )

    print(
        f"CLEAN  N={len(result['clean'])} "
        f"PF={result['clean_pf']} "
        f"RATE="
        f"{'NA' if result['clean_rate'] is None else f'{result['clean_rate']:.4f}'}"
    )

    print(
        f"DELTA  = "
        f"{'NA' if result['delta'] is None else f'{result['delta']:+.4f}'}"
    )


def print_exact_cases(
    cases: Sequence[object],
) -> None:

    print()
    print(
        "EXACT TARGET STRATUM CASES"
    )

    ordered = sorted(
        cases,
        key=lambda case: (
            case.symbol,
            case.recovery_failed_by_30m,
            case.outcome,
        ),
    )

    for case in ordered:

        predictor = (
            "FAILED"
            if case.recovery_failed_by_30m
            else "CLEAN"
        )

        print(
            f"  {case.symbol:<6} "
            f"{predictor:<6} "
            f"OUTCOME={case.outcome:<18} "
            f"FIRST_PF="
            f"{('+' + str(case.first_pf_minutes) + 'm') if case.first_pf_minutes is not None else 'NONE'}"
        )


def print_leave_one_out(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 120)
    print(
        "LEAVE-ONE-SYMBOL-OUT SENSITIVITY"
    )
    print("=" * 120)

    symbols = sorted(
        set(
            case.symbol
            for case in cases
        )
    )

    full = summarize(
        cases
    )

    print()
    print(
        "BASELINE"
    )

    print(
        f"  ALL SYMBOLS "
        f"FAILED_N={len(full['failed'])} "
        f"FAILED_PF={full['failed_pf']} "
        f"FAILED_RATE="
        f"{'NA' if full['failed_rate'] is None else f'{full['failed_rate']:.4f}'} "
        f"CLEAN_N={len(full['clean'])} "
        f"CLEAN_PF={full['clean_pf']} "
        f"CLEAN_RATE="
        f"{'NA' if full['clean_rate'] is None else f'{full['clean_rate']:.4f}'} "
        f"DELTA="
        f"{'NA' if full['delta'] is None else f'{full['delta']:+.4f}'}"
    )

    for symbol in symbols:

        reduced = [
            case
            for case in cases
            if case.symbol != symbol
        ]

        result = summarize(
            reduced
        )

        print()
        print(
            f"REMOVE {symbol}"
        )

        print(
            f"  FAILED_N={len(result['failed'])} "
            f"FAILED_PF={result['failed_pf']} "
            f"FAILED_RATE="
            f"{'NA' if result['failed_rate'] is None else f'{result['failed_rate']:.4f}'}"
        )

        print(
            f"  CLEAN_N={len(result['clean'])} "
            f"CLEAN_PF={result['clean_pf']} "
            f"CLEAN_RATE="
            f"{'NA' if result['clean_rate'] is None else f'{result['clean_rate']:.4f}'}"
        )

        print(
            f"  DELTA="
            f"{'NA' if result['delta'] is None else f'{result['delta']:+.4f}'}"
        )

        if result["delta"] is None:

            print(
                "  STATUS = NOT COMPARABLE"
            )

        else:

            print(
                "  STATUS = COMPARABLE DESCRIPTIVELY"
            )


def print_symbol_contribution(
    cases: Sequence[object],
) -> None:

    print()
    print("=" * 120)
    print(
        "SYMBOL CONTRIBUTION"
    )
    print("=" * 120)

    symbols = sorted(
        set(
            case.symbol
            for case in cases
        )
    )

    for symbol in symbols:

        symbol_cases = [
            case
            for case in cases
            if case.symbol == symbol
        ]

        failed = [
            case
            for case in symbol_cases
            if case.recovery_failed_by_30m
        ]

        clean = [
            case
            for case in symbol_cases
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

        print()
        print(
            f"{symbol}"
        )

        print(
            f"  FAILED "
            f"N={len(failed)} "
            f"PF={failed_pf}"
        )

        print(
            f"  CLEAN  "
            f"N={len(clean)} "
            f"PF={clean_pf}"
        )


def print_interpretation(
    cases: Sequence[object],
) -> None:

    full = summarize(
        cases
    )

    symbols = sorted(
        set(
            case.symbol
            for case in cases
        )
    )

    leave_one_out_deltas = []

    for symbol in symbols:

        reduced = [
            case
            for case in cases
            if case.symbol != symbol
        ]

        result = summarize(
            reduced
        )

        if result["delta"] is not None:

            leave_one_out_deltas.append(
                result["delta"]
            )

    print()
    print("=" * 120)
    print(
        "V13.17 PF SYMBOL-SENSITIVITY — INTERPRETATION"
    )
    print("=" * 120)

    print()

    print(
        f"BASELINE DELTA = "
        f"{'NA' if full['delta'] is None else f'{full['delta']:+.4f}'}"
    )

    print(
        f"LEAVE-ONE-OUT COMPARISONS AVAILABLE = "
        f"{len(leave_one_out_deltas)}"
    )

    if leave_one_out_deltas:

        print(
            f"MIN LEAVE-ONE-OUT DELTA = "
            f"{min(leave_one_out_deltas):+.4f}"
        )

        print(
            f"MAX LEAVE-ONE-OUT DELTA = "
            f"{max(leave_one_out_deltas):+.4f}"
        )

        positive_count = sum(
            delta > 0
            for delta in leave_one_out_deltas
        )

        negative_count = sum(
            delta < 0
            for delta in leave_one_out_deltas
        )

        zero_count = sum(
            delta == 0
            for delta in leave_one_out_deltas
        )

        print(
            f"POSITIVE DELTAS = "
            f"{positive_count}"
        )

        print(
            f"NEGATIVE DELTAS = "
            f"{negative_count}"
        )

        print(
            f"ZERO DELTAS     = "
            f"{zero_count}"
        )

    print()

    print(
        "This is a sensitivity check, not a validation test."
    )

    print(
        "A stable sign across leave-one-symbol-out samples "
        "would only support descriptive stability."
    )

    print(
        "It would not establish causality or a trading rule."
    )

    print(
        "The population is still small."
    )

    print(
        "No result becomes an entry, warning, rescue, hold, "
        "or exit rule."
    )

    print(
        "No production code changed."
    )


def main() -> None:

    print_header()

    all_cases = build_cases()

    cases = target_cases(
        all_cases
    )

    print()
    print(
        f"TOTAL V13.17 CASES = "
        f"{len(all_cases)}"
    )

    print(
        f"TARGET STRATUM CASES = "
        f"{len(cases)}"
    )

    print_full_result(
        cases
    )

    print_exact_cases(
        cases
    )

    print_symbol_contribution(
        cases
    )

    print_leave_one_out(
        cases
    )

    print_interpretation(
        cases
    )

    print()
    print("=" * 120)
    print(
        "V13.17 PF PREDECESSOR SYMBOL-SENSITIVITY AUDIT COMPLETE"
    )
    print("=" * 120)


if __name__ == "__main__":
    main()
