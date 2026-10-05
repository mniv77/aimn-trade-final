#!/usr/bin/env python3

"""
AIMn KISS - Experiment #36
Actual 5-Minute Candle Trajectory Inspection

RESEARCH ONLY.

Purpose
-------
Inspect the ACTUAL candle-by-candle market trajectory after a known
30-minute transition.

This experiment does NOT create a trading rule.

It compares actual 5-minute paths for carefully selected:

    0.25% -> 0.50% filtered winners
    0.25% -> 0.50% filtered losers

    0.50% -> 0.75% filtered winners
    0.50% -> 0.75% filtered losers

Primary questions
-----------------
1. What does a filtered winner actually look like?
2. What does a filtered loser actually look like?
3. Can shallow V's produce large winners?
4. Can deep V's produce winners?
5. Can recovery occur in both winners and losers?
6. What does the actual 5-minute candle sequence look like?

RESEARCH ONLY.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# FILES
# ============================================================

GEOMETRY_FILE = (
    PROJECT_ROOT
    / "kiss/results/exp32_raw_candle_v_geometry/raw_v_geometry.csv"
)

TRAJECTORY_FILE = (
    PROJECT_ROOT
    / "kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv"
)

WINNERS_FILE = (
    PROJECT_ROOT
    / "kiss/results/exp34_filtered_winner_loser/filtered_winners.csv"
)

LOSERS_FILE = (
    PROJECT_ROOT
    / "kiss/results/exp34_filtered_winner_loser/filtered_losers.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "kiss/results/exp36_candle_trajectory_inspection"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SELECTED_FILE = (
    OUTPUT_DIR / "selected_trajectory_cases.csv"
)

TEXT_FILE = (
    OUTPUT_DIR / "trajectory_inspection.txt"
)


# ============================================================
# HELPERS
# ============================================================

def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found:\n{path}"
        )

    return pd.read_csv(path)


def normalize_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(
        series,
        utc=True,
        errors="coerce",
    )


def depth_class(depth):
    if pd.isna(depth):
        return "UNKNOWN"

    if depth < 0.25:
        return "SHALLOW"

    if depth >= 1.00:
        return "DEEP"

    return "MEDIUM"


def recovery_class(row):
    recovered = bool(row["reached_recovery"])

    if not recovered:
        return "NO_RECOVERY"

    t = row["recovery_time_from_extreme_min"]

    if pd.isna(t):
        return "RECOVERY_UNKNOWN"

    if t <= 10:
        return "FAST_RECOVERY"

    if t >= 30:
        return "SLOW_RECOVERY"

    return "MEDIUM_RECOVERY"


# ============================================================
# LOAD
# ============================================================

print("=" * 78)
print("AIMn KISS - Experiment #36")
print("Actual 5-Minute Candle Trajectory Inspection")
print("=" * 78)

print()
print("Loading Experiment #32 geometry...")
geometry = read_csv(GEOMETRY_FILE)
print(f"Geometry rows: {len(geometry)}")

print()
print("Loading Experiment #32 trajectory...")
trajectory = read_csv(TRAJECTORY_FILE)
print(f"Trajectory rows: {len(trajectory)}")

print()
print("Loading Experiment #34 filtered winners...")
winners = read_csv(WINNERS_FILE)
print(f"Filtered winners: {len(winners)}")

print()
print("Loading Experiment #34 filtered losers...")
losers = read_csv(LOSERS_FILE)
print(f"Filtered losers: {len(losers)}")


# ============================================================
# NORMALIZE EXPERIMENT #32 TRAJECTORY
# ============================================================

trajectory["transition_known_utc"] = normalize_timestamp(
    trajectory["transition_known_utc"]
)

trajectory["candle_utc"] = normalize_timestamp(
    trajectory["candle_utc"]
)

trajectory["minutes_after_known"] = pd.to_numeric(
    trajectory["minutes_after_known"],
    errors="coerce",
)

numeric_trajectory_columns = [
    "open",
    "high",
    "low",
    "close",
    "adverse_from_transition_pct",
    "favorable_from_transition_pct",
    "recovery_from_raw_extreme_pct",
]

for col in numeric_trajectory_columns:
    trajectory[col] = pd.to_numeric(
        trajectory[col],
        errors="coerce",
    )


# ============================================================
# NORMALIZE EXPERIMENT #32 GEOMETRY
# ============================================================

geometry["transition_known_utc"] = normalize_timestamp(
    geometry["transition_known_utc"]
)

geometry["v_depth_pct"] = pd.to_numeric(
    geometry["v_depth_pct"],
    errors="coerce",
)

geometry["time_to_extreme_min"] = pd.to_numeric(
    geometry["time_to_extreme_min"],
    errors="coerce",
)

geometry["recovery_from_extreme_pct"] = pd.to_numeric(
    geometry["recovery_from_extreme_pct"],
    errors="coerce",
)

geometry["recovery_time_from_extreme_min"] = pd.to_numeric(
    geometry["recovery_time_from_extreme_min"],
    errors="coerce",
)

geometry["recovery_speed_pct_per_min"] = pd.to_numeric(
    geometry["recovery_speed_pct_per_min"],
    errors="coerce",
)

geometry["max_post_recovery_favorable_pct"] = pd.to_numeric(
    geometry["max_post_recovery_favorable_pct"],
    errors="coerce",
)

geometry["max_favorable_from_transition_pct"] = pd.to_numeric(
    geometry["max_favorable_from_transition_pct"],
    errors="coerce",
)

geometry["max_adverse_from_transition_pct"] = pd.to_numeric(
    geometry["max_adverse_from_transition_pct"],
    errors="coerce",
)


# ============================================================
# COMBINE EXPERIMENT #34
#
# Experiment #34 already contains the exact filter step.
# ============================================================

winners = winners.copy()
losers = losers.copy()

winners["_outcome"] = "WIN"
losers["_outcome"] = "LOSS"

filtered = pd.concat(
    [winners, losers],
    ignore_index=True,
)

filtered["transition_known_utc"] = normalize_timestamp(
    filtered["transition_known_utc"]
)

filtered["FILTERED_FROM_TRAIL_PCT"] = pd.to_numeric(
    filtered["FILTERED_FROM_TRAIL_PCT"],
    errors="coerce",
)

filtered["FILTERED_AT_TRAIL_PCT"] = pd.to_numeric(
    filtered["FILTERED_AT_TRAIL_PCT"],
    errors="coerce",
)

filtered["FILTERED_PREV_PNL_PCT"] = pd.to_numeric(
    filtered["FILTERED_PREV_PNL_PCT"],
    errors="coerce",
)

filtered["v_depth_pct"] = pd.to_numeric(
    filtered["v_depth_pct"],
    errors="coerce",
)

filtered["recovery_time_from_extreme_min"] = pd.to_numeric(
    filtered["recovery_time_from_extreme_min"],
    errors="coerce",
)

filtered["recovery_speed_pct_per_min"] = pd.to_numeric(
    filtered["recovery_speed_pct_per_min"],
    errors="coerce",
)


# ============================================================
# VERIFY THE FOUR GROUPS
# ============================================================

print()
print("=" * 78)
print("EXPERIMENT #34 FILTER GROUPS")
print("=" * 78)

for from_trail, at_trail in [
    (0.25, 0.50),
    (0.50, 0.75),
]:

    for outcome in ["WIN", "LOSS"]:

        count = len(
            filtered[
                (filtered["FILTERED_FROM_TRAIL_PCT"] == from_trail)
                &
                (filtered["FILTERED_AT_TRAIL_PCT"] == at_trail)
                &
                (filtered["_outcome"] == outcome)
            ]
        )

        print(
            f"{from_trail:.2f}% -> {at_trail:.2f}% "
            f"{outcome:4s}: {count}"
        )


# ============================================================
# SELECT CASES
#
# We deliberately select a small number of representative
# cases for actual candle inspection.
#
# For each of the four groups:
#
#   1 shallow case
#   1 deep case
#   1 fast-recovery case
#   1 slow/no-recovery case
#
# Maximum 4 per group.
# ============================================================

selected_parts = []

for from_trail, at_trail in [
    (0.25, 0.50),
    (0.50, 0.75),
]:

    for outcome in ["WIN", "LOSS"]:

        group = filtered[
            (filtered["FILTERED_FROM_TRAIL_PCT"] == from_trail)
            &
            (filtered["FILTERED_AT_TRAIL_PCT"] == at_trail)
            &
            (filtered["_outcome"] == outcome)
        ].copy()

        if group.empty:
            continue

        group["_depth_class"] = group["v_depth_pct"].apply(
            depth_class
        )

        group["_recovery_class"] = group.apply(
            recovery_class,
            axis=1,
        )

        chosen_indices = []

        # ----------------------------------------------------
        # 1. SHALLOW
        # ----------------------------------------------------

        shallow = group[
            group["_depth_class"] == "SHALLOW"
        ]

        if not shallow.empty:
            chosen_indices.append(
                shallow.index[0]
            )

        # ----------------------------------------------------
        # 2. DEEP
        # ----------------------------------------------------

        deep = group[
            group["_depth_class"] == "DEEP"
        ]

        if not deep.empty:

            for idx in deep.index:

                if idx not in chosen_indices:
                    chosen_indices.append(idx)
                    break

        # ----------------------------------------------------
        # 3. FAST RECOVERY
        # ----------------------------------------------------

        fast = group[
            group["_recovery_class"] == "FAST_RECOVERY"
        ]

        if not fast.empty:

            for idx in fast.index:

                if idx not in chosen_indices:
                    chosen_indices.append(idx)
                    break

        # ----------------------------------------------------
        # 4. SLOW / NO RECOVERY
        # ----------------------------------------------------

        slow_or_none = group[
            group["_recovery_class"].isin(
                [
                    "SLOW_RECOVERY",
                    "NO_RECOVERY",
                ]
            )
        ]

        if not slow_or_none.empty:

            for idx in slow_or_none.index:

                if idx not in chosen_indices:
                    chosen_indices.append(idx)
                    break

        chosen_indices = chosen_indices[:4]

        chosen = group.loc[
            chosen_indices
        ].copy()

        chosen["_selection_group"] = (
            f"{from_trail:.2f}->{at_trail:.2f} "
            f"{outcome}"
        )

        selected_parts.append(chosen)


# ============================================================
# COMBINE SELECTED
# ============================================================

if selected_parts:

    selected = pd.concat(
        selected_parts,
        ignore_index=True,
    )

else:

    selected = pd.DataFrame()


# ============================================================
# SAVE SELECTED CASE LIST
# ============================================================

selected.to_csv(
    SELECTED_FILE,
    index=False,
)


# ============================================================
# PRINT SELECTED CASES
# ============================================================

print()
print("=" * 78)
print("SELECTED CASES FOR ACTUAL CANDLE INSPECTION")
print("=" * 78)

display_columns = [
    "_selection_group",
    "case_id",
    "symbol",
    "direction",
    "transition_known_utc",
    "FILTERED_PREV_PNL_PCT",
    "v_depth_pct",
    "time_to_extreme_min",
    "recovery_from_extreme_pct",
    "recovery_time_from_extreme_min",
    "recovery_speed_pct_per_min",
    "max_favorable_from_transition_pct",
    "max_adverse_from_transition_pct",
]

display_columns = [
    c for c in display_columns
    if c in selected.columns
]

if selected.empty:

    print("NO CASES SELECTED.")

else:

    print(
        selected[
            display_columns
        ].to_string(index=False)
    )


# ============================================================
# BUILD HUMAN-READABLE TRAJECTORY REPORT
# ============================================================

report = []

report.append("=" * 100)
report.append(
    "AIMn KISS - EXPERIMENT #36"
)
report.append(
    "ACTUAL 5-MINUTE CANDLE TRAJECTORY INSPECTION"
)
report.append("=" * 100)
report.append("")
report.append(
    "RESEARCH ONLY - NO RULE SELECTION"
)
report.append("")


for number, case in enumerate(
    selected.to_dict("records"),
    start=1,
):

    symbol = case["symbol"]
    direction = case["direction"]
    transition = pd.Timestamp(
        case["transition_known_utc"]
    )

    report.append("")
    report.append("#" * 100)
    report.append(
        f"CASE {number}: {case['_selection_group']}"
    )
    report.append("#" * 100)

    report.append(
        f"Case ID:             {case['case_id']}"
    )

    report.append(
        f"Symbol:              {symbol}"
    )

    report.append(
        f"Direction:            {direction}"
    )

    report.append(
        f"Transition UTC:       {transition}"
    )

    report.append(
        f"Previous P&L:         "
        f"{case['FILTERED_PREV_PNL_PCT']:.4f}%"
    )

    report.append(
        f"V depth:              "
        f"{case['v_depth_pct']:.4f}%"
    )

    report.append(
        f"V depth class:        "
        f"{case['_depth_class']}"
    )

    report.append(
        f"Time to extreme:      "
        f"{case['time_to_extreme_min']:.1f} min"
    )

    report.append(
        f"Recovery:             "
        f"{case['recovery_from_extreme_pct']:.4f}%"
    )

    report.append(
        f"Recovery time:        "
        f"{case['recovery_time_from_extreme_min']}"
    )

    report.append(
        f"Recovery speed:       "
        f"{case['recovery_speed_pct_per_min']}"
    )

    report.append(
        f"Max favorable:        "
        f"{case['max_favorable_from_transition_pct']:.4f}%"
    )

    report.append(
        f"Max adverse:          "
        f"{case['max_adverse_from_transition_pct']:.4f}%"
    )

    report.append("")

    report.append(
        "ACTUAL 5-MINUTE CANDLE PATH"
    )

    report.append(
        "-" * 100
    )

    header = (
        "Min | UTC                  | "
        "Open       High       Low        Close      | "
        "Adverse % | Favorable % | Recovery %"
    )

    report.append(header)
    report.append("-" * len(header))

    case_rows = trajectory[
        (trajectory["symbol"] == symbol)
        &
        (trajectory["direction"] == direction)
        &
        (
            trajectory["transition_known_utc"]
            == transition
        )
    ].copy()

    case_rows = case_rows.sort_values(
        "minutes_after_known"
    )

    if case_rows.empty:

        report.append(
            "NO MATCHING TRAJECTORY FOUND."
        )

        continue

    for _, row in case_rows.iterrows():

        minute = int(
            row["minutes_after_known"]
        )

        utc = str(
            row["candle_utc"]
        )

        report.append(
            f"{minute:3d} | "
            f"{utc:20s} | "
            f"{row['open']:9.4f} "
            f"{row['high']:9.4f} "
            f"{row['low']:9.4f} "
            f"{row['close']:9.4f} | "
            f"{row['adverse_from_transition_pct']:9.4f} | "
            f"{row['favorable_from_transition_pct']:10.4f} | "
            f"{row['recovery_from_raw_extreme_pct']:9.4f}"
        )

    report.append("")
    report.append(
        "Interpretation aid:"
    )

    report.append(
        "  Adverse %    = movement against transition direction."
    )

    report.append(
        "  Favorable %  = movement in transition direction."
    )

    report.append(
        "  Recovery %   = rebound from the raw adverse extreme."
    )


# ============================================================
# SAVE REPORT
# ============================================================

TEXT_FILE.write_text(
    "\n".join(report),
    encoding="utf-8",
)


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 78)
print("EXPERIMENT #36 COMPLETE")
print("=" * 78)

print()
print("Selected cases:")
print(
    f"  {SELECTED_FILE}"
)

print()
print("Actual 5-minute candle report:")
print(
    f"  {TEXT_FILE}"
)

print()
print(
    "This experiment only exposes actual candle paths."
)

print(
    "It does NOT select or promote a trading rule."
)
