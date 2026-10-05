"""
================================================================================
EXPERIMENT #39 — NVDA PROFIT GIVEBACK PURE OBSERVATION
================================================================================

Purpose
-------
Measure how much already-earned profit is given back when a profitable
NVDA trade develops a pullback, and what happens afterward.

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

Source
------
Experiment #38 event output:

    kiss/results/exp38_profit_at_v/nvda_profit_at_v_events.csv

Important
---------
A trade may contain multiple profit-at-V events.

Therefore:
    - event statistics describe EVENTS
    - unique-trade counts are reported separately
    - events are NOT treated as independent trades

Key quantity
------------
profit_giveback_pct_of_peak

Example:

    prior favorable peak = +0.50%
    pullback             =  0.10%

    giveback fraction = 0.10 / 0.50 = 20%

This describes how much of the previously earned profit was surrendered.

It does NOT establish an exit threshold.

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
    "kiss/results/exp38_profit_at_v/nvda_profit_at_v_events.csv"
)

OUTPUT_DIR = Path(
    "kiss/results/exp39_profit_giveback"
)

EVENT_OUTPUT = OUTPUT_DIR / "nvda_profit_giveback_events.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "nvda_profit_giveback_summary.csv"
TRADE_OUTPUT = OUTPUT_DIR / "nvda_profit_giveback_trade_summary.csv"
QUANTILE_OUTPUT = OUTPUT_DIR / "nvda_profit_giveback_quantiles.csv"
METADATA_OUTPUT = OUTPUT_DIR / "exp39_metadata.txt"


# =============================================================================
# NUMERIC COLUMNS FROM EXPERIMENT #38
# =============================================================================

NUMERIC_COLUMNS = [
    "entry_price",
    "pnl_at_v_pct",
    "net_pnl_at_v_pct",
    "favorable_peak_before_v_pct",
    "initial_pullback_pct",
    "eventual_pnl_hindsight_pct",
    "max_profit_after_v_pct",
    "minimum_pnl_after_v_pct",
    "max_pullback_after_v_pct",
    "recovery_minutes",
    "pnl_after_5m_pct",
    "pnl_after_10m_pct",
    "pnl_after_15m_pct",
    "pnl_after_30m_pct",
    "pnl_after_60m_pct",
]


# =============================================================================
# HELPERS
# =============================================================================

def safe_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Convert selected columns to numeric values.

    Invalid or blank values become NaN.
    """
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


def safe_divide(
    numerator: pd.Series,
    denominator: pd.Series,
) -> pd.Series:
    """
    Divide while protecting against zero/invalid denominators.
    """
    denominator = denominator.replace(
        [np.inf, -np.inf, 0],
        np.nan,
    )

    result = numerator / denominator

    return result.replace(
        [np.inf, -np.inf],
        np.nan,
    )


def print_line():
    print("-" * 90)


def print_header(title: str):
    print("=" * 90)
    print(title)
    print("=" * 90)


# =============================================================================
# LOAD
# =============================================================================

def load_events() -> pd.DataFrame:

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Experiment #38 event file not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    if df.empty:
        raise ValueError(
            "Experiment #38 event file is empty."
        )

    required_columns = [
        "case_id",
        "trade_id",
        "symbol",
        "direction",
        "event_time_utc",
        "entry_time_utc",
        "entry_price",
        "pnl_at_v_pct",
        "favorable_peak_before_v_pct",
        "initial_pullback_pct",
        "eventual_pnl_hindsight_pct",
        "max_profit_after_v_pct",
        "minimum_pnl_after_v_pct",
        "max_pullback_after_v_pct",
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
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Experiment #38 event file is missing required columns:\n"
            + "\n".join(missing)
        )

    df = safe_numeric(
        df,
        NUMERIC_COLUMNS,
    )

    return df


# =============================================================================
# CALCULATE EVENT-LEVEL OBSERVATIONS
# =============================================================================

