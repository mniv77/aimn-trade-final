#!/usr/bin/env python3

"""
AIMn KISS — Experiment #47
UNPROFITABLE V: NOISE vs CONTINUING REVERSAL

RESEARCH ONLY
-------------
No production strategy changes.
No orders.
No AI training.
No threshold promotion.
No re-entry simulation.

QUESTION
--------
At an unprofitable V:

    Is price merely making noise?

or

    Is the reversal continuing against the trade?

We inspect what happens immediately AFTER the causal V:

    V
    +5m
    +10m
    +15m
    +30m
    +60m

We do NOT create a trading rule.

This experiment is descriptive only.

IMPORTANT
---------
The current Experiment #46 sample is intentionally small.
If the available post-V observations are insufficient to classify
an event, it remains INSUFFICIENT.

We do not force a classification.
"""

from pathlib import Path
import pandas as pd
import numpy as np


# =============================================================================
# PATHS
# =============================================================================

BASE = Path.home() / "aimn-trade-final"

INPUT_FILE = (
    BASE
    / "kiss"
    / "results"
    / "exp46_not_yet_profitable_v"
    / "nvda_not_yet_profitable_v_events.csv"
)

OUTPUT_DIR = (
    BASE
    / "kiss"
    / "results"
    / "exp47_v_noise_vs_continuation"
)

OUTPUT_EVENTS = OUTPUT_DIR / "nvda_v_noise_vs_continuation_events.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "nvda_v_noise_vs_continuation_summary.csv"
OUTPUT_META = OUTPUT_DIR / "exp47_metadata.txt"


# =============================================================================
# SETTINGS
# =============================================================================

# We intentionally do NOT use a percentage threshold.
#
# These are observation horizons only.
HORIZONS = [5, 10, 15, 30, 60]


# =============================================================================
# HELPERS
# =============================================================================

