"""
================================================================================
EXPERIMENT #41 — NVDA V SEQUENCE OBSERVATION
================================================================================

QUESTION
--------
Does the SEQUENCE of V events inside one trade reveal whether the original
trade continues or deteriorates?

Experiment #40 showed that one V by itself is often ambiguous.

Experiment #40 also showed that:
    - 30 of 39 trades had multiple V events
    - 9 of 39 trades had only one V event

Therefore Experiment #41 studies the sequence of V events within each trade.

PURE OBSERVATION ONLY.

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
Experiment #40 output:

    kiss/results/exp40_giveback_trajectory/
        nvda_giveback_trajectory_events.csv

IMPORTANT
---------
Events belonging to the same trade are treated as a sequence.

They are NOT treated as independent trades.

The experiment observes how the sequence develops.

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
    "kiss/results/exp40_giveback_trajectory/"
    "nvda_giveback_trajectory_events.csv"
)

OUTPUT_DIR = Path(
    "kiss/results/exp41_v_sequence"
)

EVENT_OUTPUT = OUTPUT_DIR / (
    "nvda_v_sequence_events.csv"
)

TRANSITION_OUTPUT = OUTPUT_DIR / (
    "nvda_v_sequence_transitions.csv"
)

TRADE_OUTPUT = OUTPUT_DIR / (
    "nvda_v_sequence_trade_summary.csv"
)

SUMMARY_OUTPUT = OUTPUT_DIR / (
    "nvda_v_sequence_summary.csv"
)

METADATA_OUTPUT = OUTPUT_DIR / (
    "exp41_metadata.txt"
)


# =============================================================================
# HELPERS
# =============================================================================

def print_header(title: str):

    print("=" * 90)
    print(title)
    print("=" * 90)


def print_line():

    print("-" * 90)


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


# =============================================================================
# LOAD
# =============================================================================

def load_events() -> pd.DataFrame:

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Experiment #40 event file not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    if df.empty:

        raise ValueError(
            "Experiment #40 event file is empty."
        )

    required = [
        "case_id",
        "trade_id",
        "symbol",
        "direction",
        "event_time_utc",
        "entry_time_utc",
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
        "post_v_trajectory",
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
            "Experiment #40 file is missing columns:\n"
            + "\n".join(missing)
        )

    numeric_columns = [
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

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
        errors="coerce",
    )

    df["entry_time_utc"] = pd.to_datetime(
        df["entry_time_utc"],
        utc=True,
        errors="coerce",
    )

    df["recovered_previous_peak_bool"] = (
        df["recovered_previous_peak"]
        .astype(str)
        .str.lower()
        .eq("true")
    )

    return df


# =============================================================================
# BUILD V SEQUENCE
# =============================================================================

def build_sequence(df: pd.DataFrame) -> pd.DataFrame:

    out = (
        df.sort_values(
            [
                "trade_id",
                "event_time_utc",
            ]
        )
        .copy()
    )

    # -------------------------------------------------------------------------
    # Number V events inside each trade.
    # -------------------------------------------------------------------------

    out["v_number"] = (
        out.groupby("trade_id")
        .cumcount()
        + 1
    )

    out["total_v_events_in_trade"] = (
        out.groupby("trade_id")["trade_id"]
        .transform("size")
    )

    # -------------------------------------------------------------------------
    # Previous V information.
    # -------------------------------------------------------------------------

    out["previous_v_time_utc"] = (
        out.groupby("trade_id")["event_time_utc"]
        .shift(1)
    )

    out["previous_v_pnl_pct"] = (
        out.groupby("trade_id")["pnl_at_v_pct"]
        .shift(1)
    )

    out["previous_giveback_pct_of_peak"] = (
        out.groupby("trade_id")[
            "profit_giveback_pct_of_peak"
        ]
        .shift(1)
    )

    out["previous_prior_peak_pct"] = (
        out.groupby("trade_id")[
            "favorable_peak_before_v_pct"
        ]
        .shift(1)
    )

    out["previous_recovered_previous_peak"] = (
        out.groupby("trade_id")[
            "recovered_previous_peak_bool"
        ]
        .shift(1)
    )

    # -------------------------------------------------------------------------
    # Time between V events.
    # -------------------------------------------------------------------------

    out["minutes_since_previous_v"] = (
        (
            out["event_time_utc"]
            - out["previous_v_time_utc"]
        )
        .dt.total_seconds()
        / 60.0
    )

    # -------------------------------------------------------------------------
    # P&L change from previous V.
    #
    # Positive = trade is making progress between V events.
    # Negative = trade is losing progress between V events.
    # -------------------------------------------------------------------------

    out["pnl_change_from_previous_v_pct"] = (
        out["pnl_at_v_pct"]
        - out["previous_v_pnl_pct"]
    )

    # -------------------------------------------------------------------------
    # Change in giveback fraction.
    #
    # Positive = later V surrendered a larger fraction of earned profit.
    # Negative = later V surrendered a smaller fraction.
    # -------------------------------------------------------------------------

    out["giveback_change_from_previous_v_pct_points"] = (
        out["profit_giveback_pct_of_peak"]
        - out["previous_giveback_pct_of_peak"]
    )

    # -------------------------------------------------------------------------
    # Change in prior favorable peak.
    # -------------------------------------------------------------------------

    out["prior_peak_change_from_previous_v_pct"] = (
        out["favorable_peak_before_v_pct"]
        - out["previous_prior_peak_pct"]
    )

    # -------------------------------------------------------------------------
    # Sequence observations.
    # -------------------------------------------------------------------------

    def direction_of_change(value):

        if pd.isna(value):
            return "FIRST_V"

        if value > 0:
            return "INCREASED"

        if value < 0:
            return "DECREASED"

        return "UNCHANGED"

    out["pnl_sequence_direction"] = (
        out["pnl_change_from_previous_v_pct"]
        .apply(direction_of_change)
    )

    out["giveback_sequence_direction"] = (
        out[
            "giveback_change_from_previous_v_pct_points"
        ]
        .apply(direction_of_change)
    )

    out["prior_peak_sequence_direction"] = (
        out[
            "prior_peak_change_from_previous_v_pct"
        ]
        .apply(direction_of_change)
    )

    # -------------------------------------------------------------------------
    # Did this V occur after the previous V recovered its prior peak?
    # -------------------------------------------------------------------------

    out["previous_v_had_recovered"] = (
        out["previous_recovered_previous_peak"]
        .fillna(False)
        .astype(bool)
    )

    # -------------------------------------------------------------------------
    # Sequence position.
    # -------------------------------------------------------------------------

    def position(row):

        if row["v_number"] == 1:
            return "FIRST_V"

        if row["v_number"] == 2:
            return "SECOND_V"

        if row["v_number"] == 3:
            return "THIRD_V"

        return "FOURTH_OR_LATER"

    out["sequence_position"] = out.apply(
        position,
        axis=1,
    )

    return out


# =============================================================================
# TRANSITIONS BETWEEN V EVENTS
# =============================================================================

def build_transitions(
    sequence: pd.DataFrame,
) -> pd.DataFrame:

    transitions = sequence[
        sequence["v_number"] > 1
    ].copy()

    if transitions.empty:

        return pd.DataFrame()

    # -------------------------------------------------------------------------
    # Describe each V-to-V transition.
    # -------------------------------------------------------------------------

    def transition_label(row):

        pnl_change = row[
            "pnl_change_from_previous_v_pct"
        ]

        giveback_change = row[
            "giveback_change_from_previous_v_pct_points"
        ]

        if pd.isna(pnl_change):
            return "UNDEFINED"

        if pnl_change > 0 and giveback_change < 0:
            return "P&L_UP_GIVEBACK_DOWN"

        if pnl_change > 0 and giveback_change > 0:
            return "P&L_UP_GIVEBACK_UP"

        if pnl_change < 0 and giveback_change < 0:
            return "P&L_DOWN_GIVEBACK_DOWN"

        if pnl_change < 0 and giveback_change > 0:
            return "P&L_DOWN_GIVEBACK_UP"

        if pnl_change == 0 and giveback_change == 0:
            return "BOTH_UNCHANGED"

        if pnl_change == 0:
            return "P&L_FLAT"

        if giveback_change == 0:
            return "GIVEBACK_FLAT"

        return "MIXED"

    transitions["v_to_v_transition"] = (
        transitions.apply(
            transition_label,
            axis=1,
        )
    )

    # -------------------------------------------------------------------------
    # Recovery state of the preceding V.
    # -------------------------------------------------------------------------

    transitions["previous_v_recovery_state"] = (
        np.where(
            transitions["previous_v_had_recovered"],
            "RECOVERED",
            "NOT_RECOVERED_OR_UNKNOWN",
        )
    )

    # -------------------------------------------------------------------------
    # Did the next V occur at a higher or lower P&L?
    # -------------------------------------------------------------------------

    transitions["next_v_pnl_higher"] = (
        transitions[
            "pnl_change_from_previous_v_pct"
        ]
        > 0
    )

    transitions["next_v_pnl_lower"] = (
        transitions[
            "pnl_change_from_previous_v_pct"
        ]
        < 0
    )

    return transitions


# =============================================================================
# TRADE SUMMARY
# =============================================================================

def build_trade_summary(
    sequence: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for trade_id, group in sequence.groupby(
        "trade_id",
        sort=False,
    ):

        group = group.sort_values(
            "v_number"
        )

        giveback = group[
            "profit_giveback_pct_of_peak"
        ].dropna()

        pnl_changes = group[
            "pnl_change_from_previous_v_pct"
        ].dropna()

        giveback_changes = group[
            "giveback_change_from_previous_v_pct_points"
        ].dropna()

        peak_changes = group[
            "prior_peak_change_from_previous_v_pct"
        ].dropna()

        # ---------------------------------------------------------------------
        # Sequence direction counts.
        # ---------------------------------------------------------------------

        pnl_up_count = int(
            (
                pnl_changes > 0
            ).sum()
        )

        pnl_down_count = int(
            (
                pnl_changes < 0
            ).sum()
        )

        giveback_up_count = int(
            (
                giveback_changes > 0
            ).sum()
        )

        giveback_down_count = int(
            (
                giveback_changes < 0
            ).sum()
        )

        peak_up_count = int(
            (
                peak_changes > 0
            ).sum()
        )

        peak_down_count = int(
            (
                peak_changes < 0
            ).sum()
        )

        # ---------------------------------------------------------------------
        # Overall sequence descriptions.
        # ---------------------------------------------------------------------

        if pnl_up_count > 0 and pnl_down_count > 0:
            pnl_sequence = "MIXED"
        elif pnl_up_count > 0:
            pnl_sequence = "IMPROVING"
        elif pnl_down_count > 0:
            pnl_sequence = "DETERIORATING"
        else:
            pnl_sequence = "FLAT"

        if (
            giveback_up_count > 0
            and giveback_down_count > 0
        ):
            giveback_sequence = "MIXED"
        elif giveback_up_count > 0:
            giveback_sequence = "INCREASING_GIVEBACK"
        elif giveback_down_count > 0:
            giveback_sequence = "DECREASING_GIVEBACK"
        else:
            giveback_sequence = "FLAT"

        if (
            peak_up_count > 0
            and peak_down_count > 0
        ):
            peak_sequence = "MIXED"
        elif peak_up_count > 0:
            peak_sequence = "RISING_PEAK"
        elif peak_down_count > 0:
            peak_sequence = "FALLING_PEAK"
        else:
            peak_sequence = "FLAT"

        # ---------------------------------------------------------------------
        # First and last V.
        # ---------------------------------------------------------------------

        first = group.iloc[0]
        last = group.iloc[-1]

        rows.append(
            {
                "trade_id": trade_id,
                "symbol": first["symbol"],
                "direction": first["direction"],

                "v_event_count": len(group),

                "first_v_time_utc": (
                    first["event_time_utc"]
                ),

                "last_v_time_utc": (
                    last["event_time_utc"]
                ),

                "first_v_pnl_pct": (
                    first["pnl_at_v_pct"]
                ),

                "last_v_pnl_pct": (
                    last["pnl_at_v_pct"]
                ),

                "first_v_giveback_pct_of_peak": (
                    first[
                        "profit_giveback_pct_of_peak"
                    ]
                ),

                "last_v_giveback_pct_of_peak": (
                    last[
                        "profit_giveback_pct_of_peak"
                    ]
                ),

                "max_v_giveback_pct_of_peak": (
                    giveback.max()
                    if len(giveback)
                    else np.nan
                ),

                "min_v_giveback_pct_of_peak": (
                    giveback.min()
                    if len(giveback)
                    else np.nan
                ),

                "first_v_prior_peak_pct": (
                    first[
                        "favorable_peak_before_v_pct"
                    ]
                ),

                "last_v_prior_peak_pct": (
                    last[
                        "favorable_peak_before_v_pct"
                    ]
                ),

                "pnl_change_first_to_last_v_pct": (
                    last["pnl_at_v_pct"]
                    - first["pnl_at_v_pct"]
                ),

                "giveback_change_first_to_last": (
                    last[
                        "profit_giveback_pct_of_peak"
                    ]
                    - first[
                        "profit_giveback_pct_of_peak"
                    ]
                ),

                "pnl_up_transitions": pnl_up_count,
                "pnl_down_transitions": pnl_down_count,

                "giveback_up_transitions": (
                    giveback_up_count
                ),

                "giveback_down_transitions": (
                    giveback_down_count
                ),

                "peak_up_transitions": peak_up_count,
                "peak_down_transitions": peak_down_count,

                "pnl_sequence": pnl_sequence,
                "giveback_sequence": giveback_sequence,
                "peak_sequence": peak_sequence,

                "eventual_pnl_hindsight_pct": (
                    first[
                        "eventual_pnl_hindsight_pct"
                    ]
                ),

                "post_v_trajectory_sequence": (
                    "|".join(
                        group[
                            "post_v_trajectory"
                        ]
                        .dropna()
                        .astype(str)
                    )
                ),

                "observation_outcome_sequence": (
                    "|".join(
                        group[
                            "observation_outcome"
                        ]
                        .dropna()
                        .astype(str)
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# POSITION SUMMARY
# =============================================================================

def build_position_summary(
    sequence: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for position, group in sequence.groupby(
        "sequence_position",
        sort=False,
    ):

        rows.append(
            {
                "sequence_position": position,
                "event_count": len(group),
                "unique_trades": group["trade_id"].nunique(),

                "avg_pnl_at_v_pct": (
                    group["pnl_at_v_pct"].mean()
                ),

                "median_pnl_at_v_pct": (
                    group["pnl_at_v_pct"].median()
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

                "avg_prior_peak_pct": (
                    group[
                        "favorable_peak_before_v_pct"
                    ].mean()
                ),

                "avg_pnl_change_from_previous_v_pct": (
                    group[
                        "pnl_change_from_previous_v_pct"
                    ].mean()
                ),

                "median_pnl_change_from_previous_v_pct": (
                    group[
                        "pnl_change_from_previous_v_pct"
                    ].median()
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# TRANSITION SUMMARY
# =============================================================================

def build_transition_summary(
    transitions: pd.DataFrame,
) -> pd.DataFrame:

    if transitions.empty:

        return pd.DataFrame()

    rows = []

    for label, group in transitions.groupby(
        "v_to_v_transition",
        sort=False,
    ):

        rows.append(
            {
                "v_to_v_transition": label,
                "transition_count": len(group),
                "unique_trades": group[
                    "trade_id"
                ].nunique(),

                "avg_pnl_change_pct": group[
                    "pnl_change_from_previous_v_pct"
                ].mean(),

                "median_pnl_change_pct": group[
                    "pnl_change_from_previous_v_pct"
                ].median(),

                "avg_giveback_change_points": group[
                    "giveback_change_from_previous_v_pct_points"
                ].mean(),

                "median_giveback_change_points": group[
                    "giveback_change_from_previous_v_pct_points"
                ].median(),

                "avg_minutes_between_v": group[
                    "minutes_since_previous_v"
                ].mean(),

                "median_minutes_between_v": group[
                    "minutes_since_previous_v"
                ].median(),

                "avg_eventual_pnl_pct": group[
                    "eventual_pnl_hindsight_pct"
                ].mean(),

                "median_eventual_pnl_pct": group[
                    "eventual_pnl_hindsight_pct"
                ].median(),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# SUMMARY
# =============================================================================

def build_summary(
    sequence: pd.DataFrame,
    transitions: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    rows.append(
        {
            "metric": "event_count",
            "value": len(sequence),
        }
    )

    rows.append(
        {
            "metric": "unique_trades",
            "value": sequence[
                "trade_id"
            ].nunique(),
        }
    )

    rows.append(
        {
            "metric": "unique_cases",
            "value": sequence[
                "case_id"
            ].nunique(),
        }
    )

    rows.append(
        {
            "metric": "trades_with_multiple_v",
            "value": int(
                (
                    sequence
                    .groupby("trade_id")
                    .size()
                    > 1
                ).sum()
            ),
        }
    )

    rows.append(
        {
            "metric": "trades_with_one_v",
            "value": int(
                (
                    sequence
                    .groupby("trade_id")
                    .size()
                    == 1
                ).sum()
            ),
        }
    )

    if not transitions.empty:

        rows.append(
            {
                "metric": "v_to_v_transition_count",
                "value": len(transitions),
            }
        )

        rows.append(
            {
                "metric": "avg_minutes_between_v",
                "value": transitions[
                    "minutes_since_previous_v"
                ].mean(),
            }
        )

        rows.append(
            {
                "metric": "median_minutes_between_v",
                "value": transitions[
                    "minutes_since_previous_v"
                ].median(),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# METADATA
# =============================================================================

def write_metadata(
    sequence: pd.DataFrame,
    transitions: pd.DataFrame,
):

    lines = [
        "EXPERIMENT #41 — NVDA V SEQUENCE OBSERVATION",
        "",
        "Question:",
        (
            "Does the sequence of V events inside one trade reveal "
            "whether the original trade continues or deteriorates?"
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
        f"V event count: {len(sequence)}",
        f"Unique trades: {sequence['trade_id'].nunique()}",
        f"Unique cases: {sequence['case_id'].nunique()}",
        "",
        (
            "Events are grouped chronologically within each trade "
            "to study V-to-V sequence behavior."
        ),
        "",
        (
            "P&L change from previous V is descriptive."
        ),
        (
            "Giveback change from previous V is descriptive."
        ),
        (
            "Prior peak change from previous V is descriptive."
        ),
        "",
        (
            "No threshold is selected from the observations."
        ),
        "",
        (
            "Experiment #41 does not change AIMn."
        ),
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
        "EXPERIMENT #41 — NVDA V SEQUENCE OBSERVATION"
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
    # LOAD
    # -------------------------------------------------------------------------

    df = load_events()

    print()
    print("DATA")
    print_line()

    print(
        f"Experiment #40 events : {len(df)}"
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
    # SEQUENCE
    # -------------------------------------------------------------------------

    sequence = build_sequence(df)

    transitions = build_transitions(
        sequence
    )

    trade_summary = build_trade_summary(
        sequence
    )

    position_summary = build_position_summary(
        sequence
    )

    transition_summary = build_transition_summary(
        transitions
    )

    summary = build_summary(
        sequence,
        transitions,
    )

    # -------------------------------------------------------------------------
    # OUTPUT
    # -------------------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sequence.to_csv(
        EVENT_OUTPUT,
        index=False,
    )

    transitions.to_csv(
        TRANSITION_OUTPUT,
        index=False,
    )

    trade_summary.to_csv(
        TRADE_OUTPUT,
        index=False,
    )

    # Combine summary sections into one file.
    summary_parts = [
        summary.assign(
            summary_type="overall"
        ),
        position_summary.assign(
            summary_type="sequence_position"
        ),
    ]

    if not transition_summary.empty:

        summary_parts.append(
            transition_summary.assign(
                summary_type="v_to_v_transition"
            )
        )

    final_summary = pd.concat(
        summary_parts,
        ignore_index=True,
        sort=False,
    )

    final_summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    write_metadata(
        sequence,
        transitions,
    )

    # -------------------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------------------

    print()
    print("V EVENTS PER TRADE")
    print_line()

    counts = (
        sequence
        .groupby("trade_id")
        .size()
        .value_counts()
        .sort_index()
    )

    for event_count, trade_count in counts.items():

        print(
            f"{int(event_count)} V event(s) : "
            f"{int(trade_count)} trade(s)"
        )

    print()
    print("V SEQUENCE POSITIONS")
    print_line()

    for _, row in position_summary.iterrows():

        print(
            f"{row['sequence_position']:<18} "
            f"events={int(row['event_count']):>3} "
            f"trades={int(row['unique_trades']):>3} "
            f"avg_pnl="
            f"{row['avg_pnl_at_v_pct']:>8.4f}% "
            f"avg_giveback="
            f"{row['avg_giveback_pct_of_peak']:>7.2f}%"
        )

    print()
    print("V-TO-V TRANSITIONS")
    print_line()

    if transition_summary.empty:

        print("No V-to-V transitions available.")

    else:

        for _, row in transition_summary.iterrows():

            print(
                f"{str(row['v_to_v_transition']):<30} "
                f"n={int(row['transition_count']):>3} "
                f"trades={int(row['unique_trades']):>3} "
                f"avg_dP&L="
                f"{row['avg_pnl_change_pct']:>8.4f}% "
                f"avg_dGiveback="
                f"{row['avg_giveback_change_points']:>8.2f}"
            )

    print()
    print("TRADE-LEVEL SEQUENCE")
    print_line()

    for _, row in trade_summary.iterrows():

        print(
            f"{row['trade_id']:<12} "
            f"V={int(row['v_event_count']):>2} "
            f"P&L_seq={row['pnl_sequence']:<12} "
            f"Giveback_seq={row['giveback_sequence']:<20} "
            f"Peak_seq={row['peak_sequence']:<12} "
            f"eventual="
            f"{row['eventual_pnl_hindsight_pct']:>8.4f}%"
        )

    print()
    print("IMPORTANT")
    print_line()

    print(
        "This experiment describes V sequences inside trades."
    )

    print(
        "It does not tell AIMn to exit."
    )

    print(
        "It does not establish a V threshold."
    )

    print(
        "It does not define minor, medium, or major V events."
    )

    print(
        "It does not change the trading system."
    )

    print()
    print("OUTPUT")
    print_line()

    print(EVENT_OUTPUT)
    print(TRANSITION_OUTPUT)
    print(TRADE_OUTPUT)
    print(SUMMARY_OUTPUT)
    print(METADATA_OUTPUT)

    print()
    print("=" * 90)
    print("EXPERIMENT #41 COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
