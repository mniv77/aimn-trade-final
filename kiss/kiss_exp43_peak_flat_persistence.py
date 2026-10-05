#!/usr/bin/env python3

"""
================================================================================
EXPERIMENT #43 — NVDA PEAK-FLAT PERSISTENCE
================================================================================

QUESTION
--------
When the favorable peak stops advancing, what happens afterward?

PURE OBSERVATION ONLY.

We examine:

    PEAK_FLAT
        |
        +--> another PEAK_FLAT
        +--> PEAK advances
        +--> P&L improves
        +--> P&L deteriorates
        +--> eventual positive / negative outcome

NO:
    - entry rule
    - exit rule
    - V threshold
    - minor/medium/major classification
    - optimization
    - parameter promotion
    - production changes
    - orders
    - AI training

SOURCE
------
Experiment #42:

    kiss/results/exp42_v_peak_divergence/
        nvda_v_peak_divergence_transitions.csv

IMPORTANT
---------
A flat peak is an observation only.
It is NOT an exit signal.

================================================================================
"""

from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path.cwd()

SOURCE = (
    ROOT
    / "kiss"
    / "results"
    / "exp42_v_peak_divergence"
    / "nvda_v_peak_divergence_transitions.csv"
)

OUT_DIR = (
    ROOT
    / "kiss"
    / "results"
    / "exp43_peak_flat_persistence"
)

TRANSITIONS_OUT = (
    OUT_DIR
    / "nvda_peak_flat_persistence_transitions.csv"
)

SUMMARY_OUT = (
    OUT_DIR
    / "nvda_peak_flat_persistence_summary.csv"
)

TRADE_SUMMARY_OUT = (
    OUT_DIR
    / "nvda_peak_flat_persistence_trade_summary.csv"
)

METADATA_OUT = (
    OUT_DIR
    / "exp43_metadata.txt"
)


# -----------------------------------------------------------------------------
# Numeric helper
# -----------------------------------------------------------------------------

