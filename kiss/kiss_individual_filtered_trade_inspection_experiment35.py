#!/usr/bin/env python3
"""
AIMn KISS - Experiment #35
Individual Filtered Trade Inspection

RESEARCH ONLY.

Purpose
-------
Inspect the ACTUAL individual transitions removed by increasing the
trailing entry threshold.

Primary inspection groups:

    0.25% -> 0.50%
    0.50% -> 0.75%

Experiment #34 already separated the filtered population into winners
and losers.

This experiment does NOT:
    - change the strategy
    - optimize parameters
    - choose a threshold
    - train AI
    - place orders

It simply prints the individual cases so we can study the actual
market trajectories.

The goal is to identify whether there are recurring differences between:

    FILTERED WINNERS
    FILTERED LOSERS

without prematurely converting observations into rules.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    ROOT
    / "kiss"
    / "results"
    / "exp34_filtered_winner_loser"
    / "filtered_winners.csv"
)

LOSERS_FILE = (
    ROOT
    / "kiss"
    / "results"
    / "exp34_filtered_winner_loser"
    / "filtered_losers.csv"
)

OUTPUT_DIR = (
    ROOT
    / "kiss"
    / "results"
    / "exp35_individual_filtered_trade_inspection"
)

OUTPUT_ALL = OUTPUT_DIR / "individual_filtered_trades.csv"


INSPECTION_STEPS = [
    (0.25, 0.50),
    (0.50, 0.75),
]


def fmt(value, digits=3):
    if pd.isna(value):
        return "NA"

    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_bool(value):
    if pd.isna(value):
        return "NA"

    text = str(value).strip().lower()

    if text == "true":
        return "YES"

    if text == "false":
        return "NO"

    return str(value)


def load_files():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Winners file not found:\n{INPUT_FILE}"
        )

    if not LOSERS_FILE.exists():
        raise FileNotFoundError(
            f"Losers file not found:\n{LOSERS_FILE}"
        )

    winners = pd.read_csv(INPUT_FILE)
    losers = pd.read_csv(LOSERS_FILE)

    winners["classification"] = "WINNER"
    losers["classification"] = "LOSER"

    return winners, losers


def prepare(df):
    numeric_columns = [
        "FILTERED_FROM_TRAIL_PCT",
        "FILTERED_AT_TRAIL_PCT",
        "FILTERED_PREV_PNL_PCT",
        "v_depth_pct",
        "time_to_extreme_min",
        "recovery_from_extreme_pct",
        "recovery_time_from_extreme_min",
        "recovery_speed_pct_per_min",
        "near_extreme_dwell_min",
        "max_post_recovery_favorable_pct",
        "max_favorable_from_transition_pct",
        "max_adverse_from_transition_pct",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


def print_case(row, number):
    print()
    print("-" * 100)
    print(f"CASE #{number}")
    print("-" * 100)

    print(
        f"{row['symbol']}  "
        f"{row['direction']}  "
        f"{row['transition_time_utc']}"
    )

    print(
        f"Classification : {row['classification']}"
    )

    print(
        f"Filtered       : "
        f"{fmt(row['FILTERED_FROM_TRAIL_PCT'], 2)}% "
        f"-> "
        f"{fmt(row['FILTERED_AT_TRAIL_PCT'], 2)}%"
    )

    print(
        f"Previous P&L   : "
        f"{fmt(row['FILTERED_PREV_PNL_PCT'], 4)}%"
    )

    print()
    print("RAW V GEOMETRY")

    print(
        f"  V depth                    : "
        f"{fmt(row['v_depth_pct'], 4)}%"
    )

    print(
        f"  Time to extreme             : "
        f"{fmt(row['time_to_extreme_min'], 1)} min"
    )

    print(
        f"  Recovery from extreme      : "
        f"{fmt(row['recovery_from_extreme_pct'], 4)}%"
    )

    print(
        f"  Recovery time              : "
        f"{fmt(row['recovery_time_from_extreme_min'], 1)} min"
    )

    print(
        f"  Recovery speed             : "
        f"{fmt(row['recovery_speed_pct_per_min'], 4)}%/min"
    )

    print(
        f"  Near-extreme dwell         : "
        f"{fmt(row['near_extreme_dwell_min'], 1)} min"
    )

    print(
        f"  Post-recovery favorable    : "
        f"{fmt(row['max_post_recovery_favorable_pct'], 4)}%"
    )

    print(
        f"  Max favorable from trans.  : "
        f"{fmt(row['max_favorable_from_transition_pct'], 4)}%"
    )

    print(
        f"  Max adverse from trans.    : "
        f"{fmt(row['max_adverse_from_transition_pct'], 4)}%"
    )

    print()
    print("RECOVERY")

    print(
        f"  Reached recovery           : "
        f"{fmt_bool(row['reached_recovery'])}"
    )

    print(
        f"  Reached favorable          : "
        f"{fmt_bool(row['reached_favorable'])}"
    )


def make_inspection_table(winners, losers):
    frames = []

    for df in [winners, losers]:
        frames.append(df)

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    columns = [
        "case_id",
        "symbol",
        "direction",
        "transition_time_utc",
        "classification",
        "FILTERED_FROM_TRAIL_PCT",
        "FILTERED_AT_TRAIL_PCT",
        "FILTERED_PREV_PNL_PCT",
        "v_depth_pct",
        "time_to_extreme_min",
        "recovery_from_extreme_pct",
        "recovery_time_from_extreme_min",
        "recovery_speed_pct_per_min",
        "near_extreme_dwell_min",
        "max_post_recovery_favorable_pct",
        "max_favorable_from_transition_pct",
        "max_adverse_from_transition_pct",
        "reached_recovery",
        "reached_favorable",
    ]

    columns = [
        column
        for column in columns
        if column in combined.columns
    ]

    out = combined[columns].copy()

    out = out.sort_values(
        [
            "FILTERED_FROM_TRAIL_PCT",
            "FILTERED_AT_TRAIL_PCT",
            "classification",
            "symbol",
            "transition_time_utc",
        ]
    )

    return out


def main():
    print("=" * 100)
    print("EXPERIMENT #35 INDIVIDUAL FILTERED TRADE INSPECTION")
    print("=" * 100)
    print("RESEARCH ONLY")
    print()

    winners, losers = load_files()

    winners = prepare(winners)
    losers = prepare(losers)

    print(
        f"[LOAD] Winners: {len(winners)}"
    )

    print(
        f"[LOAD] Losers : {len(losers)}"
    )

    print()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    inspection = make_inspection_table(
        winners,
        losers,
    )

    inspection.to_csv(
        OUTPUT_ALL,
        index=False,
    )

    case_number = 0

    for from_trail, at_trail in INSPECTION_STEPS:

        print()
        print("=" * 100)
        print(
            f"FILTER STEP: {from_trail:.2f}% -> {at_trail:.2f}%"
        )
        print("=" * 100)

        winner_step = winners[
            (winners["FILTERED_FROM_TRAIL_PCT"] == from_trail)
            & (winners["FILTERED_AT_TRAIL_PCT"] == at_trail)
        ].copy()

        loser_step = losers[
            (losers["FILTERED_FROM_TRAIL_PCT"] == from_trail)
            & (losers["FILTERED_AT_TRAIL_PCT"] == at_trail)
        ].copy()

        print()
        print(
            f"FILTERED WINNERS: {len(winner_step)}"
        )

        winner_step = winner_step.sort_values(
            "FILTERED_PREV_PNL_PCT",
            ascending=False,
        )

        for _, row in winner_step.iterrows():
            case_number += 1
            print_case(
                row,
                case_number,
            )

        print()
        print(
            f"FILTERED LOSERS: {len(loser_step)}"
        )

        loser_step = loser_step.sort_values(
            "FILTERED_PREV_PNL_PCT",
            ascending=True,
        )

        for _, row in loser_step.iterrows():
            case_number += 1
            print_case(
                row,
                case_number,
            )

    print()
    print("=" * 100)
    print("EXPERIMENT #35 COMPLETE")
    print("=" * 100)
    print()
    print(
        f"Detailed CSV: {OUTPUT_ALL}"
    )
    print()
    print(
        "The output above is intended for human inspection."
    )
    print(
        "No threshold or trading rule was selected."
    )


if __name__ == "__main__":
    main()
