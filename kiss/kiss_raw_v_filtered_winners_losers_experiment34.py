#!/usr/bin/env python3
"""
AIMn KISS - Experiment #34
Raw V Geometry: Filtered Winners vs Filtered Losers

RESEARCH ONLY.

Purpose
-------
Experiment #33 connected independent raw 5m V geometry from Experiment #32
to the actual trailing-entry outcomes from Experiment #30.

Experiment #34 goes one step deeper.

For every transition filtered out when the entry trail is increased:

    0.25% -> 0.50%
    0.50% -> 0.75%
    0.75% -> 1.00%
    1.00% -> 1.25%
    1.25% -> 1.50%

split the filtered transitions into:

    FILTERED WINNERS
    FILTERED LOSERS

and compare their raw V geometry.

This experiment DOES NOT:
    - change the trading strategy
    - choose an entry threshold
    - optimize parameters
    - train AI/ML
    - generate production rules
    - place orders
    - rerun the market simulation

It only analyzes the already-generated Experiment #33 results.

Questions
---------
1. What does a filtered winner look like?
2. What does a filtered loser look like?
3. Is V depth different?
4. Is recovery speed different?
5. Is time-to-extreme different?
6. Is dwell near the adverse extreme different?
7. Is post-recovery favorable movement different?
8. Does reaching recovery distinguish winners from losers?
9. Does reaching favorable movement distinguish winners from losers?
10. Are there obvious individual counterexamples?

Important
---------
This is descriptive research only.

A difference between groups is NOT automatically a usable trading rule.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List

import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    ROOT
    / "kiss"
    / "results"
    / "exp33_raw_v_vs_entry_outcome"
    / "raw_v_filtered_by_trail.csv"
)

OUTPUT_DIR = (
    ROOT
    / "kiss"
    / "results"
    / "exp34_filtered_winner_loser"
)

OUTPUT_WINNERS = OUTPUT_DIR / "filtered_winners.csv"
OUTPUT_LOSERS = OUTPUT_DIR / "filtered_losers.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "filtered_geometry_summary.csv"
OUTPUT_JSON = OUTPUT_DIR / "filtered_winner_loser_summary.json"


# ---------------------------------------------------------------------
# Trail transitions
# ---------------------------------------------------------------------

TRAIL_STEPS = [
    (0.25, 0.50),
    (0.50, 0.75),
    (0.75, 1.00),
    (1.00, 1.25),
    (1.25, 1.50),
]


# ---------------------------------------------------------------------
# Geometry fields
# ---------------------------------------------------------------------

GEOMETRY_FIELDS = [
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


BOOLEAN_FIELDS = [
    "reached_recovery",
    "reached_favorable",
]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def pct_code(value: float) -> str:
    """
    Convert a trail percentage to the Experiment #33 filename/code style.

    Examples:
        0.25 -> 025
        0.50 -> 050
        0.75 -> 075
        1.00 -> 100
        1.25 -> 125
        1.50 -> 150
    """
    return f"{int(round(value * 100)):03d}"


def safe_float(value):
    """
    Convert a value to float where possible.
    Return NaN for missing/unusable values.
    """
    if pd.isna(value):
        return math.nan

    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def mean_or_nan(series: pd.Series):
    if series.empty:
        return math.nan

    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if numeric.empty:
        return math.nan

    return float(numeric.mean())


def median_or_nan(series: pd.Series):
    if series.empty:
        return math.nan

    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if numeric.empty:
        return math.nan

    return float(numeric.median())


def pct_true(series: pd.Series):
    """
    Percentage of non-missing values that are True.
    """
    if series.empty:
        return math.nan

    values = series.dropna()

    if values.empty:
        return math.nan

    normalized = values.astype(str).str.lower().map(
        {
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        }
    )

    normalized = normalized.dropna()

    if normalized.empty:
        return math.nan

    return float(normalized.mean() * 100.0)


def format_number(value, digits: int = 6):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    return round(float(value), digits)


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

def validate_input(df: pd.DataFrame) -> None:
    required = [
        "case_id",
        "symbol",
        "direction",
        "transition_time_utc",
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
        "FILTERED_FROM_TRAIL_PCT",
        "FILTERED_AT_TRAIL_PCT",
        "FILTERED_PREV_PNL_PCT",
        "FILTERED_PREV_OUTCOME",
    ]

    missing = [column for column in required if column not in df.columns]

    if missing:
        raise RuntimeError(
            "Experiment #33 CSV is missing required columns:\n"
            + "\n".join(f"  - {column}" for column in missing)
        )


# ---------------------------------------------------------------------
# Add classification
# ---------------------------------------------------------------------

def classify_filtered_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize and classify Experiment #33 filtered rows.

    FILTERED_PREV_OUTCOME should normally be WIN or LOSS.
    Anything else is preserved as OTHER rather than silently classified.
    """

    out = df.copy()

    out["FILTERED_PREV_PNL_PCT"] = pd.to_numeric(
        out["FILTERED_PREV_PNL_PCT"],
        errors="coerce",
    )

    out["FILTERED_FROM_TRAIL_PCT"] = pd.to_numeric(
        out["FILTERED_FROM_TRAIL_PCT"],
        errors="coerce",
    )

    out["FILTERED_AT_TRAIL_PCT"] = pd.to_numeric(
        out["FILTERED_AT_TRAIL_PCT"],
        errors="coerce",
    )

    outcome = (
        out["FILTERED_PREV_OUTCOME"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    out["FILTERED_CLASS"] = outcome.map(
        {
            "WIN": "WINNER",
            "LOSS": "LOSER",
        }
    ).fillna("OTHER")

    return out


# ---------------------------------------------------------------------
# Per-group summary
# ---------------------------------------------------------------------

def summarize_group(
    group: pd.DataFrame,
    from_trail: float,
    at_trail: float,
    classification: str,
) -> Dict:

    row: Dict = {
        "from_trail_pct": from_trail,
        "at_trail_pct": at_trail,
        "classification": classification,
        "count": int(len(group)),
        "total_previous_pnl_pct": format_number(
            pd.to_numeric(
                group["FILTERED_PREV_PNL_PCT"],
                errors="coerce",
            ).sum(),
            6,
        ),
        "avg_previous_pnl_pct": format_number(
            mean_or_nan(group["FILTERED_PREV_PNL_PCT"]),
            6,
        ),
        "median_previous_pnl_pct": format_number(
            median_or_nan(group["FILTERED_PREV_PNL_PCT"]),
            6,
        ),
    }

    for field in GEOMETRY_FIELDS:
        row[f"avg_{field}"] = format_number(
            mean_or_nan(group[field]),
            6,
        )

        row[f"median_{field}"] = format_number(
            median_or_nan(group[field]),
            6,
        )

    for field in BOOLEAN_FIELDS:
        row[f"pct_{field}_true"] = format_number(
            pct_true(group[field]),
            3,
        )

    return row


# ---------------------------------------------------------------------
# Winner vs loser difference
# ---------------------------------------------------------------------

def summarize_difference(
    winners: pd.DataFrame,
    losers: pd.DataFrame,
    from_trail: float,
    at_trail: float,
) -> Dict:

    row: Dict = {
        "from_trail_pct": from_trail,
        "at_trail_pct": at_trail,
        "classification": "WINNER_MINUS_LOSER",
        "count": int(len(winners) - len(losers)),
        "total_previous_pnl_pct": format_number(
            pd.to_numeric(
                winners["FILTERED_PREV_PNL_PCT"],
                errors="coerce",
            ).sum()
            - pd.to_numeric(
                losers["FILTERED_PREV_PNL_PCT"],
                errors="coerce",
            ).sum(),
            6,
        ),
        "avg_previous_pnl_pct": format_number(
            mean_or_nan(winners["FILTERED_PREV_PNL_PCT"])
            - mean_or_nan(losers["FILTERED_PREV_PNL_PCT"]),
            6,
        ),
        "median_previous_pnl_pct": format_number(
            median_or_nan(winners["FILTERED_PREV_PNL_PCT"])
            - median_or_nan(losers["FILTERED_PREV_PNL_PCT"]),
            6,
        ),
    }

    for field in GEOMETRY_FIELDS:
        row[f"avg_{field}"] = format_number(
            mean_or_nan(winners[field])
            - mean_or_nan(losers[field]),
            6,
        )

        row[f"median_{field}"] = format_number(
            median_or_nan(winners[field])
            - median_or_nan(losers[field]),
            6,
        )

    for field in BOOLEAN_FIELDS:
        row[f"pct_{field}_true"] = format_number(
            pct_true(winners[field])
            - pct_true(losers[field]),
            3,
        )

    return row


# ---------------------------------------------------------------------
# Actual individual filtered cases
# ---------------------------------------------------------------------

def build_case_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep the most useful fields for direct trade inspection.
    """

    columns = [
        "case_id",
        "symbol",
        "direction",
        "transition_time_utc",
        "transition_known_utc",
        "transition_close",

        "FILTERED_FROM_TRAIL_PCT",
        "FILTERED_AT_TRAIL_PCT",
        "FILTERED_PREV_PNL_PCT",
        "FILTERED_PREV_OUTCOME",

        "v_depth_pct",
        "time_to_extreme_min",
        "adverse_extreme_time_utc",

        "recovery_from_extreme_pct",
        "recovery_time_from_extreme_min",
        "recovery_speed_pct_per_min",

        "near_extreme_dwell_min",

        "max_post_recovery_favorable_pct",
        "max_favorable_from_transition_pct",
        "max_adverse_from_transition_pct",

        "reached_recovery",
        "reached_favorable",

        "candles_measured",
    ]

    available = [column for column in columns if column in df.columns]

    out = df[available].copy()

    sort_columns = [
        column
        for column in [
            "FILTERED_AT_TRAIL_PCT",
            "FILTERED_PREV_PNL_PCT",
            "symbol",
            "transition_time_utc",
        ]
        if column in out.columns
    ]

    if sort_columns:
        ascending = []

        for column in sort_columns:
            if column == "FILTERED_PREV_PNL_PCT":
                ascending.append(True)
            else:
                ascending.append(True)

        out = out.sort_values(
            sort_columns,
            ascending=ascending,
        )

    return out


# ---------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 100)
    print("EXPERIMENT #34 RAW V GEOMETRY: FILTERED WINNERS VS FILTERED LOSERS")
    print("=" * 100)
    print("RESEARCH ONLY")
    print()
    print("Input:")
    print(f"  {INPUT_FILE}")
    print()
    print("Trail transitions:")

    for from_trail, at_trail in TRAIL_STEPS:
        print(
            f"  {from_trail:.2f}% -> {at_trail:.2f}%"
        )

    print()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Experiment #33 output not found:\n{INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_FILE)

    print(f"[LOAD] Experiment #33 filtered rows: {len(df)}")

    validate_input(df)

    df = classify_filtered_rows(df)

    print()

    class_counts = (
        df["FILTERED_CLASS"]
        .value_counts(dropna=False)
        .to_dict()
    )

    print("[CLASSIFICATION]")
    for key, value in class_counts.items():
        print(f"  {key}: {value}")

    print()

    # ---------------------------------------------------------------
    # Keep only WINNER and LOSER rows for the main analysis.
    # ---------------------------------------------------------------

    winners = df[df["FILTERED_CLASS"] == "WINNER"].copy()
    losers = df[df["FILTERED_CLASS"] == "LOSER"].copy()

    # Save complete winner/loser case lists.
    winner_cases = build_case_table(winners)
    loser_cases = build_case_table(losers)

    winner_cases.to_csv(OUTPUT_WINNERS, index=False)
    loser_cases.to_csv(OUTPUT_LOSERS, index=False)

    # ---------------------------------------------------------------
    # Summary rows
    # ---------------------------------------------------------------

    summary_rows: List[Dict] = []

    for from_trail, at_trail in TRAIL_STEPS:

        step_mask = (
            (df["FILTERED_FROM_TRAIL_PCT"] == from_trail)
            & (df["FILTERED_AT_TRAIL_PCT"] == at_trail)
        )

        step = df[step_mask].copy()

        step_winners = step[
            step["FILTERED_CLASS"] == "WINNER"
        ].copy()

        step_losers = step[
            step["FILTERED_CLASS"] == "LOSER"
        ].copy()

        step_other = step[
            step["FILTERED_CLASS"] == "OTHER"
        ].copy()

        print("-" * 100)
        print(
            f"TRAIL {from_trail:.2f}% -> {at_trail:.2f}%"
        )
        print(
            f"  total filtered : {len(step)}"
        )
        print(
            f"  winners        : {len(step_winners)}"
        )
        print(
            f"  losers         : {len(step_losers)}"
        )
        print(
            f"  other          : {len(step_other)}"
        )

        summary_rows.append(
            summarize_group(
                step_winners,
                from_trail,
                at_trail,
                "WINNER",
            )
        )

        summary_rows.append(
            summarize_group(
                step_losers,
                from_trail,
                at_trail,
                "LOSER",
            )
        )

        summary_rows.append(
            summarize_difference(
                step_winners,
                step_losers,
                from_trail,
                at_trail,
            )
        )

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
    )

    # ---------------------------------------------------------------
    # Detailed JSON summary
    # ---------------------------------------------------------------

    json_data = {
        "experiment": 34,
        "title": "Raw V Geometry: Filtered Winners vs Filtered Losers",
        "research_only": True,
        "input_file": str(INPUT_FILE),
        "input_rows": int(len(df)),
        "classification_counts": {
            str(key): int(value)
            for key, value in class_counts.items()
        },
        "trail_steps": [
            {
                "from_trail_pct": from_trail,
                "at_trail_pct": at_trail,
            }
            for from_trail, at_trail in TRAIL_STEPS
        ],
        "groups": [],
    }

    for from_trail, at_trail in TRAIL_STEPS:

        step = df[
            (df["FILTERED_FROM_TRAIL_PCT"] == from_trail)
            & (df["FILTERED_AT_TRAIL_PCT"] == at_trail)
        ].copy()

        step_winners = step[
            step["FILTERED_CLASS"] == "WINNER"
        ].copy()

        step_losers = step[
            step["FILTERED_CLASS"] == "LOSER"
        ].copy()

        winner_summary = summarize_group(
            step_winners,
            from_trail,
            at_trail,
            "WINNER",
        )

        loser_summary = summarize_group(
            step_losers,
            from_trail,
            at_trail,
            "LOSER",
        )

        difference_summary = summarize_difference(
            step_winners,
            step_losers,
            from_trail,
            at_trail,
        )

        json_data["groups"].append(
            {
                "from_trail_pct": from_trail,
                "at_trail_pct": at_trail,
                "winner": winner_summary,
                "loser": loser_summary,
                "winner_minus_loser": difference_summary,
            }
        )

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            json_data,
            handle,
            indent=2,
            allow_nan=False,
        )

    # ---------------------------------------------------------------
    # Console summary
    # ---------------------------------------------------------------

    print()
    print("=" * 100)
    print("EXPERIMENT #34 COMPLETE")
    print("=" * 100)
    print()

    display_columns = [
        "from_trail_pct",
        "at_trail_pct",
        "classification",
        "count",
        "avg_previous_pnl_pct",
        "median_previous_pnl_pct",
        "avg_v_depth_pct",
        "avg_time_to_extreme_min",
        "avg_recovery_speed_pct_per_min",
        "avg_near_extreme_dwell_min",
        "avg_max_post_recovery_favorable_pct",
        "avg_max_favorable_from_transition_pct",
        "avg_max_adverse_from_transition_pct",
        "pct_reached_recovery_true",
        "pct_reached_favorable_true",
    ]

    available_display = [
        column
        for column in display_columns
        if column in summary.columns
    ]

    print(
        summary[available_display].to_string(
            index=False
        )
    )

    print()
    print("WINNERS:")
    print(f"  {OUTPUT_WINNERS}")

    print("LOSERS:")
    print(f"  {OUTPUT_LOSERS}")

    print("SUMMARY:")
    print(f"  {OUTPUT_SUMMARY}")

    print("JSON:")
    print(f"  {OUTPUT_JSON}")

    print()
    print("IMPORTANT:")
    print(
        "This experiment describes filtered winner/loser geometry."
    )
    print(
        "It does NOT select an entry trail or create a trading rule."
    )


if __name__ == "__main__":
    main()