def calculate_event_metrics(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()

    # -------------------------------------------------------------------------
    # 1. Absolute amount of profit surrendered from the prior favorable peak.
    #
    # This is already represented by initial_pullback_pct in Experiment #38.
    # Keep an explicit field so #39 is self-contained.
    # -------------------------------------------------------------------------

    out["absolute_profit_giveback_pct"] = (
        out["initial_pullback_pct"]
    )

    # -------------------------------------------------------------------------
    # 2. Fraction of previously earned profit that was given back.
    #
    # Example:
    #
    # peak  = 0.50%
    # pullback = 0.10%
    #
    # 0.10 / 0.50 * 100 = 20%
    # -------------------------------------------------------------------------

    out["profit_giveback_pct_of_peak"] = safe_divide(
        out["initial_pullback_pct"],
        out["favorable_peak_before_v_pct"],
    ) * 100.0

    # -------------------------------------------------------------------------
    # 3. How much of the prior favorable peak remained at the V.
    # -------------------------------------------------------------------------

    out["remaining_profit_pct_of_peak"] = safe_divide(
        out["pnl_at_v_pct"],
        out["favorable_peak_before_v_pct"],
    ) * 100.0

    # -------------------------------------------------------------------------
    # 4. Additional gross profit achieved after the V.
    # -------------------------------------------------------------------------

    out["additional_profit_after_v_pct"] = (
        out["max_profit_after_v_pct"]
        - out["pnl_at_v_pct"]
    )

    # -------------------------------------------------------------------------
    # 5. Maximum drawdown after V measured from P&L at V.
    #
    # Positive value means additional adverse movement after the event.
    # -------------------------------------------------------------------------

    out["additional_drawdown_after_v_pct"] = (
        out["pnl_at_v_pct"]
        - out["minimum_pnl_after_v_pct"]
    )

    # -------------------------------------------------------------------------
    # 6. Eventual change from P&L at V.
    #
    # This is hindsight/reference information only.
    # -------------------------------------------------------------------------

    out["eventual_change_from_v_pct"] = (
        out["eventual_pnl_hindsight_pct"]
        - out["pnl_at_v_pct"]
    )

    # -------------------------------------------------------------------------
    # 7. Did the event remain profitable relative to entry?
    # -------------------------------------------------------------------------

    out["eventual_positive_hindsight"] = (
        out["eventual_pnl_hindsight_pct"] > 0
    )

    # -------------------------------------------------------------------------
    # 8. Did P&L at V cover the prior peak?
    #
    # This should normally be true because the event definition is based on
    # a profitable V/pullback, but we measure it rather than assume it.
    # -------------------------------------------------------------------------

    out["pnl_at_v_positive"] = (
        out["pnl_at_v_pct"] > 0
    )

    # -------------------------------------------------------------------------
    # 9. Giveback fraction category.
    #
    # IMPORTANT:
    # These are descriptive labels only.
    # They are NOT trading thresholds.
    #
    # Use data-derived quartiles later instead of inventing trading levels.
    # -------------------------------------------------------------------------

    valid = out["profit_giveback_pct_of_peak"].dropna()

    if len(valid) >= 4:
        q25 = valid.quantile(0.25)
        q50 = valid.quantile(0.50)
        q75 = valid.quantile(0.75)

        def giveback_bucket(value):
            if pd.isna(value):
                return "UNDEFINED"

            if value <= q25:
                return "Q1_LOW_GIVEBACK"

            if value <= q50:
                return "Q2"

            if value <= q75:
                return "Q3"

            return "Q4_HIGH_GIVEBACK"

        out["giveback_distribution_quartile"] = (
            out["profit_giveback_pct_of_peak"]
            .apply(giveback_bucket)
        )

    else:
        out["giveback_distribution_quartile"] = (
            "INSUFFICIENT_DATA"
        )

    return out


# =============================================================================
# EVENT SUMMARY
# =============================================================================

def build_event_summary(df: pd.DataFrame) -> pd.DataFrame:

    rows = []

    total_events = len(df)
    unique_trades = df["trade_id"].nunique()
    unique_cases = df["case_id"].nunique()

    rows.append(
        {
            "section": "population",
            "metric": "event_count",
            "value": total_events,
        }
    )

    rows.append(
        {
            "section": "population",
            "metric": "unique_trades",
            "value": unique_trades,
        }
    )

    rows.append(
        {
            "section": "population",
            "metric": "unique_cases",
            "value": unique_cases,
        }
    )

    # -------------------------------------------------------------------------
    # P&L at V
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "pnl_at_v",
            "metric": "average_pnl_at_v_pct",
            "value": df["pnl_at_v_pct"].mean(),
        }
    )

    rows.append(
        {
            "section": "pnl_at_v",
            "metric": "median_pnl_at_v_pct",
            "value": df["pnl_at_v_pct"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Prior peak
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "prior_peak",
            "metric": "average_prior_peak_pct",
            "value": df["favorable_peak_before_v_pct"].mean(),
        }
    )

    rows.append(
        {
            "section": "prior_peak",
            "metric": "median_prior_peak_pct",
            "value": df["favorable_peak_before_v_pct"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Absolute giveback
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "absolute_giveback",
            "metric": "average_initial_pullback_pct",
            "value": df["absolute_profit_giveback_pct"].mean(),
        }
    )

    rows.append(
        {
            "section": "absolute_giveback",
            "metric": "median_initial_pullback_pct",
            "value": df["absolute_profit_giveback_pct"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Giveback as percentage of earned profit
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "profit_giveback_fraction",
            "metric": "average_giveback_pct_of_peak",
            "value": df["profit_giveback_pct_of_peak"].mean(),
        }
    )

    rows.append(
        {
            "section": "profit_giveback_fraction",
            "metric": "median_giveback_pct_of_peak",
            "value": df["profit_giveback_pct_of_peak"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Remaining profit
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "remaining_profit",
            "metric": "average_remaining_profit_pct_of_peak",
            "value": df["remaining_profit_pct_of_peak"].mean(),
        }
    )

    rows.append(
        {
            "section": "remaining_profit",
            "metric": "median_remaining_profit_pct_of_peak",
            "value": df["remaining_profit_pct_of_peak"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Additional profit after V
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "after_v",
            "metric": "average_additional_profit_after_v_pct",
            "value": df["additional_profit_after_v_pct"].mean(),
        }
    )

    rows.append(
        {
            "section": "after_v",
            "metric": "median_additional_profit_after_v_pct",
            "value": df["additional_profit_after_v_pct"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Additional drawdown after V
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "after_v",
            "metric": "average_additional_drawdown_after_v_pct",
            "value": df["additional_drawdown_after_v_pct"].mean(),
        }
    )

    rows.append(
        {
            "section": "after_v",
            "metric": "median_additional_drawdown_after_v_pct",
            "value": df["additional_drawdown_after_v_pct"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Eventual change
    # -------------------------------------------------------------------------

    rows.append(
        {
            "section": "eventual",
            "metric": "average_eventual_change_from_v_pct",
            "value": df["eventual_change_from_v_pct"].mean(),
        }
    )

    rows.append(
        {
            "section": "eventual",
            "metric": "median_eventual_change_from_v_pct",
            "value": df["eventual_change_from_v_pct"].median(),
        }
    )

    # -------------------------------------------------------------------------
    # Recovery
    # -------------------------------------------------------------------------

    recovery = df["recovered_previous_peak"].astype(str).str.lower() == "true"

    rows.append(
        {
            "section": "recovery",
            "metric": "recovered_previous_peak_count",
            "value": int(recovery.sum()),
        }
    )

    rows.append(
        {
            "section": "recovery",
            "metric": "recovered_previous_peak_pct",
            "value": recovery.mean() * 100.0,
        }
    )

    recovery_times = df.loc[
        recovery,
        "recovery_minutes",
    ].dropna()

    rows.append(
        {
            "section": "recovery",
            "metric": "average_recovery_minutes",
            "value": (
                recovery_times.mean()
                if len(recovery_times)
                else np.nan
            ),
        }
    )

    rows.append(
        {
            "section": "recovery",
            "metric": "median_recovery_minutes",
            "value": (
                recovery_times.median()
                if len(recovery_times)
                else np.nan
            ),
        }
    )

    # -------------------------------------------------------------------------
    # Cost coverage
    # -------------------------------------------------------------------------

    if "cost_covered_at_v" in df.columns:
        cost_covered = (
            df["cost_covered_at_v"]
            .astype(str)
            .str.lower()
            .eq("true")
        )

        rows.append(
            {
                "section": "cost",
                "metric": "cost_covered_event_count",
                "value": int(cost_covered.sum()),
            }
        )

        rows.append(
            {
                "section": "cost",
                "metric": "cost_covered_event_pct",
                "value": cost_covered.mean() * 100.0,
            }
        )

    # -------------------------------------------------------------------------
    # Observation outcomes
    # -------------------------------------------------------------------------

    outcome_counts = (
        df["observation_outcome"]
        .value_counts(dropna=False)
    )

    for outcome, count in outcome_counts.items():

        rows.append(
            {
                "section": "observation_outcome",
                "metric": f"count_{outcome}",
                "value": int(count),
            }
        )

        rows.append(
            {
                "section": "observation_outcome",
                "metric": f"pct_{outcome}",
                "value": (
                    float(count)
                    / total_events
                    * 100.0
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# QUANTILE SUMMARY
# =============================================================================

def build_quantile_summary(df: pd.DataFrame) -> pd.DataFrame:

    rows = []

    metrics = {
        "pnl_at_v_pct": "P&L at V",
        "favorable_peak_before_v_pct": "Prior favorable peak",
        "absolute_profit_giveback_pct": "Absolute profit giveback",
        "profit_giveback_pct_of_peak": "Giveback % of prior peak",
        "remaining_profit_pct_of_peak": "Remaining profit % of prior peak",
        "additional_profit_after_v_pct": "Additional profit after V",
        "additional_drawdown_after_v_pct": "Additional drawdown after V",
        "eventual_change_from_v_pct": "Eventual change from V",
    }

    quantiles = [
        0.10,
        0.25,
        0.50,
        0.75,
        0.90,
    ]

    for column, description in metrics.items():

        series = pd.to_numeric(
            df[column],
            errors="coerce",
        ).dropna()

        for q in quantiles:

            rows.append(
                {
                    "metric": column,
                    "description": description,
                    "quantile": q,
                    "value": (
                        series.quantile(q)
                        if len(series)
                        else np.nan
                    ),
                    "n": len(series),
                }
            )

    return pd.DataFrame(rows)


# =============================================================================
# DESCRIPTIVE GIVEBACK DISTRIBUTION
# =============================================================================

def build_distribution_summary(df: pd.DataFrame) -> pd.DataFrame:

    rows = []

    for bucket, group in df.groupby(
        "giveback_distribution_quartile",
        dropna=False,
        sort=False,
    ):

        recovery = (
            group["recovered_previous_peak"]
            .astype(str)
            .str.lower()
            .eq("true")
        )

        rows.append(
            {
                "giveback_distribution_quartile": bucket,
                "event_count": len(group),
                "unique_trades": group["trade_id"].nunique(),
                "avg_pnl_at_v_pct": group["pnl_at_v_pct"].mean(),
                "median_pnl_at_v_pct": group["pnl_at_v_pct"].median(),
                "avg_prior_peak_pct": (
                    group["favorable_peak_before_v_pct"].mean()
                ),
                "avg_absolute_giveback_pct": (
                    group["absolute_profit_giveback_pct"].mean()
                ),
                "avg_giveback_pct_of_peak": (
                    group["profit_giveback_pct_of_peak"].mean()
                ),
                "median_giveback_pct_of_peak": (
                    group["profit_giveback_pct_of_peak"].median()
                ),
                "recovered_previous_peak_count": (
                    int(recovery.sum())
                ),
                "recovered_previous_peak_pct": (
                    recovery.mean() * 100.0
                ),
                "avg_eventual_pnl_pct": (
                    group["eventual_pnl_hindsight_pct"].mean()
                ),
                "median_eventual_pnl_pct": (
                    group["eventual_pnl_hindsight_pct"].median()
                ),
                "avg_eventual_change_from_v_pct": (
                    group["eventual_change_from_v_pct"].mean()
                ),
                "avg_additional_drawdown_after_v_pct": (
                    group["additional_drawdown_after_v_pct"].mean()
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# TRADE-LEVEL SUMMARY
# =============================================================================

def build_trade_summary(df: pd.DataFrame) -> pd.DataFrame:

    rows = []

    for trade_id, group in df.groupby(
        "trade_id",
        sort=False,
    ):

        giveback = group["profit_giveback_pct_of_peak"].dropna()

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

                "max_pnl_at_v_pct": (
                    group["pnl_at_v_pct"].max()
                ),

                "max_prior_peak_pct": (
                    group["favorable_peak_before_v_pct"].max()
                ),

                "max_absolute_giveback_pct": (
                    group["absolute_profit_giveback_pct"].max()
                ),

                "max_giveback_pct_of_peak": (
                    giveback.max()
                    if len(giveback)
                    else np.nan
                ),

                "median_giveback_pct_of_peak": (
                    giveback.median()
                    if len(giveback)
                    else np.nan
                ),

                "eventual_pnl_hindsight_pct": (
                    group["eventual_pnl_hindsight_pct"].iloc[0]
                ),

                "recovered_any_previous_peak": (
                    group["recovered_previous_peak"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .any()
                ),

                "observation_outcomes": (
                    "|".join(
                        group["observation_outcome"]
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
    event_summary: pd.DataFrame,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "EXPERIMENT #39 — NVDA PROFIT GIVEBACK PURE OBSERVATION",
        "",
        "Purpose:",
        (
            "Measure how much already-earned profit is given back "
            "during a profitable pullback and what happens afterward."
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
            "Multiple events can belong to the same trade. "
            "Event counts therefore must not be interpreted as "
            "independent trade counts."
        ),
        "",
        "Key quantity:",
        (
            "profit_giveback_pct_of_peak = "
            "initial_pullback_pct / favorable_peak_before_v_pct * 100"
        ),
        "",
        "This quantity describes the fraction of previously earned "
        "profit surrendered during the observed pullback.",
        "",
        "It is descriptive only and does not establish a trading threshold.",
        "",
        "All eventual P&L fields are hindsight/reference fields.",
        "",
        "Experiment #39 does not change AIMn.",
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
        "EXPERIMENT #39 — NVDA PROFIT GIVEBACK PURE OBSERVATION"
    )

    print()
    print("RESEARCH ONLY")
    print_line()
    print("No entry rule")
    print("No exit rule")
    print("No V threshold")
    print("No minor/medium/major classification")
    print("No optimization")
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
        f"Experiment #38 events : {len(df)}"
    )

    print(
        f"Unique NVDA trades     : {df['trade_id'].nunique()}"
    )

    print(
        f"Unique transition cases: {df['case_id'].nunique()}"
    )

    # -------------------------------------------------------------------------
    # Calculate
    # -------------------------------------------------------------------------

    df = calculate_event_metrics(df)

    # -------------------------------------------------------------------------
    # Build outputs
    # -------------------------------------------------------------------------

    event_summary = build_event_summary(df)

    quantile_summary = build_quantile_summary(df)

    distribution_summary = build_distribution_summary(df)

    trade_summary = build_trade_summary(df)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Event output
    df.to_csv(
        EVENT_OUTPUT,
        index=False,
    )

    # Summary combines main metrics + descriptive distribution
    combined_summary = pd.concat(
        [
            event_summary.assign(
                summary_type="overall"
            ),
            distribution_summary.assign(
                summary_type="giveback_distribution"
            ),
        ],
        ignore_index=True,
        sort=False,
    )

    combined_summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    quantile_summary.to_csv(
        QUANTILE_OUTPUT,
        index=False,
    )

    trade_summary.to_csv(
        TRADE_OUTPUT,
        index=False,
    )

    write_metadata(
        df,
        event_summary,
    )

    # -------------------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------------------

    print()
    print("PROFIT AT V")
    print_line()

    print(
        f"Average P&L at V       : "
        f"{df['pnl_at_v_pct'].mean():.4f}%"
    )

    print(
        f"Median P&L at V        : "
        f"{df['pnl_at_v_pct'].median():.4f}%"
    )

    print()
    print("PRIOR FAVORABLE PEAK")
    print_line()

    print(
        f"Average prior peak     : "
        f"{df['favorable_peak_before_v_pct'].mean():.4f}%"
    )

    print(
        f"Median prior peak      : "
        f"{df['favorable_peak_before_v_pct'].median():.4f}%"
    )

    print()
    print("ABSOLUTE PROFIT GIVEBACK")
    print_line()

    print(
        f"Average giveback       : "
        f"{df['absolute_profit_giveback_pct'].mean():.4f}%"
    )

    print(
        f"Median giveback        : "
        f"{df['absolute_profit_giveback_pct'].median():.4f}%"
    )

    print()
    print("PROFIT GIVEBACK AS % OF EARNED PROFIT")
    print_line()

    print(
        f"Average giveback/peak  : "
        f"{df['profit_giveback_pct_of_peak'].mean():.2f}%"
    )

    print(
        f"Median giveback/peak   : "
        f"{df['profit_giveback_pct_of_peak'].median():.2f}%"
    )

    print()
    print("REMAINING PROFIT")
    print_line()

    print(
        f"Average remaining      : "
        f"{df['remaining_profit_pct_of_peak'].mean():.2f}% "
        f"of prior peak"
    )

    print(
        f"Median remaining       : "
        f"{df['remaining_profit_pct_of_peak'].median():.2f}% "
        f"of prior peak"
    )

    print()
    print("AFTER V")
    print_line()

    print(
        f"Additional profit avg  : "
        f"{df['additional_profit_after_v_pct'].mean():.4f}%"
    )

    print(
        f"Additional profit med  : "
        f"{df['additional_profit_after_v_pct'].median():.4f}%"
    )

    print(
        f"Additional drawdown avg: "
        f"{df['additional_drawdown_after_v_pct'].mean():.4f}%"
    )

    print(
        f"Additional drawdown med: "
        f"{df['additional_drawdown_after_v_pct'].median():.4f}%"
    )

    print()
    print("RECOVERY")
    print_line()

    recovered = (
        df["recovered_previous_peak"]
        .astype(str)
        .str.lower()
        .eq("true")
    )

    recovery_times = df.loc[
        recovered,
        "recovery_minutes",
    ].dropna()

    print(
        f"Recovered previous peak: "
        f"{int(recovered.sum())}/{len(df)}"
    )

    print(
        f"Recovery percentage     : "
        f"{recovered.mean() * 100:.2f}%"
    )

    print(
        f"Average recovery time   : "
        f"{recovery_times.mean():.2f} minutes"
        if len(recovery_times)
        else "Average recovery time   : n/a"
    )

    print(
        f"Median recovery time    : "
        f"{recovery_times.median():.2f} minutes"
        if len(recovery_times)
        else "Median recovery time    : n/a"
    )

    print()
    print("EVENTUAL CHANGE FROM V")
    print_line()

    print(
        f"Average eventual change : "
        f"{df['eventual_change_from_v_pct'].mean():.4f}%"
    )

    print(
        f"Median eventual change  : "
        f"{df['eventual_change_from_v_pct'].median():.4f}%"
    )

    print()
    print("OBSERVATION OUTCOMES")
    print_line()

    counts = (
        df["observation_outcome"]
        .value_counts()
    )

    for outcome, count in counts.items():

        pct = (
            count
            / len(df)
            * 100.0
        )

        print(
            f"{outcome:<48} "
            f"{count:>4} "
            f"({pct:6.2f}%)"
        )

    print()
    print("GIVEBACK DISTRIBUTION")
    print_line()

    distribution = build_distribution_summary(df)

    for _, row in distribution.iterrows():

        print(
            f"{str(row['giveback_distribution_quartile']):<24} "
            f"events={int(row['event_count']):>3} "
            f"trades={int(row['unique_trades']):>3} "
            f"avg_giveback={row['avg_giveback_pct_of_peak']:7.2f}% "
            f"recovered={row['recovered_previous_peak_pct']:6.2f}%"
        )

    print()
    print("QUANTILES — GIVEBACK % OF PRIOR PEAK")
    print_line()

    q = quantile_summary[
        quantile_summary["metric"]
        == "profit_giveback_pct_of_peak"
    ]

    for _, row in q.iterrows():

        print(
            f"Q{int(row['quantile'] * 100):>2} "
            f"= {row['value']:.2f}%"
        )

    print()
    print("IMPORTANT")
    print_line()

    print(
        "This experiment describes how much earned profit was given back."
    )

    print(
        "It does not tell AIMn to exit."
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
    print(QUANTILE_OUTPUT)
    print(METADATA_OUTPUT)

    print()
    print("=" * 90)
    print("EXPERIMENT #39 COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
