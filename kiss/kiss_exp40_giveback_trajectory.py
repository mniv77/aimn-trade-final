"""
================================================================================
EXPERIMENT #40 — NVDA PROFIT GIVEBACK TRAJECTORY
================================================================================

QUESTION
--------
After a profitable V begins giving back already-earned profit, what happens
next?

Does the trade:

    V -> recover -> continue

or:

    V -> give back more -> deteriorate

This is a PURE OBSERVATION experiment.

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
Experiment #39 event output:

    kiss/results/exp39_profit_giveback/
        nvda_profit_giveback_events.csv

The Experiment #38 event population is therefore preserved.

IMPORTANT
---------
A trade can contain multiple V events.

Events are observations, not independent trades.

We therefore report both:
    - event count
    - unique trade count

KEY QUESTION
------------
After the V, does the trade continue in its original direction or does the
profit giveback develop into deeper deterioration?

The experiment records actual P&L changes at:

    +5m
    +10m
    +15m
    +30m
    +60m

and compares those with:

    P&L at V
    prior favorable peak
    initial giveback
    additional profit
    additional drawdown
    eventual P&L

No threshold is selected.

================================================================================
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

INPUT_FILE = Path(
    "kiss/results/exp39_profit_giveback/"
    "nvda_profit_giveback_events.csv"
)

OUTPUT_DIR = Path(
    "kiss/results/exp40_giveback_trajectory"
)

EVENT_OUTPUT = OUTPUT_DIR / (
    "nvda_giveback_trajectory_events.csv"
)

SUMMARY_OUTPUT = OUTPUT_DIR / (
    "nvda_giveback_trajectory_summary.csv"
)

TRADE_OUTPUT = OUTPUT_DIR / (
    "nvda_giveback_trajectory_trade_summary.csv"
)

METADATA_OUTPUT = OUTPUT_DIR / (
    "exp40_metadata.txt"
)


# =============================================================================
# HELPERS
# =============================================================================

def safe_numeric(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:

    for column in columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


def print_header(title: str):

    print("=" * 90)
    print(title)
    print("=" * 90)


def print_line():

    print("-" * 90)


# =============================================================================
# LOAD
# =============================================================================

def load_events() -> pd.DataFrame:

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Experiment #39 output not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    if df.empty:

        raise ValueError(
            "Experiment #39 event file is empty."
        )

    required = [
        "case_id",
        "trade_id",
        "symbol",
        "direction",
        "event_time_utc",
        "entry_time_utc",
        "entry_price",
        "pnl_at_v_pct",
        "favorable_peak_before_v_pct",
        "absolute_profit_giveback_pct",
        "profit_giveback_pct_of_peak",
        "remaining_profit_pct_of_peak",
        "eventual_pnl_hindsight_pct",
        "additional_profit_after_v_pct",
        "additional_drawdown_after_v_pct",
        "eventual_change_from_v_pct",
        "recovered_previous_peak",
        "recovery_minutes",
        "observation_outcome",
        "pnl_after_5m_pct",
        "pnl_after_10m_pct",
        "pnl_after_15m_pct",
        "pnl_after_30m_pct",
        "pnl_after_60m_pct",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Experiment #39 file is missing columns:\n"
            + "\n".join(missing)
        )

    numeric_columns = [
        "entry_price",
        "pnl_at_v_pct",
        "favorable_peak_before_v_pct",
        "absolute_profit_giveback_pct",
        "profit_giveback_pct_of_peak",
        "remaining_profit_pct_of_peak",
        "eventual_pnl_hindsight_pct",
        "additional_profit_after_v_pct",
        "additional_drawdown_after_v_pct",
        "eventual_change_from_v_pct",
        "recovery_minutes",
        "pnl_after_5m_pct",
        "pnl_after_10m_pct",
        "pnl_after_15m_pct",
        "pnl_after_30m_pct",
        "pnl_after_60m_pct",
    ]

    df = safe_numeric(
        df,
        numeric_columns,
    )

    return df


# =============================================================================
# TRAJECTORY METRICS
# =============================================================================

def calculate_trajectory(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()

    # -------------------------------------------------------------------------
    # Change from P&L at V.
    #
    # Positive = trade improved after V.
    # Negative = trade deteriorated after V.
    # -------------------------------------------------------------------------

    for minutes in [5, 10, 15, 30, 60]:

        pnl_column = f"pnl_after_{minutes}m_pct"

        change_column = (
            f"change_from_v_after_{minutes}m_pct"
        )

        out[change_column] = (
            out[pnl_column]
            - out["pnl_at_v_pct"]
        )

    # -------------------------------------------------------------------------
    # Did P&L improve after V?
    # -------------------------------------------------------------------------

    out["improved_after_v_5m"] = (
        out["change_from_v_after_5m_pct"] > 0
    )

    out["improved_after_v_10m"] = (
        out["change_from_v_after_10m_pct"] > 0
    )

    out["improved_after_v_15m"] = (
        out["change_from_v_after_15m_pct"] > 0
    )

    out["improved_after_v_30m"] = (
        out["change_from_v_after_30m_pct"] > 0
    )

    out["improved_after_v_60m"] = (
        out["change_from_v_after_60m_pct"] > 0
    )

    # -------------------------------------------------------------------------
    # Did P&L fall below zero after V?
    # -------------------------------------------------------------------------

    for minutes in [5, 10, 15, 30, 60]:

        pnl_column = f"pnl_after_{minutes}m_pct"

        flag_column = (
            f"negative_after_{minutes}m"
        )

        out[flag_column] = (
            out[pnl_column] < 0
        )

    # -------------------------------------------------------------------------
    # Did the trade recover the P&L that existed at V?
    #
    # This is different from recovering the previous favorable peak.
    # -------------------------------------------------------------------------

    for minutes in [5, 10, 15, 30, 60]:

        pnl_column = f"pnl_after_{minutes}m_pct"

        recovered_column = (
            f"recovered_v_pnl_after_{minutes}m"
        )

        out[recovered_column] = (
            out[pnl_column]
            >= out["pnl_at_v_pct"]
        )

    # -------------------------------------------------------------------------
    # Did the trade exceed the prior favorable peak?
    #
    # This uses the stored post-V P&L values as observations.
    # -------------------------------------------------------------------------

    for minutes in [5, 10, 15, 30, 60]:

        pnl_column = f"pnl_after_{minutes}m_pct"

        peak_column = (
            f"exceeded_previous_peak_after_{minutes}m"
        )

        out[peak_column] = (
            out[pnl_column]
            >= out["favorable_peak_before_v_pct"]
        )

    # -------------------------------------------------------------------------
    # Best observed P&L across available post-V checkpoints.
    # -------------------------------------------------------------------------

    checkpoint_columns = [
        "pnl_after_5m_pct",
        "pnl_after_10m_pct",
        "pnl_after_15m_pct",
        "pnl_after_30m_pct",
        "pnl_after_60m_pct",
    ]

    out["best_checkpoint_pnl_after_v_pct"] = (
        out[checkpoint_columns].max(
            axis=1,
            skipna=True,
        )
    )

    out["worst_checkpoint_pnl_after_v_pct"] = (
        out[checkpoint_columns].min(
            axis=1,
            skipna=True,
        )
    )

    # -------------------------------------------------------------------------
    # Best improvement from V at the available checkpoints.
    # -------------------------------------------------------------------------

    out["best_checkpoint_change_from_v_pct"] = (
        out["best_checkpoint_pnl_after_v_pct"]
        - out["pnl_at_v_pct"]
    )

    # -------------------------------------------------------------------------
    # Worst deterioration from V at available checkpoints.
    # -------------------------------------------------------------------------

    out["worst_checkpoint_change_from_v_pct"] = (
        out["worst_checkpoint_pnl_after_v_pct"]
        - out["pnl_at_v_pct"]
    )

    # -------------------------------------------------------------------------
    # Simple descriptive trajectory label.
    #
    # These labels are descriptive only.
    # They are NOT trading classifications.
    #
    # CONTINUED:
    #     all available post-V checkpoints are >= P&L at V
    #
    # DETERIORATING:
    #     all available post-V checkpoints are < P&L at V
    #
    # MIXED:
    #     some improve and some deteriorate
    #
    # INSUFFICIENT:
    #     no post-V checkpoint available
    # -------------------------------------------------------------------------

    def classify_row(row):

        values = [
            row.get(
                "pnl_after_5m_pct",
                np.nan,
            ),
            row.get(
                "pnl_after_10m_pct",
                np.nan,
            ),
            row.get(
                "pnl_after_15m_pct",
                np.nan,
            ),
            row.get(
                "pnl_after_30m_pct",
                np.nan,
            ),
            row.get(
                "pnl_after_60m_pct",
                np.nan,
            ),
        ]

        values = [
            value
            for value in values
            if pd.notna(value)
        ]

        if not values:
            return "INSUFFICIENT"

        changes = [
            value - row["pnl_at_v_pct"]
            for value in values
        ]

        has_positive = any(
            change > 0
            for change in changes
        )

        has_negative = any(
            change < 0
            for change in changes
        )

        if has_positive and has_negative:
            return "MIXED"

        if has_positive:
            return "CONTINUED"

        if has_negative:
            return "DETERIORATING"

        return "FLAT"

    out["post_v_trajectory"] = out.apply(
        classify_row,
        axis=1,
    )

    return out


# =============================================================================
# CHECKPOINT SUMMARY
# =============================================================================

def build_checkpoint_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for minutes in [5, 10, 15, 30, 60]:

        pnl_column = (
            f"pnl_after_{minutes}m_pct"
        )

        change_column = (
            f"change_from_v_after_{minutes}m_pct"
        )

        series = df[pnl_column].dropna()

        changes = df[change_column].dropna()

        if len(series) == 0:
            continue

        rows.append(
            {
                "checkpoint_minutes": minutes,
                "n": len(series),
                "avg_pnl_pct": series.mean(),
                "median_pnl_pct": series.median(),
                "avg_change_from_v_pct": changes.mean(),
                "median_change_from_v_pct": changes.median(),
                "improved_count": int(
                    (changes > 0).sum()
                ),
                "improved_pct": (
                    (changes > 0).mean()
                    * 100.0
                ),
                "deteriorated_count": int(
                    (changes < 0).sum()
                ),
                "deteriorated_pct": (
                    (changes < 0).mean()
                    * 100.0
                ),
                "flat_count": int(
                    (changes == 0).sum()
                ),
                "negative_pnl_count": int(
                    (series < 0).sum()
                ),
                "negative_pnl_pct": (
                    (series < 0).mean()
                    * 100.0
                ),
                "recovered_v_pnl_count": int(
                    (
                        df.loc[
                            series.index,
                            pnl_column,
                        ]
                        >=
                        df.loc[
                            series.index,
                            "pnl_at_v_pct",
                        ]
                    ).sum()
                ),
                "recovered_previous_peak_count": int(
                    (
                        df.loc[
                            series.index,
                            pnl_column,
                        ]
                        >=
                        df.loc[
                            series.index,
                            "favorable_peak_before_v_pct",
                        ]
                    ).sum()
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# TRAJECTORY SUMMARY
# =============================================================================

def build_trajectory_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    total = len(df)

    rows.append(
        {
            "section": "population",
            "metric": "event_count",
            "value": total,
        }
    )

    rows.append(
        {
            "section": "population",
            "metric": "unique_trades",
            "value": df["trade_id"].nunique(),
        }
    )

    rows.append(
        {
            "section": "population",
            "metric": "unique_cases",
            "value": df["case_id"].nunique(),
        }
    )

    # -------------------------------------------------------------------------
    # Overall trajectory
    # -------------------------------------------------------------------------

    trajectory_counts = (
        df["post_v_trajectory"]
        .value_counts()
    )

    for label, count in trajectory_counts.items():

        rows.append(
            {
                "section": "trajectory",
                "metric": f"count_{label}",
                "value": int(count),
            }
        )

        rows.append(
            {
                "section": "trajectory",
                "metric": f"pct_{label}",
                "value": (
                    count
                    / total
                    * 100.0
                ),
            }
        )

    # -------------------------------------------------------------------------
    # Improvement/deterioration across checkpoints
    # -------------------------------------------------------------------------

    for minutes in [5, 10, 15, 30, 60]:

        column = (
            f"change_from_v_after_{minutes}m_pct"
        )

        series = df[column].dropna()

        if len(series) == 0:
            continue

        rows.append(
            {
                "section": "checkpoint",
                "metric": f"avg_change_{minutes}m_pct",
                "value": series.mean(),
            }
        )

        rows.append(
            {
                "section": "checkpoint",
                "metric": f"median_change_{minutes}m_pct",
                "value": series.median(),
            }
        )

        rows.append(
            {
                "section": "checkpoint",
                "metric": f"improved_pct_{minutes}m",
                "value": (
                    (series > 0).mean()
                    * 100.0
                ),
            }
        )

        rows.append(
            {
                "section": "checkpoint",
                "metric": f"deteriorated_pct_{minutes}m",
                "value": (
                    (series < 0).mean()
                    * 100.0
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# GIVEBACK VS TRAJECTORY
# =============================================================================

def build_giveback_vs_trajectory(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for trajectory, group in df.groupby(
        "post_v_trajectory",
        sort=False,
    ):

        rows.append(
            {
                "post_v_trajectory": trajectory,
                "event_count": len(group),
                "unique_trades": group["trade_id"].nunique(),

                "avg_pnl_at_v_pct": (
                    group["pnl_at_v_pct"].mean()
                ),

                "median_pnl_at_v_pct": (
                    group["pnl_at_v_pct"].median()
                ),

                "avg_prior_peak_pct": (
                    group[
                        "favorable_peak_before_v_pct"
                    ].mean()
                ),

                "avg_absolute_giveback_pct": (
                    group[
                        "absolute_profit_giveback_pct"
                    ].mean()
                ),

                "median_absolute_giveback_pct": (
                    group[
                        "absolute_profit_giveback_pct"
                    ].median()
                ),

                "avg_giveback_pct_of_peak": (
                    group[
                        "profit_giveback_pct_of_peak"
                    ].mean()
                ),

                "median_giveback_pct_of_peak": (
                    group[
                        "profit_giveback_pct_of_peak"
                    ].median()
                ),

                "avg_additional_profit_after_v_pct": (
                    group[
                        "additional_profit_after_v_pct"
                    ].mean()
                ),

                "avg_additional_drawdown_after_v_pct": (
                    group[
                        "additional_drawdown_after_v_pct"
                    ].mean()
                ),

                "avg_eventual_change_from_v_pct": (
                    group[
                        "eventual_change_from_v_pct"
                    ].mean()
                ),

                "median_eventual_change_from_v_pct": (
                    group[
                        "eventual_change_from_v_pct"
                    ].median()
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# TRADE SUMMARY
# =============================================================================

def build_trade_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for trade_id, group in df.groupby(
        "trade_id",
        sort=False,
    ):

        changes_5 = group[
            "change_from_v_after_5m_pct"
        ].dropna()

        changes_10 = group[
            "change_from_v_after_10m_pct"
        ].dropna()

        changes_15 = group[
            "change_from_v_after_15m_pct"
        ].dropna()

        changes_30 = group[
            "change_from_v_after_30m_pct"
        ].dropna()

        changes_60 = group[
            "change_from_v_after_60m_pct"
        ].dropna()

        all_changes = pd.concat(
            [
                changes_5,
                changes_10,
                changes_15,
                changes_30,
                changes_60,
            ],
            ignore_index=True,
        )

        rows.append(
            {
                "trade_id": trade_id,
                "symbol": group["symbol"].iloc[0],
                "direction": group["direction"].iloc[0],

                "event_count": len(group),

                "first_event_time_utc": (
                    group["event_time_utc"].iloc[0]
                ),

                "last_event_time_utc": (
                    group["event_time_utc"].iloc[-1]
                ),

                "max_giveback_pct_of_peak": (
                    group[
                        "profit_giveback_pct_of_peak"
                    ].max()
                ),

                "median_giveback_pct_of_peak": (
                    group[
                        "profit_giveback_pct_of_peak"
                    ].median()
                ),

                "best_change_from_v_pct": (
                    all_changes.max()
                    if len(all_changes)
                    else np.nan
                ),

                "worst_change_from_v_pct": (
                    all_changes.min()
                    if len(all_changes)
                    else np.nan
                ),

                "eventual_pnl_hindsight_pct": (
                    group[
                        "eventual_pnl_hindsight_pct"
                    ].iloc[0]
                ),

                "any_recovered_previous_peak": (
                    group[
                        "recovered_previous_peak"
                    ]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .any()
                ),

                "trajectory_labels": (
                    "|".join(
                        group[
                            "post_v_trajectory"
                        ]
                        .dropna()
                        .astype(str)
                        .unique()
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# METADATA
# =============================================================================

def write_metadata(
    df: pd.DataFrame,
):

    lines = [
        "EXPERIMENT #40 — NVDA PROFIT GIVEBACK TRAJECTORY",
        "",
        "Question:",
        (
            "After a profitable V begins giving back earned profit, "
            "what happens next?"
        ),
        "",
        "Research status:",
        "PURE OBSERVATION ONLY",
        "",
        "No entry rule.",
        "No exit rule.",
        "No V threshold.",
        "No minor/medium/major classification.",
        "No optimization.",
        "No parameter promotion.",
        "No production changes.",
        "No orders.",
        "No AI training.",
        "",
        "Source:",
        str(INPUT_FILE),
        "",
        f"Event count: {len(df)}",
        f"Unique trades: {df['trade_id'].nunique()}",
        f"Unique cases: {df['case_id'].nunique()}",
        "",
        "Important:",
        (
            "Multiple events may belong to the same trade. "
            "Events are therefore observations rather than "
            "independent trades."
        ),
        "",
        "Trajectory definition:",
        (
            "CONTINUED means all available post-V checkpoints "
            "improved relative to P&L at V."
        ),
        (
            "DETERIORATING means all available post-V checkpoints "
            "worsened relative to P&L at V."
        ),
        (
            "MIXED means both improvement and deterioration were "
            "observed across the available checkpoints."
        ),
        "",
        "These trajectory labels are descriptive only.",
        "They are not trading rules.",
        "",
        "All eventual P&L fields are hindsight/reference information.",
        "",
        "Experiment #40 does not change AIMn.",
    ]

    METADATA_OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    print_header(
        "EXPERIMENT #40 — NVDA PROFIT GIVEBACK TRAJECTORY"
    )

    print()
    print("RESEARCH ONLY")
    print_line()

    print("No entry rule")
    print("No exit rule")
    print("No V threshold")
    print("No minor/medium/major classification")
    print("No optimization")
    print("No parameter promotion")
    print("No production changes")
    print("No orders")
    print("No AI training")

    # -------------------------------------------------------------------------
    # Load
    # -------------------------------------------------------------------------

    df = load_events()

    print()
    print("DATA")
    print_line()

    print(
        f"Experiment #39 events : {len(df)}"
    )

    print(
        f"Unique NVDA trades     : "
        f"{df['trade_id'].nunique()}"
    )

    print(
        f"Unique transition cases: "
        f"{df['case_id'].nunique()}"
    )

    # -------------------------------------------------------------------------
    # Calculate
    # -------------------------------------------------------------------------

    df = calculate_trajectory(df)

    # -------------------------------------------------------------------------
    # Summaries
    # -------------------------------------------------------------------------

    checkpoint_summary = (
        build_checkpoint_summary(df)
    )

    trajectory_summary = (
        build_trajectory_summary(df)
    )

    giveback_summary = (
        build_giveback_vs_trajectory(df)
    )

    trade_summary = (
        build_trade_summary(df)
    )

    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        EVENT_OUTPUT,
        index=False,
    )

    combined_summary = pd.concat(
        [
            trajectory_summary.assign(
                summary_type="overall"
            ),
            checkpoint_summary.assign(
                summary_type="checkpoint"
            ),
            giveback_summary.assign(
                summary_type="giveback_vs_trajectory"
            ),
        ],
        ignore_index=True,
        sort=False,
    )

    combined_summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    trade_summary.to_csv(
        TRADE_OUTPUT,
        index=False,
    )

    write_metadata(df)

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print()
    print("POST-V TRAJECTORY")
    print_line()

    trajectory_counts = (
        df["post_v_trajectory"]
        .value_counts()
    )

    for label, count in trajectory_counts.items():

        pct = (
            count
            / len(df)
            * 100.0
        )

        print(
            f"{label:<24}"
            f"{count:>4} "
            f"({pct:6.2f}%)"
        )

    print()
    print("CHECKPOINTS — CHANGE FROM P&L AT V")
    print_line()

    for _, row in checkpoint_summary.iterrows():

        print(
            f"{int(row['checkpoint_minutes']):>2}m "
            f"n={int(row['n']):>3} "
            f"avg_change={row['avg_change_from_v_pct']:>8.4f}% "
            f"median_change={row['median_change_from_v_pct']:>8.4f}% "
            f"improved={row['improved_pct']:>6.2f}% "
            f"deteriorated={row['deteriorated_pct']:>6.2f}%"
        )

    print()
    print("P&L AFTER V")
    print_line()

    for minutes in [5, 10, 15, 30, 60]:

        column = (
            f"pnl_after_{minutes}m_pct"
        )

        series = df[column].dropna()

        if len(series) == 0:
            continue

        print(
            f"{minutes:>2}m "
            f"n={len(series):>3} "
            f"avg={series.mean():>8.4f}% "
            f"median={series.median():>8.4f}%"
        )

    print()
    print("GIVEBACK VS TRAJECTORY")
    print_line()

    for _, row in giveback_summary.iterrows():

        print(
            f"{str(row['post_v_trajectory']):<24}"
            f"events={int(row['event_count']):>3} "
            f"trades={int(row['unique_trades']):>3} "
            f"avg_giveback="
            f"{row['avg_giveback_pct_of_peak']:>7.2f}% "
            f"avg_eventual_change="
            f"{row['avg_eventual_change_from_v_pct']:>8.4f}%"
        )

    print()
    print("TRADE-LEVEL CHECK")
    print_line()

    print(
        f"Unique trades represented : "
        f"{trade_summary['trade_id'].nunique()}"
    )

    print(
        f"Trades with multiple events: "
        f"{int((trade_summary['event_count'] > 1).sum())}"
    )

    print(
        f"Trades with one event      : "
        f"{int((trade_summary['event_count'] == 1).sum())}"
    )

    print()
    print("IMPORTANT")
    print_line()

    print(
        "This experiment describes the trajectory after profit giveback."
    )

    print(
        "It does not tell AIMn to exit."
    )

    print(
        "It does not establish a giveback threshold."
    )

    print(
        "It does not establish a V threshold."
    )

    print(
        "It does not classify V events as minor, medium, or major."
    )

    print(
        "It does not change the trading system."
    )

    print()
    print("OUTPUT")
    print_line()

    print(EVENT_OUTPUT)
    print(SUMMARY_OUTPUT)
    print(TRADE_OUTPUT)
    print(METADATA_OUTPUT)

    print()
    print("=" * 90)
    print("EXPERIMENT #40 COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