def num(df, column):
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source file not found:\n{SOURCE}"
        )

    df = pd.read_csv(
        SOURCE
    )

    print()
    print("=" * 100)
    print("EXPERIMENT #43")
    print("NVDA PEAK-FLAT PERSISTENCE")
    print("=" * 100)
    print()

    print(
        f"Source rows loaded : {len(df)}"
    )

    # -------------------------------------------------------------------------
    # Required columns from ACTUAL Experiment #42 file
    # -------------------------------------------------------------------------

    required = [
        "trade_id",
        "case_id",
        "event_time_utc",
        "pnl_at_v_pct",
        "favorable_peak_before_v_pct",
        "eventual_pnl_hindsight_pct",
        "v_number",
        "total_v_events_in_trade",
        "previous_v_time_utc",
        "previous_v_pnl_pct",
        "previous_prior_peak_pct",
        "minutes_since_previous_v",
        "pnl_change_from_previous_v_pct",
        "giveback_change_from_previous_v_pct_points",
        "prior_peak_change_from_previous_v_pct",
        "pnl_peak_relationship",
        "relationship_type",
        "previous_v_recovery_state",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required columns:\n"
            + "\n".join(
                f"  {c}"
                for c in missing
            )
        )

    # -------------------------------------------------------------------------
    # Numeric conversion
    # -------------------------------------------------------------------------

    numeric_columns = [
        "pnl_at_v_pct",
        "favorable_peak_before_v_pct",
        "eventual_pnl_hindsight_pct",
        "v_number",
        "total_v_events_in_trade",
        "previous_v_pnl_pct",
        "previous_prior_peak_pct",
        "minutes_since_previous_v",
        "pnl_change_from_previous_v_pct",
        "giveback_change_from_previous_v_pct_points",
        "prior_peak_change_from_previous_v_pct",
    ]

    for column in numeric_columns:
        num(df, column)

    # -------------------------------------------------------------------------
    # Dates
    # -------------------------------------------------------------------------

    for column in [
        "event_time_utc",
        "previous_v_time_utc",
    ]:

        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
            utc=True
        )

    # -------------------------------------------------------------------------
    # Sort by trade and chronological V number
    # -------------------------------------------------------------------------

    df = df.sort_values(
        [
            "trade_id",
            "v_number",
            "event_time_utc",
        ]
    ).reset_index(
        drop=True
    )

    # -------------------------------------------------------------------------
    # Define whether CURRENT V represents a flat peak versus previous V.
    #
    # This comes directly from Experiment #42.
    #
    # PEAK_FLAT means:
    #
    #     prior_peak_sequence_direction = UNCHANGED
    #
    # or the explicit:
    #
    #     pnl_peak_relationship = PEAK_FLAT
    #
    # We use the explicit #42 relationship as primary.
    # -------------------------------------------------------------------------

    df["is_peak_flat"] = (
        df["pnl_peak_relationship"]
        .eq("PEAK_FLAT")
    )

    df["is_peak_up"] = (
        df["pnl_peak_relationship"]
        .eq("A_PNL_UP_PEAK_UP")
        |
        df["pnl_peak_relationship"]
        .eq("B_PNL_DOWN_PEAK_UP")
    )

    df["is_peak_down"] = (
        df["prior_peak_change_from_previous_v_pct"]
        < 0
    )

    # -------------------------------------------------------------------------
    # Calculate the sign of the P&L change.
    # -------------------------------------------------------------------------

    def pnl_direction(value):

        if pd.isna(value):
            return "UNKNOWN"

        if value > 0:
            return "PNL_UP"

        if value < 0:
            return "PNL_DOWN"

        return "PNL_FLAT"

    df["pnl_change_direction"] = (
        df["pnl_change_from_previous_v_pct"]
        .apply(pnl_direction)
    )

    # -------------------------------------------------------------------------
    # Peak-flat persistence.
    #
    # IMPORTANT:
    #
    # We count consecutive PEAK_FLAT observations within each trade.
    #
    # This does NOT create a threshold.
    # It merely describes what occurred.
    # -------------------------------------------------------------------------

    df["peak_flat_run"] = 0

    for trade_id, group in df.groupby(
        "trade_id",
        sort=False
    ):

        run = 0

        for idx in group.index:

            if bool(
                df.loc[
                    idx,
                    "is_peak_flat"
                ]
            ):
                run += 1
            else:
                run = 0

            df.loc[
                idx,
                "peak_flat_run"
            ] = run

    # -------------------------------------------------------------------------
    # What happened at the NEXT V?
    #
    # We use the next row in chronological V sequence.
    # -------------------------------------------------------------------------

    df["next_peak_relationship"] = (
        df.groupby(
            "trade_id"
        )[
            "pnl_peak_relationship"
        ]
        .shift(-1)
    )

    df["next_pnl_change_pct"] = (
        df.groupby(
            "trade_id"
        )[
            "pnl_change_from_previous_v_pct"
        ]
        .shift(-1)
    )

    df["next_peak_change_pct"] = (
        df.groupby(
            "trade_id"
        )[
            "prior_peak_change_from_previous_v_pct"
        ]
        .shift(-1)
    )

    df["next_eventual_pnl_pct"] = (
        df.groupby(
            "trade_id"
        )[
            "eventual_pnl_hindsight_pct"
        ]
        .shift(-1)
    )

    # -------------------------------------------------------------------------
    # Describe resolution after a flat peak.
    # -------------------------------------------------------------------------

    def resolution(row):

        next_relationship = (
            row["next_peak_relationship"]
        )

        next_peak_change = (
            row["next_peak_change_pct"]
        )

        next_pnl_change = (
            row["next_pnl_change_pct"]
        )

        if pd.isna(next_relationship):
            return "NO_NEXT_V"

        if next_relationship == "PEAK_FLAT":
            if pd.notna(next_pnl_change):

                if next_pnl_change > 0:
                    return "FLAT_AGAIN_PNL_UP"

                if next_pnl_change < 0:
                    return "FLAT_AGAIN_PNL_DOWN"

                return "FLAT_AGAIN_PNL_FLAT"

            return "FLAT_AGAIN"

        if (
            pd.notna(next_peak_change)
            and next_peak_change > 0
        ):

            if pd.notna(next_pnl_change):

                if next_pnl_change > 0:
                    return "PEAK_RESUMES_PNL_UP"

                if next_pnl_change < 0:
                    return "PEAK_RESUMES_PNL_DOWN"

            return "PEAK_RESUMES"

        if (
            pd.notna(next_peak_change)
            and next_peak_change < 0
        ):

            if pd.notna(next_pnl_change):

                if next_pnl_change > 0:
                    return "PEAK_DOWN_PNL_UP"

                if next_pnl_change < 0:
                    return "PEAK_DOWN_PNL_DOWN"

            return "PEAK_DOWN"

        return "UNKNOWN"

    df["flat_resolution"] = df.apply(
        resolution,
        axis=1
    )

    # -------------------------------------------------------------------------
    # Only flat-peak observations.
    # -------------------------------------------------------------------------

    flat = df[
        df["is_peak_flat"]
    ].copy()

    # -------------------------------------------------------------------------
    # SUMMARY 1:
    #
    # Flat run length.
    # -------------------------------------------------------------------------

    summary_rows = []

    for run_length, group in flat.groupby(
        "peak_flat_run",
        sort=True
    ):

        summary_rows.append({
            "peak_flat_run": int(
                run_length
            ),

            "observations": len(
                group
            ),

            "unique_trades": group[
                "trade_id"
            ].nunique(),

            "avg_pnl_change_pct": group[
                "pnl_change_from_previous_v_pct"
            ].mean(),

            "median_pnl_change_pct": group[
                "pnl_change_from_previous_v_pct"
            ].median(),

            "avg_peak_change_pct": group[
                "prior_peak_change_from_previous_v_pct"
            ].mean(),

            "median_peak_change_pct": group[
                "prior_peak_change_from_previous_v_pct"
            ].median(),

            "avg_eventual_pnl_pct": group[
                "eventual_pnl_hindsight_pct"
            ].mean(),

            "median_eventual_pnl_pct": group[
                "eventual_pnl_hindsight_pct"
            ].median(),

            "eventual_positive_pct": (
                group[
                    "eventual_pnl_hindsight_pct"
                ] > 0
            ).mean() * 100,
        })

    summary = pd.DataFrame(
        summary_rows
    )

    summary.to_csv(
        SUMMARY_OUT,
        index=False
    )

    # -------------------------------------------------------------------------
    # SUMMARY 2:
    #
    # How did the flat peak resolve?
    # -------------------------------------------------------------------------

    resolution_rows = []

    for resolution_name, group in df[
        df["is_peak_flat"]
    ].groupby(
        "flat_resolution",
        sort=False
    ):

        resolution_rows.append({
            "flat_resolution": resolution_name,

            "observations": len(
                group
            ),

            "unique_trades": group[
                "trade_id"
            ].nunique(),

            "avg_current_pnl_pct": group[
                "pnl_at_v_pct"
            ].mean(),

            "median_current_pnl_pct": group[
                "pnl_at_v_pct"
            ].median(),

            "avg_pnl_change_pct": group[
                "pnl_change_from_previous_v_pct"
            ].mean(),

            "median_pnl_change_pct": group[
                "pnl_change_from_previous_v_pct"
            ].median(),

            "avg_peak_change_pct": group[
                "prior_peak_change_from_previous_v_pct"
            ].mean(),

            "median_peak_change_pct": group[
                "prior_peak_change_from_previous_v_pct"
            ].median(),

            "avg_eventual_pnl_pct": group[
                "eventual_pnl_hindsight_pct"
            ].mean(),

            "median_eventual_pnl_pct": group[
                "eventual_pnl_hindsight_pct"
            ].median(),

            "eventual_positive_pct": (
                group[
                    "eventual_pnl_hindsight_pct"
                ] > 0
            ).mean() * 100,
        })

    resolution_summary = pd.DataFrame(
        resolution_rows
    )

    resolution_summary.to_csv(
        OUT_DIR
        / "nvda_peak_flat_resolution_summary.csv",
        index=False
    )

    # -------------------------------------------------------------------------
    # TRADE LEVEL
    #
    # Build the sequence of flat-peak observations for each trade.
    # -------------------------------------------------------------------------

    trade_rows = []

    for trade_id, group in df.groupby(
        "trade_id",
        sort=False
    ):

        flat_group = group[
            group["is_peak_flat"]
        ]

        if len(flat_group) == 0:
            continue

        path = []

        for _, row in flat_group.iterrows():

            path.append(
                f"FLAT{int(row['peak_flat_run'])}"
                f"->{row['flat_resolution']}"
            )

        trade_rows.append({
            "trade_id": trade_id,

            "flat_peak_observations": len(
                flat_group
            ),

            "maximum_flat_run": int(
                flat_group[
                    "peak_flat_run"
                ].max()
            ),

            "flat_path": " | ".join(
                path
            ),

            "eventual_pnl_pct": float(
                group[
                    "eventual_pnl_hindsight_pct"
                ].iloc[-1]
            ),
        })

    trade_summary = pd.DataFrame(
        trade_rows
    )

    trade_summary.to_csv(
        TRADE_SUMMARY_OUT,
        index=False
    )

    # -------------------------------------------------------------------------
    # Save full transition-level research file.
    # -------------------------------------------------------------------------

    df.to_csv(
        TRANSITIONS_OUT,
        index=False
    )

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    metadata = f"""
================================================================================
EXPERIMENT #43 COMPLETE
================================================================================

QUESTION
--------
When the favorable peak stops advancing, what happens afterward?

SOURCE
------
{SOURCE}

SOURCE ROWS
-----------
{len(df)}

PEAK-FLAT OBSERVATIONS
----------------------
{len(flat)}

TRADES
------
Total trades represented       : {df["trade_id"].nunique()}
Trades with PEAK_FLAT           : {flat["trade_id"].nunique()}

RESEARCH STATUS
---------------
PURE OBSERVATION.

No entry rule.
No exit rule.
No V threshold.
No minor/medium/major classification.
No optimization.
No parameter promotion.
No production changes.
No orders.
No AI training.

A flat peak is an observation only.

OUTPUTS
-------
{TRANSITIONS_OUT}
{SUMMARY_OUT}
{OUT_DIR / "nvda_peak_flat_resolution_summary.csv"}
{TRADE_SUMMARY_OUT}
{METADATA_OUT}

================================================================================
"""

    METADATA_OUT.write_text(
        metadata.strip() + "\n",
        encoding="utf-8"
    )

    # -------------------------------------------------------------------------
    # Console output
    # -------------------------------------------------------------------------

    print()
    print("=" * 100)
    print("EXPERIMENT #43")
    print("NVDA PEAK-FLAT PERSISTENCE")
    print("=" * 100)

    print()
    print("DATA")
    print("-" * 100)

    print(
        f"Source rows              : {len(df)}"
    )

    print(
        f"PEAK_FLAT observations   : {len(flat)}"
    )

    print(
        f"Unique trades            : "
        f"{df['trade_id'].nunique()}"
    )

    print(
        f"Trades with PEAK_FLAT    : "
        f"{flat['trade_id'].nunique()}"
    )

    print()
    print("PEAK-FLAT RUN LENGTH")
    print("-" * 100)

    if len(summary) == 0:

        print(
            "No PEAK_FLAT observations found."
        )

    else:

        for _, row in summary.iterrows():

            print(
                f"FLAT RUN "
                f"{int(row['peak_flat_run']):2d}"
                f" | n={int(row['observations']):3d}"
                f" | trades="
                f"{int(row['unique_trades']):3d}"
                f" | dP&L="
                f"{row['avg_pnl_change_pct']:+.4f}%"
                f" | dPeak="
                f"{row['avg_peak_change_pct']:+.4f}%"
                f" | eventual="
                f"{row['avg_eventual_pnl_pct']:+.4f}%"
                f" | positive="
                f"{row['eventual_positive_pct']:.2f}%"
            )

    print()
    print("FLAT-PEAK RESOLUTION")
    print("-" * 100)

    if len(resolution_summary) == 0:

        print(
            "No PEAK_FLAT resolution observations."
        )

    else:

        for _, row in resolution_summary.iterrows():

            print(
                f"{row['flat_resolution']:<32}"
                f" n={int(row['observations']):3d}"
                f" trades="
                f"{int(row['unique_trades']):3d}"
                f" | dP&L="
                f"{row['avg_pnl_change_pct']:+.4f}%"
                f" | dPeak="
                f"{row['avg_peak_change_pct']:+.4f}%"
                f" | eventual="
                f"{row['avg_eventual_pnl_pct']:+.4f}%"
                f" | positive="
                f"{row['eventual_positive_pct']:.2f}%"
            )

    print()
    print("OUTPUT")
    print("-" * 100)

    print(
        TRANSITIONS_OUT
    )

    print(
        SUMMARY_OUT
    )

    print(
        OUT_DIR
        / "nvda_peak_flat_resolution_summary.csv"
    )

    print(
        TRADE_SUMMARY_OUT
    )

    print(
        METADATA_OUT
    )

    print()
    print("=" * 100)
    print("EXPERIMENT #43 COMPLETE")
    print("=" * 100)
    print()


if __name__ == "__main__":
    main()

