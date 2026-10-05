"""
KISS V13.17 — GOOGL MOTIF REPLICATION AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING

QUESTION
-------
Do the five newly added GOOGL trajectory cases reproduce the same
canonical trajectory motifs seen across the original seven-symbol
V13.17 population?

This is a companion audit to V13.17.
It does NOT create a new trading rule or alter the V13.17 methodology.

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
- Uses the existing V13.17 research path builder.
- Uses unique trajectory cases.
- Evaluates motif history only from information available through
  the current checkpoint.
- Keeps direction and current state visible.
- For controlled comparisons, requires motif PRESENT and ABSENT
  within the same symbol + direction + current state + checkpoint.
- Future return is measured FROM the checkpoint.
- Checkpoint observations are never counted as separate trajectory cases.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple, Any

import importlib


# ---------------------------------------------------------------------------
# Existing V13.17 implementation
# ---------------------------------------------------------------------------

V1317_MODULE_NAME = (
    "kiss.kiss_transition_detector_v5_6_12_13_17_case_aware_validation"
)

v1317 = importlib.import_module(V1317_MODULE_NAME)


# ---------------------------------------------------------------------------
# Research configuration
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

MOTIFS = {
    "DR_REC": (
        "DETERIORATING",
        "RECOVERING",
    ),
    "DR_REC_DR": (
        "DETERIORATING",
        "RECOVERING",
        "DETERIORATING",
    ),
    "REC_NEU_DET": (
        "RECOVERING",
        "NEUTRAL",
        "DETERIORATING",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def avg(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def fmt(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{value:+.3f}%"


def fmt_time(value: Any) -> str:
    if value is None:
        return "NA"
    return str(value)


def case_key(path: Any) -> Tuple[str, str, Any]:
    return (
        path.symbol,
        path.direction,
        path.opposite_time,
    )


def points_through(path: Any, checkpoint: int) -> List[Any]:
    return [
        point
        for point in path.points
        if point.minutes <= checkpoint
    ]


def point_at(path: Any, minutes: int) -> Optional[Any]:
    for point in path.points:
        if point.minutes == minutes:
            return point
    return None


def sequence_through(path: Any, checkpoint: int) -> List[str]:
    return [
        point.state
        for point in points_through(path, checkpoint)
        if point.state
    ]


def has_exact_motif(
    sequence: Sequence[str],
    motif: Sequence[str],
) -> bool:
    if len(sequence) < len(motif):
        return False

    width = len(motif)

    for i in range(0, len(sequence) - width + 1):
        if tuple(sequence[i:i + width]) == tuple(motif):
            return True

    return False


def motif_present(
    path: Any,
    checkpoint: int,
    motif_name: str,
) -> bool:
    sequence = sequence_through(path, checkpoint)

    if motif_name == "PERSISTENT_FAILURE_HISTORY":
        return "PERSISTENT_FAILURE" in sequence

    motif = MOTIFS[motif_name]
    return has_exact_motif(sequence, motif)


def future_return_from_checkpoint(
    direction: str,
    checkpoint_point: Any,
    future_point: Any,
) -> Optional[float]:
    """
    Reconstruct signed return FROM checkpoint TO future point.

    Existing V13 logic stores return_pct relative to original decision price.

    LONG:
        factor = 1 + return_pct / 100

    SHORT:
        factor = 1 - return_pct / 100

    We then calculate the signed return of the future price relative
    to the checkpoint price.
    """

    if checkpoint_point.return_pct is None:
        return None

    if future_point.return_pct is None:
        return None

    try:
        cp_ret = float(checkpoint_point.return_pct)
        fut_ret = float(future_point.return_pct)
    except (TypeError, ValueError):
        return None

    if direction == "LONG":
        cp_factor = 1.0 + cp_ret / 100.0
        fut_factor = 1.0 + fut_ret / 100.0

        if cp_factor == 0:
            return None

        ratio = fut_factor / cp_factor
        return (ratio - 1.0) * 100.0

    if direction == "SHORT":
        cp_factor = 1.0 - cp_ret / 100.0
        fut_factor = 1.0 - fut_ret / 100.0

        if cp_factor == 0:
            return None

        ratio = fut_factor / cp_factor

        # For a SHORT, falling price is positive signed return.
        return (1.0 - ratio) * 100.0

    return None


# ---------------------------------------------------------------------------
# Build unique V13.17 research cases
# ---------------------------------------------------------------------------

def build_unique_cases() -> List[Any]:
    print("=" * 80)
    print("V13.17 — GOOGL MOTIF REPLICATION AUDIT")
    print("=" * 80)
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print()

    paths = v1317.build_v1317_research_paths()

    by_key: Dict[Tuple[str, str, Any], Any] = {}

    for path in paths:
        key = case_key(path)

        if key not in by_key:
            by_key[key] = path

    unique = list(by_key.values())

    print(f"RAW TRAJECTORY PATHS:    {len(paths)}")
    print(f"UNIQUE TRAJECTORY CASES: {len(unique)}")
    print()

    return unique


# ---------------------------------------------------------------------------
# Population summary
# ---------------------------------------------------------------------------

def population_summary(cases: Sequence[Any]) -> None:
    print("=" * 80)
    print("POPULATION / CASE SUMMARY")
    print("=" * 80)

    by_symbol: Dict[str, List[Any]] = defaultdict(list)

    for path in cases:
        by_symbol[path.symbol].append(path)

    total = 0

    for symbol in SYMBOLS:
        rows = by_symbol.get(symbol, [])

        long_n = sum(1 for path in rows if path.direction == "LONG")
        short_n = sum(1 for path in rows if path.direction == "SHORT")

        print(
            f"{symbol:5s} "
            f"CASES={len(rows):2d} "
            f"LONG={long_n:2d} "
            f"SHORT={short_n:2d}"
        )

        total += len(rows)

    print("-" * 80)
    print(f"TOTAL UNIQUE CASES: {total}")
    print()


# ---------------------------------------------------------------------------
# Motif prevalence by symbol
# ---------------------------------------------------------------------------

def motif_prevalence_by_symbol(cases: Sequence[Any]) -> None:
    print("=" * 80)
    print("MOTIF PREVALENCE BY SYMBOL")
    print("=" * 80)
    print(
        "Counts are UNIQUE CASES with the motif present by the checkpoint."
    )
    print(
        "A case can appear at multiple checkpoints, but is never duplicated"
    )
    print(
        "within one symbol + checkpoint + motif cell."
    )
    print()

    motif_names = (
        "DR_REC",
        "DR_REC_DR",
        "REC_NEU_DET",
        "PERSISTENT_FAILURE_HISTORY",
    )

    for checkpoint in CHECKPOINTS:
        print(f"CHECKPOINT +{checkpoint}m")

        for symbol in SYMBOLS:
            symbol_cases = [
                path
                for path in cases
                if path.symbol == symbol
            ]

            values = []

            for motif_name in motif_names:
                count = sum(
                    1
                    for path in symbol_cases
                    if motif_present(path, checkpoint, motif_name)
                )

                values.append(f"{motif_name}={count}")

            print(
                f"  {symbol:5s} CASES={len(symbol_cases):2d} "
                + " ".join(values)
            )

        print()


# ---------------------------------------------------------------------------
# Detailed GOOGL case ledger
# ---------------------------------------------------------------------------

def googl_case_ledger(cases: Sequence[Any]) -> None:
    print("=" * 80)
    print("GOOGL CASE LEDGER")
    print("=" * 80)

    googl_cases = [
        path
        for path in cases
        if path.symbol == "GOOGL"
    ]

    if not googl_cases:
        print("ERROR: No GOOGL cases found.")
        print()
        return

    for index, path in enumerate(
        sorted(
            googl_cases,
            key=lambda p: (
                p.opposite_time,
                p.direction,
            ),
        ),
        start=1,
    ):
        print("-" * 80)
        print(
            f"GOOGL CASE {index:02d}  "
            f"{path.direction}  "
            f"OPPOSITE={fmt_time(path.opposite_time)}"
        )

        for checkpoint in CHECKPOINTS:
            point = point_at(path, checkpoint)

            if point is None:
                continue

            sequence = sequence_through(path, checkpoint)

            dr_rec = motif_present(
                path,
                checkpoint,
                "DR_REC",
            )

            dr_rec_dr = motif_present(
                path,
                checkpoint,
                "DR_REC_DR",
            )

            rec_neu_det = motif_present(
                path,
                checkpoint,
                "REC_NEU_DET",
            )

            pf_hist = motif_present(
                path,
                checkpoint,
                "PERSISTENT_FAILURE_HISTORY",
            )

            print(
                f"  +{checkpoint:02d}m "
                f"STATE={point.state:18s} "
                f"RET={fmt(point.return_pct):>9s} "
                f"DR_REC={'Y' if dr_rec else 'N'} "
                f"DR_REC_DR={'Y' if dr_rec_dr else 'N'} "
                f"REC_NEU_DET={'Y' if rec_neu_det else 'N'} "
                f"PF_HIST={'Y' if pf_hist else 'N'}"
            )

            print(
                f"      SEQUENCE="
                f"{' -> '.join(sequence) if sequence else 'NONE'}"
            )

    print()


# ---------------------------------------------------------------------------
# Symbol-level controlled replication
# ---------------------------------------------------------------------------

def controlled_symbol_replication(cases: Sequence[Any]) -> None:
    print("=" * 80)
    print("SYMBOL-LEVEL CONTROLLED MOTIF REPLICATION")
    print("=" * 80)
    print(
        "CONTROL = SYMBOL + DIRECTION + CURRENT STATE + CHECKPOINT"
    )
    print(
        "COMPARE = MOTIF PRESENT vs MOTIF ABSENT"
    )
    print(
        "This is deliberately stricter than the pooled V13.17 comparison."
    )
    print()

    motif_names = (
        "DR_REC",
        "DR_REC_DR",
        "REC_NEU_DET",
        "PERSISTENT_FAILURE_HISTORY",
    )

    # Track sign consistency of valid symbol-level deltas.
    sign_summary: Dict[str, List[float]] = defaultdict(list)

    valid_rows = []

    for symbol in SYMBOLS:
        symbol_cases = [
            path
            for path in cases
            if path.symbol == symbol
        ]

        for checkpoint in CHECKPOINTS:
            rows = []

            for path in symbol_cases:
                cp = point_at(path, checkpoint)

                if cp is None:
                    continue

                rows.append((path, cp))

            if not rows:
                continue

            control_groups = defaultdict(
                lambda: {
                    "P": [],
                    "A": [],
                }
            )

            for path, cp in rows:
                control_key = (
                    path.direction,
                    cp.state,
                )

                for motif_name in motif_names:
                    key = (
                        motif_name,
                        control_key,
                    )

                    present = motif_present(
                        path,
                        checkpoint,
                        motif_name,
                    )

                    if present:
                        control_groups[key]["P"].append(
                            (path, cp)
                        )
                    else:
                        control_groups[key]["A"].append(
                            (path, cp)
                        )

            for motif_name in motif_names:
                for (m_name, control_key), groups in control_groups.items():

                    if m_name != motif_name:
                        continue

                    present_rows = groups["P"]
                    absent_rows = groups["A"]

                    if not present_rows or not absent_rows:
                        continue

                    direction, current_state = control_key

                    for horizon in FUTURE_HORIZONS:
                        present_returns = []
                        absent_returns = []

                        for path, cp in present_rows:
                            future = point_at(
                                path,
                                checkpoint + horizon,
                            )

                            if future is not None:
                                value = future_return_from_checkpoint(
                                    path.direction,
                                    cp,
                                    future,
                                )

                                if value is not None:
                                    present_returns.append(value)

                        for path, cp in absent_rows:
                            future = point_at(
                                path,
                                checkpoint + horizon,
                            )

                            if future is not None:
                                value = future_return_from_checkpoint(
                                    path.direction,
                                    cp,
                                    future,
                                )

                                if value is not None:
                                    absent_returns.append(value)

                        if not present_returns or not absent_returns:
                            continue

                        p_avg = avg(present_returns)
                        a_avg = avg(absent_returns)

                        if p_avg is None or a_avg is None:
                            continue

                        delta = p_avg - a_avg

                        valid_rows.append(
                            (
                                symbol,
                                checkpoint,
                                horizon,
                                direction,
                                current_state,
                                motif_name,
                                len(present_returns),
                                len(absent_returns),
                                p_avg,
                                a_avg,
                                delta,
                            )
                        )

                        sign_summary[motif_name].append(delta)

    if not valid_rows:
        print("NO SYMBOL-LEVEL TWO-SIDED COMPARISONS AVAILABLE.")
        print()
        return

    for row in valid_rows:
        (
            symbol,
            checkpoint,
            horizon,
            direction,
            current_state,
            motif_name,
            p_n,
            a_n,
            p_avg,
            a_avg,
            delta,
        ) = row

        print(
            f"{symbol:5s} "
            f"CP=+{checkpoint:02d}m "
            f"H=+{horizon:02d}m "
            f"{direction:5s} "
            f"{current_state:18s} "
            f"{motif_name:24s} "
            f"P={p_n:2d} "
            f"A={a_n:2d} "
            f"P_AVG={fmt(p_avg):>9s} "
            f"A_AVG={fmt(a_avg):>9s} "
            f"DELTA={fmt(delta):>9s}"
        )

    print()
    print("=" * 80)
    print("REPLICATION SIGN SUMMARY")
    print("=" * 80)

    for motif_name in (
        "DR_REC",
        "DR_REC_DR",
        "REC_NEU_DET",
        "PERSISTENT_FAILURE_HISTORY",
    ):
        values = sign_summary.get(motif_name, [])

        positives = sum(1 for value in values if value > 0)
        negatives = sum(1 for value in values if value < 0)
        zeros = sum(1 for value in values if value == 0)

        print(
            f"{motif_name:24s} "
            f"VALID_COMPARISONS={len(values):2d} "
            f"POS={positives:2d} "
            f"NEG={negatives:2d} "
            f"ZERO={zeros:2d}"
        )

    print()


# ---------------------------------------------------------------------------
# Focused GOOGL two-sided checks
# ---------------------------------------------------------------------------

def focused_googl_checks(cases: Sequence[Any]) -> None:
    print("=" * 80)
    print("GOOGL TWO-SIDED CONTROL CHECKS")
    print("=" * 80)

    googl_cases = [
        path
        for path in cases
        if path.symbol == "GOOGL"
    ]

    motif_names = (
        "DR_REC",
        "DR_REC_DR",
        "REC_NEU_DET",
        "PERSISTENT_FAILURE_HISTORY",
    )

    any_valid = False

    for checkpoint in CHECKPOINTS:
        rows = []

        for path in googl_cases:
            cp = point_at(path, checkpoint)

            if cp is not None:
                rows.append((path, cp))

        if not rows:
            continue

        for motif_name in motif_names:
            grouped = defaultdict(lambda: {"P": [], "A": []})

            for path, cp in rows:
                key = (
                    path.direction,
                    cp.state,
                )

                if motif_present(
                    path,
                    checkpoint,
                    motif_name,
                ):
                    grouped[key]["P"].append((path, cp))
                else:
                    grouped[key]["A"].append((path, cp))

            for (direction, state), groups in grouped.items():

                if not groups["P"] or not groups["A"]:
                    continue

                any_valid = True

                print(
                    f"GOOGL CP=+{checkpoint:02d}m "
                    f"{direction:5s} "
                    f"{state:18s} "
                    f"{motif_name:24s} "
                    f"P_CASES={len(groups['P'])} "
                    f"A_CASES={len(groups['A'])}"
                )

                for horizon in FUTURE_HORIZONS:
                    p_values = []
                    a_values = []

                    for path, cp in groups["P"]:
                        future = point_at(
                            path,
                            checkpoint + horizon,
                        )

                        if future is not None:
                            value = future_return_from_checkpoint(
                                path.direction,
                                cp,
                                future,
                            )

                            if value is not None:
                                p_values.append(value)

                    for path, cp in groups["A"]:
                        future = point_at(
                            path,
                            checkpoint + horizon,
                        )

                        if future is not None:
                            value = future_return_from_checkpoint(
                                path.direction,
                                cp,
                                future,
                            )

                            if value is not None:
                                a_values.append(value)

                    if p_values and a_values:
                        p_avg = avg(p_values)
                        a_avg = avg(a_values)
                        delta = (
                            p_avg - a_avg
                            if p_avg is not None and a_avg is not None
                            else None
                        )

                        print(
                            f"    H={horizon:02d}m "
                            f"P_N={len(p_values):2d} "
                            f"A_N={len(a_values):2d} "
                            f"P_AVG={fmt(p_avg):>9s} "
                            f"A_AVG={fmt(a_avg):>9s} "
                            f"DELTA={fmt(delta):>9s}"
                        )
                    else:
                        print(
                            f"    H={horizon:02d}m "
                            f"NO TWO-SIDED FUTURE RETURN"
                        )

    if not any_valid:
        print(
            "No GOOGL checkpoint produced a two-sided "
            "present-vs-absent comparison within the same "
            "direction and current state."
        )

    print()


# ---------------------------------------------------------------------------
# Final interpretation
# ---------------------------------------------------------------------------

def interpretation(cases: Sequence[Any]) -> None:
    googl_n = sum(
        1
        for path in cases
        if path.symbol == "GOOGL"
    )

    print("=" * 80)
    print("V13.17 GOOGL REPLICATION AUDIT — INTERPRETATION")
    print("=" * 80)
    print()
    print(
        f"UNIQUE TRAJECTORY CASES IN EXPANDED POPULATION: {len(cases)}"
    )
    print(
        f"GOOGL UNIQUE TRAJECTORY CASES: {googl_n}"
    )
    print()
    print(
        "This audit asks whether the trajectory motifs replicate "
        "across symbols."
    )
    print()
    print(
        "A motif appearing in GOOGL is NOT sufficient to validate it."
    )
    print(
        "A motif appearing in several symbols with consistent "
        "controlled behavior would be stronger evidence."
    )
    print()
    print(
        "Symbol-level samples remain small and may produce many "
        "NO TWO-SIDED comparisons."
    )
    print()
    print(
        "Checkpoint observations are not independent trajectory cases."
    )
    print()
    print(
        "NO ENTRY / HOLD / WARNING / EXIT RULE IS CREATED."
    )
    print(
        "NO PRODUCTION ENGINE CHANGE."
    )
    print(
        "NO AI TRAINING."
    )
    print()
    print("=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cases = build_unique_cases()

    population_summary(cases)
    motif_prevalence_by_symbol(cases)
    googl_case_ledger(cases)
    focused_googl_checks(cases)
    controlled_symbol_replication(cases)
    interpretation(cases)


if __name__ == "__main__":
    main()