def clean_numeric(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def first_existing(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


def safe_mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()) if len(s) else np.nan


def safe_median(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.median()) if len(s) else np.nan


def fmt_pct(value):
    if pd.isna(value):
        return "N/A"
    return f"{value:.4f}%"


# =============================================================================
# LOAD
# =============================================================================

def load_data():
    print("=" * 100)
    print("AIMn KISS — EXPERIMENT #47")
    print("UNPROFITABLE V: NOISE vs CONTINUING REVERSAL")
    print("=" * 100)
    print()
    print("Research only.")
    print("No production strategy changes.")
    print("No orders.")
    print("No AI.")
    print("No threshold promotion.")
    print("No re-entry simulation.")
    print()

    if not INPUT_FILE.exists():
        print("=" * 100)
        print("ERROR")
        print("=" * 100)
        print()
        print("Experiment #46 output file was not found:")
        print(INPUT_FILE)
        print()
        return None

    df = pd.read_csv(INPUT_FILE)

    print("Input file :", INPUT_FILE)
    print("Rows       :", len(df))
    print("Columns    :", len(df.columns))
    print()

    print("Actual columns:")
    print(list(df.columns))
    print()

    return df


# =============================================================================
# NORMALIZE COLUMN NAMES
# =============================================================================

def normalize(df):

    df = df.copy()

    # P&L at the V
    pnl_col = first_existing(
        df,
        [
            "exit_now_pnl_pct",
            "pnl_at_v_pct",
            "net_pnl_at_v_pct",
        ],
    )

    if pnl_col is None:
        raise ValueError(
            "Could not find the P&L-at-V column. "
            f"Available columns: {list(df.columns)}"
        )

    if pnl_col != "exit_now_pnl_pct":
        df["exit_now_pnl_pct"] = df[pnl_col]

    # STAY / eventual result
    stay_col = first_existing(
        df,
        [
            "eventual_pnl_hindsight_pct",
            "stay_actual_pnl_pct",
            "actual_stay_pnl_pct",
        ],
    )

    if stay_col is None:
        raise ValueError(
            "Could not find the eventual STAY P&L column. "
            f"Available columns: {list(df.columns)}"
        )

    if stay_col != "eventual_pnl_hindsight_pct":
        df["eventual_pnl_hindsight_pct"] = df[stay_col]

    # Numeric columns
    numeric_cols = [
        "exit_now_pnl_pct",
        "eventual_pnl_hindsight_pct",
    ]

    for h in HORIZONS:
        numeric_cols.extend(
            [
                f"change_from_v_after_{h}m_pct",
                f"pnl_after_{h}m_pct",
            ]
        )

    numeric_cols.extend(
        [
            "max_profit_after_v_pct",
            "minimum_pnl_after_v_pct",
        ]
    )

    df = clean_numeric(df, numeric_cols)

    # Event time
    if "event_time_utc" in df.columns:
        df["event_time_utc"] = pd.to_datetime(
            df["event_time_utc"],
            errors="coerce",
            utc=True,
        )

    return df


# =============================================================================
# OBSERVATION OF POST-V BEHAVIOR
# =============================================================================

def classify_event(row):

    """
    Classify ONLY when enough post-V information exists.

    We deliberately avoid a percentage threshold.

    Logic:

    IMMEDIATE_NOISE
        Price moves against the trade immediately,
        but then returns toward/improves from the V.

    NOISE_THEN_RECOVERY
        Initial adverse movement is followed by a meaningful
        recovery toward the trade direction.

    CONTINUING_REVERSAL
        The post-V path continues against the trade across
        available checkpoints.

    MIXED
        Neither behavior dominates.

    INSUFFICIENT
        Not enough post-V observations to make a causal
        trajectory observation.
    """

    changes = []

    for h in HORIZONS:
        col = f"change_from_v_after_{h}m_pct"

        if col in row.index:
            value = row[col]

            if pd.notna(value):
                changes.append((h, float(value)))

    # Need at least two observations to examine movement over time.
    if len(changes) < 2:
        return "INSUFFICIENT"

    values = [v for _, v in changes]

    positive_count = sum(v > 0 for v in values)
    negative_count = sum(v < 0 for v in values)

    # First post-V observation
    first_value = values[0]

    # Last available observation
    last_value = values[-1]

    # -------------------------------------------------------------------------
    # Noise:
    # initial adverse move followed by recovery toward/above V
    # -------------------------------------------------------------------------

    if first_value < 0 and last_value > first_value:
        # If the path actually crosses into positive territory,
        # call it clear recovery.
        if last_value > 0:
            return "NOISE_THEN_RECOVERY"

        # Otherwise, it improved but remained adverse.
        # We do not pretend that this is a full recovery.
        if positive_count > 0:
            return "MIXED"

    # -------------------------------------------------------------------------
    # Continuing reversal:
    # successive observations remain adverse / worsen
    # -------------------------------------------------------------------------

    if all(v <= 0 for v in values):
        # Require at least two negative observations.
        if negative_count >= 2:
            return "CONTINUING_REVERSAL"

    # -------------------------------------------------------------------------
    # Immediate noise:
    # initial adverse move, followed by clear improvement
    # -------------------------------------------------------------------------

    if first_value < 0 and last_value >= 0:
        return "IMMEDIATE_NOISE"

    # -------------------------------------------------------------------------
    # Strong persistent deterioration from V
    # -------------------------------------------------------------------------

    if first_value <= 0 and last_value < first_value:
        return "CONTINUING_REVERSAL"

    # -------------------------------------------------------------------------
    # Strong improvement
    # -------------------------------------------------------------------------

    if first_value >= 0 and last_value > first_value:
        return "IMMEDIATE_NOISE"

    return "MIXED"


# =============================================================================
# DIRECTION TEXT
# =============================================================================

def direction_text(value):
    """
    IMPORTANT:
    This function receives a VALUE, not a dataframe row.

    The previous #47 crashed because direction_text() expected
    row.get(...), while the caller supplied a string.
    """

    direction = str(value).upper().strip()

    if direction == "LONG":
        return "LONG"

    if direction == "SHORT":
        return "SHORT"

    return direction


# =============================================================================
# ADD BEHAVIOR MEASUREMENTS
# =============================================================================

def add_behavior_columns(df):

    df = df.copy()

    df["v_behavior"] = df.apply(classify_event, axis=1)

    # Count available post-V checkpoints.
    available_counts = []

    for _, row in df.iterrows():
        count = 0

        for h in HORIZONS:
            col = f"change_from_v_after_{h}m_pct"

            if col in row.index and pd.notna(row[col]):
                count += 1

        available_counts.append(count)

    df["post_v_observations_available"] = available_counts

    # First available change
    first_changes = []
    last_changes = []

    for _, row in df.iterrows():

        values = []

        for h in HORIZONS:
            col = f"change_from_v_after_{h}m_pct"

            if col in row.index and pd.notna(row[col]):
                values.append(float(row[col]))

        if values:
            first_changes.append(values[0])
            last_changes.append(values[-1])
        else:
            first_changes.append(np.nan)
            last_changes.append(np.nan)

    df["first_post_v_change_pct"] = first_changes
    df["last_post_v_change_pct"] = last_changes

    # STAY vs EXIT
    df["stay_minus_exit_pct"] = (
        df["eventual_pnl_hindsight_pct"]
        - df["exit_now_pnl_pct"]
    )

    df["stay_better"] = (
        df["stay_minus_exit_pct"] > 0
    )

    df["exit_better"] = (
        df["stay_minus_exit_pct"] < 0
    )

    df["same_result"] = (
        df["stay_minus_exit_pct"] == 0
    )

    return df


# =============================================================================
# CORE RESULT
# =============================================================================

def print_core_result(df):

    print("=" * 100)
    print("CORE RESULT")
    print("=" * 100)
    print()

    print("Unprofitable V events :", len(df))
    print("Unique trades         :", df["trade_id"].nunique()
          if "trade_id" in df.columns else "N/A")
    print()

    counts = df["v_behavior"].value_counts()

    categories = [
        "IMMEDIATE_NOISE",
        "NOISE_THEN_RECOVERY",
        "CONTINUING_REVERSAL",
        "MIXED",
        "INSUFFICIENT",
    ]

    for category in categories:
        n = int(counts.get(category, 0))
        pct = (n / len(df) * 100) if len(df) else 0

        print(
            f"{category:<32}"
            f"{n:>5} "
            f"({pct:>6.2f}%)"
        )

    print()

    print(
        "Average EXIT NOW P&L :",
        fmt_pct(df["exit_now_pnl_pct"].mean()),
    )

    print(
        "Average STAY P&L     :",
        fmt_pct(df["eventual_pnl_hindsight_pct"].mean()),
    )

    print(
        "Average STAY - EXIT  :",
        fmt_pct(df["stay_minus_exit_pct"].mean()),
    )

    print(
        "Median STAY - EXIT   :",
        fmt_pct(df["stay_minus_exit_pct"].median()),
    )

    print()

    print(
        "STAY better :",
        int(df["stay_better"].sum()),
    )

    print(
        "EXIT better :",
        int(df["exit_better"].sum()),
    )

    print(
        "Same        :",
        int(df["same_result"].sum()),
    )

    print()


# =============================================================================
# BEHAVIOR × STAY / EXIT
# =============================================================================

def print_behavior_summary(df):

    print("=" * 100)
    print("BEHAVIOR × STAY vs EXIT")
    print("=" * 100)
    print()

    rows = []

    for behavior in [
        "IMMEDIATE_NOISE",
        "NOISE_THEN_RECOVERY",
        "CONTINUING_REVERSAL",
        "MIXED",
        "INSUFFICIENT",
    ]:

        g = df[df["v_behavior"] == behavior]

        if len(g) == 0:
            continue

        stay_better = int(g["stay_better"].sum())
        exit_better = int(g["exit_better"].sum())
        same = int(g["same_result"].sum())

        positive_stay = int(
            (g["eventual_pnl_hindsight_pct"] > 0).sum()
        )

        negative_stay = int(
            (g["eventual_pnl_hindsight_pct"] < 0).sum()
        )

        print(f"[{behavior}]")
        print("Events                 :", len(g))
        print("Unique trades          :", g["trade_id"].nunique()
              if "trade_id" in g.columns else "N/A")
        print("STAY better            :", stay_better)
        print("EXIT better            :", exit_better)
        print("Same                   :", same)

        print(
            "Average V P&L          :",
            fmt_pct(g["exit_now_pnl_pct"].mean()),
        )

        print(
            "Average STAY final     :",
            fmt_pct(g["eventual_pnl_hindsight_pct"].mean()),
        )

        print(
            "Average STAY - EXIT    :",
            fmt_pct(g["stay_minus_exit_pct"].mean()),
        )

        print(
            "Median STAY - EXIT     :",
            fmt_pct(g["stay_minus_exit_pct"].median()),
        )

        print("STAY eventual positive :", positive_stay)
        print("STAY eventual negative :", negative_stay)
        print()

        rows.append(
            {
                "behavior": behavior,
                "events": len(g),
                "unique_trades": (
                    g["trade_id"].nunique()
                    if "trade_id" in g.columns
                    else np.nan
                ),
                "stay_better": stay_better,
                "exit_better": exit_better,
                "same": same,
                "avg_exit_pnl_pct": g["exit_now_pnl_pct"].mean(),
                "median_exit_pnl_pct": g["exit_now_pnl_pct"].median(),
                "avg_stay_pnl_pct": (
                    g["eventual_pnl_hindsight_pct"].mean()
                ),
                "median_stay_pnl_pct": (
                    g["eventual_pnl_hindsight_pct"].median()
                ),
                "avg_stay_minus_exit_pct": (
                    g["stay_minus_exit_pct"].mean()
                ),
                "median_stay_minus_exit_pct": (
                    g["stay_minus_exit_pct"].median()
                ),
                "stay_eventual_positive": positive_stay,
                "stay_eventual_negative": negative_stay,
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# BEHAVIOR × DIRECTION
# =============================================================================

def print_direction_summary(df):

    print("=" * 100)
    print("BEHAVIOR × DIRECTION")
    print("=" * 100)
    print()

    if "direction" not in df.columns:
        print("Direction column not available.")
        print()
        return

    # IMPORTANT:
    # Do NOT call direction_text(row).
    # direction_text expects the actual direction value.
    directions = (
        df["direction"]
        .dropna()
        .astype(str)
        .str.upper()
        .unique()
        .tolist()
    )

    behaviors = [
        "IMMEDIATE_NOISE",
        "NOISE_THEN_RECOVERY",
        "CONTINUING_REVERSAL",
        "MIXED",
        "INSUFFICIENT",
    ]

    for direction in directions:

        direction_df = df[
            df["direction"]
            .astype(str)
            .str.upper()
            == direction
        ]

        print(f"--- {direction_text(direction)} ---")

        for behavior in behaviors:

            g = direction_df[
                direction_df["v_behavior"] == behavior
            ]

            if len(g) == 0:
                continue

            print(
                f"{behavior:<32}"
                f"n={len(g):>3} "
                f"STAY={int(g['stay_better'].sum()):>2} "
                f"EXIT={int(g['exit_better'].sum()):>2} "
                f"AVG Δ={fmt_pct(g['stay_minus_exit_pct'].mean())}"
            )

        print()


# =============================================================================
# FIVE-MINUTE PATH TABLE
# =============================================================================

def print_path_table(df):

    print("=" * 100)
    print("POST-V 5-MINUTE PATH")
    print("=" * 100)
    print()

    display_cols = []

    for col in [
        "case_id",
        "trade_id",
        "direction",
        "event_time_utc",
        "exit_now_pnl_pct",
        "first_post_v_change_pct",
        "last_post_v_change_pct",
        "v_behavior",
        "eventual_pnl_hindsight_pct",
        "stay_minus_exit_pct",
    ]:
        if col in df.columns:
            display_cols.append(col)

    for h in HORIZONS:
        col = f"change_from_v_after_{h}m_pct"

        if col in df.columns:
            display_cols.append(col)

    if not display_cols:
        print("No displayable columns.")
        return

    print(
        df[display_cols]
        .sort_values(
            by=["event_time_utc"]
            if "event_time_utc" in df.columns
            else ["case_id"]
        )
        .to_string(index=False)
    )

    print()


# =============================================================================
# CASE-BY-CASE
# =============================================================================

def print_case_by_case(df):

    print("=" * 100)
    print("CASE-BY-CASE")
    print("=" * 100)
    print()

    for _, row in df.iterrows():

        case_id = row.get("case_id", "")
        trade_id = row.get("trade_id", "")
        direction = row.get("direction", "")

        exit_pnl = row.get("exit_now_pnl_pct", np.nan)
        stay_pnl = row.get("eventual_pnl_hindsight_pct", np.nan)
        delta = row.get("stay_minus_exit_pct", np.nan)

        behavior = row.get("v_behavior", "UNKNOWN")

        if pd.isna(delta):
            decision = "NO STAY RESULT"
        elif delta > 0:
            decision = "STAY BETTER"
        elif delta < 0:
            decision = "EXIT BETTER"
        else:
            decision = "SAME"

        print(
            f"{case_id:<12}"
            f"{trade_id:<12}"
            f"{direction:<6}"
            f" V={fmt_pct(exit_pnl):>10}"
            f" STAY={fmt_pct(stay_pnl):>10}"
            f" Δ={fmt_pct(delta):>10}"
            f" {behavior:<24}"
            f" --> {decision}"
        )

    print()


# =============================================================================
# SUMMARY FILE
# =============================================================================

def build_summary(df, behavior_summary):

    rows = []

    rows.append(
        {
            "section": "TOTAL",
            "behavior": "ALL",
            "events": len(df),
            "unique_trades": (
                df["trade_id"].nunique()
                if "trade_id" in df.columns
                else np.nan
            ),
            "stay_better": int(df["stay_better"].sum()),
            "exit_better": int(df["exit_better"].sum()),
            "same": int(df["same_result"].sum()),
            "avg_exit_pnl_pct": df["exit_now_pnl_pct"].mean(),
            "median_exit_pnl_pct": df["exit_now_pnl_pct"].median(),
            "avg_stay_pnl_pct": (
                df["eventual_pnl_hindsight_pct"].mean()
            ),
            "median_stay_pnl_pct": (
                df["eventual_pnl_hindsight_pct"].median()
            ),
            "avg_stay_minus_exit_pct": (
                df["stay_minus_exit_pct"].mean()
            ),
            "median_stay_minus_exit_pct": (
                df["stay_minus_exit_pct"].median()
            ),
        }
    )

    for _, row in behavior_summary.iterrows():

        rows.append(
            {
                "section": "BEHAVIOR",
                "behavior": row["behavior"],
                "events": row["events"],
                "unique_trades": row["unique_trades"],
                "stay_better": row["stay_better"],
                "exit_better": row["exit_better"],
                "same": row["same"],
                "avg_exit_pnl_pct": row["avg_exit_pnl_pct"],
                "median_exit_pnl_pct": row["median_exit_pnl_pct"],
                "avg_stay_pnl_pct": row["avg_stay_pnl_pct"],
                "median_stay_pnl_pct": row["median_stay_pnl_pct"],
                "avg_stay_minus_exit_pct": row[
                    "avg_stay_minus_exit_pct"
                ],
                "median_stay_minus_exit_pct": row[
                    "median_stay_minus_exit_pct"
                ],
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# METADATA
# =============================================================================

def write_metadata(df):

    with open(OUTPUT_META, "w", encoding="utf-8") as f:

        f.write("AIMn KISS — Experiment #47\n")
        f.write("UNPROFITABLE V: NOISE vs CONTINUING REVERSAL\n")
        f.write("=" * 80 + "\n\n")

        f.write("Research only.\n")
        f.write("No production strategy changes.\n")
        f.write("No orders.\n")
        f.write("No AI training.\n")
        f.write("No threshold promotion.\n")
        f.write("No re-entry simulation.\n\n")

        f.write("QUESTION\n")
        f.write("--------\n")
        f.write(
            "At an unprofitable V, is price merely making noise,\n"
            "or is the reversal continuing against the trade?\n\n"
        )

        f.write("SOURCE\n")
        f.write("------\n")
        f.write(f"{INPUT_FILE}\n\n")

        f.write("EVENTS\n")
        f.write(f"{len(df)}\n\n")

        f.write("UNIQUE TRADES\n")
        f.write(
            f"{df['trade_id'].nunique() if 'trade_id' in df.columns else 'N/A'}\n\n"
        )

        f.write("CLASSIFICATION\n")
        f.write("--------------\n")

        counts = df["v_behavior"].value_counts()

        for category in [
            "IMMEDIATE_NOISE",
            "NOISE_THEN_RECOVERY",
            "CONTINUING_REVERSAL",
            "MIXED",
            "INSUFFICIENT",
        ]:
            f.write(
                f"{category}: "
                f"{int(counts.get(category, 0))}\n"
            )

        f.write("\n")
        f.write("IMPORTANT\n")
        f.write("---------\n")
        f.write(
            "The experiment does not promote any threshold or trading rule.\n"
        )
        f.write(
            "Insufficient events remain insufficient rather than being forced\n"
        )
        f.write(
            "into a noise or continuation category.\n"
        )


# =============================================================================
# MAIN
# =============================================================================

def main():

    df = load_data()

    if df is None:
        return

    try:
        df = normalize(df)
    except Exception as exc:
        print("=" * 100)
        print("ERROR")
        print("=" * 100)
        print(str(exc))
        print()
        return

    try:
        df = add_behavior_columns(df)
    except Exception as exc:
        print("=" * 100)
        print("ERROR WHILE ANALYZING POST-V TRAJECTORY")
        print("=" * 100)
        print(str(exc))
        print()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # PRINT RESULTS
    # -------------------------------------------------------------------------

    print_core_result(df)

    behavior_summary = print_behavior_summary(df)

    print_direction_summary(df)

    print_path_table(df)

    print_case_by_case(df)

    # -------------------------------------------------------------------------
    # SAVE EVENTS
    # -------------------------------------------------------------------------

    df.to_csv(
        OUTPUT_EVENTS,
        index=False,
    )

    # -------------------------------------------------------------------------
    # SAVE SUMMARY
    # -------------------------------------------------------------------------

    summary = build_summary(
        df,
        behavior_summary,
    )

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
    )

    # -------------------------------------------------------------------------
    # SAVE METADATA
    # -------------------------------------------------------------------------

    write_metadata(df)

    # -------------------------------------------------------------------------
    # FINAL
    # -------------------------------------------------------------------------

    print("=" * 100)
    print("OUTPUTS")
    print("=" * 100)
    print()
    print("Events :", OUTPUT_EVENTS)
    print("Summary:", OUTPUT_SUMMARY)
    print("Meta   :", OUTPUT_META)
    print()

    print("=" * 100)
    print("EXPERIMENT #47 COMPLETE")
    print("=" * 100)
    print()

    print(
        "IMPORTANT: This is still a very small sample."
    )
    print(
        "The purpose is to observe the post-V behavior, not to create a rule."
    )
    print()


if __name__ == "__main__":
    main()

