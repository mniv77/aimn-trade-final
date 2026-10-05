"""
KISS V13.17 COMPANION RESEARCH
MOTIF ONSET / TIMING AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
--------
When does each canonical motif FIRST become visible?

A motif can be interesting historically but useless operationally
if it appears only after substantial deterioration has already occurred.

CANONICAL MOTIFS
----------------
1. DETERIORATING -> RECOVERING
2. DETERIORATING -> RECOVERING -> DETERIORATING
3. RECOVERING -> NEUTRAL -> DETERIORATING
4. PERSISTENT_FAILURE HISTORY

CASE KEY
--------
(symbol, direction, opposite_time)

METHODOLOGY
-----------
- Reuses the existing V13.17 trajectory cases.
- Uses the expanded 8-symbol / 28-case population.
- Uses completed checkpoint observations only.
- Finds the EARLIEST checkpoint where each motif becomes present.
- Future return is measured FROM THAT MOTIF-ONSET CHECKPOINT.
- Motifs may overlap; each motif is analyzed independently.
- This is timing/replication research, NOT a trading rule.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple
import importlib


# ---------------------------------------------------------------------------
# Reuse the existing V13.17 companion methodology
# ---------------------------------------------------------------------------

rep = importlib.import_module(
    "kiss.kiss_transition_detector_v5_6_12_13_17_googl_replication_audit"
)

v1317 = importlib.import_module(
    "kiss.kiss_transition_detector_v5_6_12_13_17_case_aware_validation"
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

CHECKPOINTS = (15, 30, 45, 60)
FUTURE_HORIZONS = (15, 30, 45)

MOTIF_NAMES = (
    "DR_REC",
    "DR_REC_DR",
    "REC_NEU_DET",
    "PERSISTENT_FAILURE_HISTORY",
)


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{value:+.3f}%"


def point_at(path: Any, minutes: int) -> Optional[Any]:
    return rep.point_at(path, minutes)


def motif_present(
    path: Any,
    checkpoint: int,
    motif_name: str,
) -> bool:
    return rep.motif_present(
        path,
        checkpoint,
        motif_name,
    )


def sequence_through(
    path: Any,
    checkpoint: int,
) -> List[str]:
    return rep.sequence_through(
        path,
        checkpoint,
    )


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


def find_first_onset(
    path: Any,
    motif_name: str,
) -> Optional[int]:
    """
    Return the earliest checkpoint at which the motif exists.
    """

    for checkpoint in CHECKPOINTS:
        if motif_present(
            path,
            checkpoint,
            motif_name,
        ):
            return checkpoint

    return None


def onset_record(
    path: Any,
    motif_name: str,
) -> Optional[Dict[str, Any]]:

    onset = find_first_onset(
        path,
        motif_name,
    )

    if onset is None:
        return None

    point = point_at(
        path,
        onset,
    )

    if point is None:
        return None

    returns = {}

    for horizon in FUTURE_HORIZONS:
        future = point_at(
            path,
            onset + horizon,
        )

        if future is None:
            returns[horizon] = None
            continue

        returns[horizon] = future_return_from_checkpoint(
            path.direction,
            point,
            future,
        )

    return {
        "symbol": path.symbol,
        "direction": path.direction,
        "opposite_time": path.opposite_time,
        "motif": motif_name,
        "onset": onset,
        "state": point.state,
        "return_pct": point.return_pct,
        "sequence": sequence_through(
            path,
            onset,
        ),
        "future": returns,
    }


def build_cases() -> List[Any]:
    paths = rep.build_unique_cases()

    unique = {}

    for path in paths:
        key = (
            path.symbol,
            path.direction,
            path.opposite_time,
        )

        unique[key] = path

    return list(unique.values())


def print_population(cases: Sequence[Any]) -> None:
    print("=" * 80)
    print("V13.17 MOTIF ONSET / TIMING AUDIT")
    print("=" * 80)
    print()
    print(f"UNIQUE CASES: {len(cases)}")

    by_symbol = defaultdict(int)

    for path in cases:
        by_symbol[path.symbol] += 1

    print()

    for symbol in SYMBOLS:
        print(
            f"{symbol:5s} CASES={by_symbol[symbol]:2d}"
        )

    print()


def print_onset_summary(
    cases: Sequence[Any],
) -> List[Dict[str, Any]]:

    print("=" * 80)
    print("FIRST MOTIF ONSET SUMMARY")
    print("=" * 80)

    records = []

    for motif_name in MOTIF_NAMES:

        motif_records = []

        for path in cases:
            record = onset_record(
                path,
                motif_name,
            )

            if record is not None:
                motif_records.append(record)
                records.append(record)

        print()
        print(
            f"MOTIF: {motif_name}"
        )

        if not motif_records:
            print("  NO CASES WITH THIS MOTIF")
            continue

        onset_counts = defaultdict(int)
        symbol_set = set()

        for record in motif_records:
            onset_counts[record["onset"]] += 1
            symbol_set.add(record["symbol"])

        print(
            f"  CASES WITH MOTIF: {len(motif_records)}"
        )

        print(
            f"  SYMBOLS WITH MOTIF: {len(symbol_set)}"
        )

        print(
            "  SYMBOL LIST: "
            + ", ".join(sorted(symbol_set))
        )

        for checkpoint in CHECKPOINTS:
            n = onset_counts.get(
                checkpoint,
                0,
            )

            if n:
                print(
                    f"  FIRST ONSET +{checkpoint:02d}m: {n}"
                )

    print()

    return records


def print_case_level_onsets(
    records: Sequence[Dict[str, Any]],
) -> None:

    print("=" * 80)
    print("CASE-LEVEL MOTIF ONSET")
    print("=" * 80)

    ordered = sorted(
        records,
        key=lambda r: (
            r["symbol"],
            r["opposite_time"],
            r["direction"],
            r["motif"],
        ),
    )

    for record in ordered:

        sequence = record["sequence"]

        print("-" * 80)
        print(
            f"{record['symbol']:5s} "
            f"{record['direction']:5s} "
            f"OPPOSITE={record['opposite_time']} "
            f"MOTIF={record['motif']}"
        )

        print(
            f"  FIRST ONSET=+{record['onset']}m "
            f"STATE={record['state']} "
            f"RETURN={fmt_pct(record['return_pct'])}"
        )

        print(
            "  SEQUENCE="
            + (
                " -> ".join(sequence)
                if sequence
                else "NONE"
            )
        )

        for horizon in FUTURE_HORIZONS:
            value = record["future"].get(horizon)

            print(
                f"  FUTURE +{horizon:02d}m "
                f"FROM ONSET: {fmt_pct(value)}"
            )


def print_onset_by_symbol(
    records: Sequence[Dict[str, Any]],
) -> None:

    print()
    print("=" * 80)
    print("MOTIF ONSET BY SYMBOL")
    print("=" * 80)

    by_symbol = defaultdict(
        lambda: defaultdict(list)
    )

    for record in records:
        by_symbol[
            record["symbol"]
        ][
            record["motif"]
        ].append(record)

    for symbol in SYMBOLS:

        print()
        print(
            f"{symbol:5s}"
        )

        for motif_name in MOTIF_NAMES:

            motif_records = by_symbol[symbol].get(
                motif_name,
                [],
            )

            if not motif_records:
                print(
                    f"  {motif_name:30s} NONE"
                )
                continue

            onsets = [
                r["onset"]
                for r in motif_records
            ]

            print(
                f"  {motif_name:30s} "
                f"N={len(onsets):2d} "
                f"ONSETS={onsets}"
            )


def print_goo_gl_timing(
    records: Sequence[Dict[str, Any]],
) -> None:

    print()
    print("=" * 80)
    print("GOOGL MOTIF TIMING")
    print("=" * 80)

    googl = [
        r
        for r in records
        if r["symbol"] == "GOOGL"
    ]

    for motif_name in MOTIF_NAMES:

        rows = [
            r
            for r in googl
            if r["motif"] == motif_name
        ]

        print()

        print(
            f"MOTIF: {motif_name}"
        )

        if not rows:
            print(
                "  GOOGL: NOT OBSERVED"
            )
            continue

        for record in rows:

            print(
                f"  {record['direction']:5s} "
                f"OPPOSITE={record['opposite_time']} "
                f"FIRST_ONSET=+{record['onset']}m "
                f"STATE={record['state']} "
                f"RETURN={fmt_pct(record['return_pct'])}"
            )

            for horizon in FUTURE_HORIZONS:

                value = record["future"].get(
                    horizon
                )

                if value is not None:
                    print(
                        f"      FUTURE +{horizon}m "
                        f"FROM ONSET={fmt_pct(value)}"
                    )


def print_lateness(
    records: Sequence[Dict[str, Any]],
) -> None:

    print()
    print("=" * 80)
    print("MOTIF TIMING / LATENESS")
    print("=" * 80)

    for motif_name in MOTIF_NAMES:

        rows = [
            r
            for r in records
            if r["motif"] == motif_name
        ]

        if not rows:
            print(
                f"{motif_name:30s} NO OBSERVATIONS"
            )
            continue

        early = sum(
            1
            for r in rows
            if r["onset"] == 15
        )

        medium = sum(
            1
            for r in rows
            if r["onset"] == 30
        )

        late = sum(
            1
            for r in rows
            if r["onset"] in (45, 60)
        )

        avg_onset = (
            sum(r["onset"] for r in rows)
            / len(rows)
        )

        print(
            f"{motif_name:30s} "
            f"N={len(rows):2d} "
            f"+15={early:2d} "
            f"+30={medium:2d} "
            f"+45/+60={late:2d} "
            f"AVG_ONSET=+{avg_onset:.1f}m"
        )


def print_future_return_summary(
    records: Sequence[Dict[str, Any]],
) -> None:

    print()
    print("=" * 80)
    print("FUTURE RETURN FROM FIRST MOTIF ONSET")
    print("=" * 80)

    for motif_name in MOTIF_NAMES:

        rows = [
            r
            for r in records
            if r["motif"] == motif_name
        ]

        print()
        print(
            f"MOTIF: {motif_name}"
        )

        for horizon in FUTURE_HORIZONS:

            values = [
                r["future"].get(horizon)
                for r in rows
                if r["future"].get(horizon) is not None
            ]

            if not values:
                print(
                    f"  +{horizon:02d}m N=0"
                )
                continue

            average = sum(values) / len(values)

            negative = sum(
                1
                for value in values
                if value < 0
            )

            positive = sum(
                1
                for value in values
                if value > 0
            )

            print(
                f"  +{horizon:02d}m "
                f"N={len(values):2d} "
                f"AVG={fmt_pct(average):>9s} "
                f"NEG={negative:2d} "
                f"POS={positive:2d}"
            )


def interpretation(
    cases: Sequence[Any],
    records: Sequence[Dict[str, Any]],
) -> None:

    print()
    print("=" * 80)
    print("INTERPRETATION")
    print("=" * 80)
    print()

    print(
        f"EXPANDED UNIQUE CASES: {len(cases)}"
    )

    googl_cases = sum(
        1
        for path in cases
        if path.symbol == "GOOGL"
    )

    print(
        f"GOOGL CASES: {googl_cases}"
    )

    print()

    print(
        "The primary question is TIMING:"
    )

    print(
        "Does a motif appear early enough to add "
        "information, or only after deterioration "
        "is already visible?"
    )

    print()

    print(
        "PERSISTENT_FAILURE HISTORY is treated separately "
        "because it is a history-presence condition rather "
        "than a multi-state transition sequence."
    )

    print()

    print(
        "No motif is promoted to an entry, hold, warning, "
        "or exit rule."
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
    print("MOTIF ONSET / TIMING AUDIT COMPLETE")
    print("=" * 80)


def main() -> None:

    cases = build_cases()

    print_population(cases)

    records = print_onset_summary(
        cases
    )

    print_case_level_onsets(
        records
    )

    print_onset_by_symbol(
        records
    )

    print_goo_gl_timing(
        records
    )

    print_lateness(
        records
    )

    print_future_return_summary(
        records
    )

    interpretation(
        cases,
        records
    )


if __name__ == "__main__":
    main()
