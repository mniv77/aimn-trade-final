"""
================================================================================
EXPERIMENT #42 — NVDA V SEQUENCE + PEAK PROGRESSION
================================================================================

QUESTION
--------
When P&L and favorable peak disagree between successive V events, what happens
afterward?

We study four descriptive combinations:

    A: P&L UP   + Peak UP
    B: P&L DOWN + Peak UP
    C: P&L UP   + Peak DOWN
    D: P&L DOWN + Peak DOWN

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
Experiment #41:

    kiss/results/exp41_v_sequence/
        nvda_v_sequence_events.csv
        nvda_v_sequence_transitions.csv

IMPORTANT
---------
Transitions are observations between V events.

They are NOT independent trades.

Multiple transitions can belong to the same trade.

================================================================================
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

INPUT_EVENTS = Path(
    "kiss/results/exp41_v_sequence/"
    "nvda_v_sequence_events.csv"
)

INPUT_TRANSITIONS = Path(
    "kiss/results/exp41_v_sequence/"
    "nvda_v_sequence_transitions.csv"
)

OUTPUT_DIR = Path(
    "kiss/results/exp42_v_peak_divergence"
)

TRANSITION_OUTPUT = OUTPUT_DIR / (
    "nvda_v_peak_divergence_transitions.csv"
)

SUMMARY_OUTPUT = OUTPUT_DIR / (
    "nvda_v_peak_divergence_summary.csv"
)

TRADE_OUTPUT = OUTPUT_DIR / (
    "nvda_v_peak_divergence_trade_summary.csv"
)

METADATA_OUTPUT = OUTPUT_DIR / (
    "exp42_metadata.txt"
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

def load_transitions() -> pd.DataFrame:

    if not INPUT_TRANSITIONS.exists():

        raise FileNotFoundError(
            "Experiment #41 transition file not found:\n"
            f"{INPUT_TRANSITIONS}"
        )

    df = pd.read_csv(
        INPUT_TRANSITIONS
    )

    if df.empty:

        raise ValueError(
            "Experiment #41 transition file is empty."
        )

    required = [
        "trade_id",
        "symbol",
        "direction",
        "v_number",
        "previous_v_time_utc",
        "event_time_utc",
        "previous_v_pnl_pct",
        "pnl_at_v_pct",
        "previous_prior_peak_pct",
        "favorable_peak_before_v_pct",
        "pnl_change_from_previous_v_pct",
        "prior_peak_change_from_previous_v_pct",
        "giveback_change_from_previous_v_pct_points",
        "minutes_since_previous_v",
        "previous_v_had_recovered",
        "eventual_pnl_hindsight_pct",
        "v_to_v_transition",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Experiment #41 transition file is missing columns:\n"
            + "\n".join(missing)
        )

    numeric_columns = [
        "v_number",
        "previous_v_pnl_pct",
        "pnl_at_v_pct",
        "previous_prior_peak_pct",
        "favorable_peak_before_v_pct",
        "pnl_change_from_previous_v_pct",
        "prior_peak_change_from_previous_v_pct",
        "giveback_change_from_previous_v_pct_points",
        "minutes_since_previous_v",
        "eventual_pnl_hindsight_pct",
    ]

    df = safe_numeric(
        df,
        numeric_columns,
    )

    df["previous_v_time_utc"] = pd.to_datetime(
        df["previous_v_time_utc"],
        utc=True,
        errors="coerce",
    )

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
        errors="coerce",
    )

    return df


# =============================================================================
# CLASSIFY P&L / PEAK RELATIONSHIP
# =============================================================================

def classify_relationship(
    df: pd.DataFrame,
) -> pd.DataFrame:

    out = df.copy()

    pnl_change = out[
        "pnl_change_from_previous_v_pct"
    ]

    peak_change = out[
        "prior_peak_change_from_previous_v_pct"
    ]

    def classify(row):

        pnl = row[
            "pnl_change_from_previous_v_pct"
        ]

        peak = row[
            "prior_peak_change_from_previous_v_pct"
        ]

        if pd.isna(pnl) or pd.isna(peak):
            return "UNDEFINED"

        if pnl > 0 and peak > 0:
            return "A_PNL_UP_PEAK_UP"

        if pnl < 0 and peak > 0:
            return "B_PNL_DOWN_PEAK_UP"

        if pnl > 0 and peak < 0:
            return "C_PNL_UP_PEAK_DOWN"

        if pnl < 0 and peak < 0:
            return "D_PNL_DOWN_PEAK_DOWN"

        if pnl == 0 and peak == 0:
            return "FLAT_FLAT"

        if pnl == 0:
            return "PNL_FLAT"

        if peak == 0:
            return "PEAK_FLAT"

        return "OTHER"

    out["pnl_peak_relationship"] = out.apply(
        classify,
        axis=1,
    )

    # -------------------------------------------------------------------------
    # Agreement / divergence description.
    # -------------------------------------------------------------------------

    def agreement(row):

        pnl = row[
            "pnl_change_from_previous_v_pct"
        ]

        peak = row[
            "prior_peak_change_from_previous_v_pct"
        ]

        if pd.isna(pnl) or pd.isna(peak):
            return "UNDEFINED"

        if pnl > 0 and peak > 0:
            return "AGREE_IMPROVING"

        if pnl < 0 and peak < 0:
            return "AGREE_DETERIORATING"

        if pnl < 0 and peak > 0:
            return "DIVERGENCE_PNL_DOWN_PEAK_UP"

        if pnl > 0 and peak < 0:
            return "DIVERGENCE_PNL_UP_PEAK_DOWN"

        return "FLAT_OR_MIXED"

    out["relationship_type"] = out.apply(
        agreement,
        axis=1,
    )

    return out


# =============================================================================
# SUMMARY BY RELATIONSHIP
# =============================================================================

def build_relationship_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for relationship, group in df.groupby(
        "pnl_peak_relationship",
        sort=False,
    ):

        eventual = group[
            "eventual_pnl_hindsight_pct"
        ].dropna()

        pnl_change = group[
            "pnl_change_from_previous_v_pct"
        ].dropna()

        peak_change = group[
            "prior_peak_change_from_previous_v_pct"
        ].dropna()

        giveback_change = group[
            "giveback_change_from_previous_v_pct_points"
        ].dropna()

        previous_recovered = (
            group[
                "previous_v_had_recovered"
            ]
            .astype(bool)
        )

        rows.append(
            {
                "pnl_peak_relationship": relationship,

                "transition_count": len(group),

                "unique_trades": (
                    group["trade_id"]
                    .nunique()
                ),

                "avg_pnl_change_pct": (
                    pnl_change.mean()
                ),

                "median_pnl_change_pct": (
                    pnl_change.median()
                ),

                "avg_peak_change_pct": (
                    peak_change.mean()
                ),

                "median_peak_change_pct": (
                    peak_change.median()
                ),

                "avg_giveback_change_points": (
                    giveback_change.mean()
                ),

                "median_giveback_change_points": (
                    giveback_change.median()
                ),

                "avg_minutes_between_v": (
                    group[
                        "minutes_since_previous_v"
                    ].mean()
                ),

                "median_minutes_between_v": (
                    group[
                        "minutes_since_previous_v"
                    ].median()
                ),

                "previous_v_recovered_count": (
                    int(
                        previous_recovered.sum()
                    )
                ),

                "previous_v_recovered_pct": (
                    previous_recovered.mean()
                    * 100.0
                ),

                "avg_eventual_pnl_pct": (
                    eventual.mean()
                ),

                "median_eventual_pnl_pct": (
                    eventual.median()
                ),

                "eventual_positive_count": (
                    int(
                        (eventual > 0).sum()
                    )
                ),

                "eventual_positive_pct": (
                    (
                        eventual > 0
                    ).mean()
                    * 100.0
                    if len(eventual)
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# TRADE-LEVEL SUMMARY
# =============================================================================

def build_trade_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for trade_id, group in df.groupby(
        "trade_id",
        sort=False,
    ):

        group = group.sort_values(
            "event_time_utc"
        )

        relationships = (
            group[
                "pnl_peak_relationship"
            ]
            .dropna()
            .astype(str)
            .tolist()
        )

        unique_relationships = list(
            dict.fromkeys(
                relationships
            )
        )

        rows.append(
            {
                "trade_id": trade_id,

                "symbol": group[
                    "symbol"
                ].iloc[0],

                "direction": group[
                    "direction"
                ].iloc[0],

                "transition_count": len(group),

                "relationship_sequence": (
                    "|".join(
                        unique_relationships
                    )
                ),

                "relationship_path": (
                    " -> ".join(
                        relationships
                    )
                ),

                "a_count": int(
                    (
                        group[
                            "pnl_peak_relationship"
                        ]
                        == "A_PNL_UP_PEAK_UP"
                    ).sum()
                ),

                "b_count": int(
                    (
                        group[
                            "pnl_peak_relationship"
                        ]
                        == "B_PNL_DOWN_PEAK_UP"
                    ).sum()
                ),

                "c_count": int(
                    (
                        group[
                            "pnl_peak_relationship"
                        ]
                        == "C_PNL_UP_PEAK_DOWN"
                    ).sum()
                ),

                "d_count": int(
                    (
                        group[
                            "pnl_peak_relationship"
                        ]
                        == "D_PNL_DOWN_PEAK_DOWN"
                    ).sum()
                ),

                "eventual_pnl_hindsight_pct": (
                    group[
                        "eventual_pnl_hindsight_pct"
                    ].iloc[0]
                ),

                "positive_eventual_pnl": (
                    group[
                        "eventual_pnl_hindsight_pct"
                    ].iloc[0] > 0
                ),

                "avg_pnl_change_pct": (
                    group[
                        "pnl_change_from_previous_v_pct"
                    ].mean()
                ),

                "avg_peak_change_pct": (
                    group[
                        "prior_peak_change_from_previous_v_pct"
                    ].mean()
                ),

                "avg_giveback_change_points": (
                    group[
                        "giveback_change_from_previous_v_pct_points"
                    ].mean()
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# SPECIFIC DIVERGENCE SUMMARY
# =============================================================================

def build_divergence_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:

    divergence = df[
        df["relationship_type"].isin(
            [
                "DIVERGENCE_PNL_DOWN_PEAK_UP",
                "DIVERGENCE_PNL_UP_PEAK_DOWN",
            ]
        )
    ].copy()

    if divergence.empty:

        return pd.DataFrame()

    rows = []

    for relationship, group in divergence.groupby(
        "relationship_type",
        sort=False,
    ):

        eventual = group[
            "eventual_pnl_hindsight_pct"
        ].dropna()

        rows.append(
            {
                "relationship_type": relationship,

                "transition_count": len(group),

                "unique_trades": (
                    group["trade_id"]
                    .nunique()
                ),

                "avg_pnl_change_pct": (
                    group[
                        "pnl_change_from_previous_v_pct"
                    ].mean()
                ),

                "avg_peak_change_pct": (
                    group[
                        "prior_peak_change_from_previous_v_pct"
                    ].mean()
                ),

                "avg_giveback_change_points": (
                    group[
                        "giveback_change_from_previous_v_pct_points"
                    ].mean()
                ),

                "avg_minutes_between_v": (
                    group[
                        "minutes_since_previous_v"
                    ].mean()
                ),

                "avg_eventual_pnl_pct": (
                    eventual.mean()
                ),

                "median_eventual_pnl_pct": (
                    eventual.median()
                ),

                "eventual_positive_pct": (
                    (
                        eventual > 0
                    ).mean()
                    * 100.0
                    if len(eventual)
                    else np.nan
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
        "EXPERIMENT #42 — NVDA V SEQUENCE + PEAK PROGRESSION",
        "",
        "Question:",
        (
            "When P&L and favorable peak disagree between successive V events, "
            "what happens afterward?"
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
        str(INPUT_TRANSITIONS),
        "",
        f"V-to-V transitions: {len(df)}",
        f"Unique trades: {df['trade_id'].nunique()}",
        "",
        "Relationship groups:",
        "A = P&L UP + Peak UP",
        "B = P&L DOWN + Peak UP",
        "C = P&L UP + Peak DOWN",
        "D = P&L DOWN + Peak DOWN",
        "",
        "These groups are descriptive only.",
        "No threshold is selected.",
        "No trading rule is derived.",
        "",
        "Eventual P&L is hindsight/reference information.",
        "",
        "Experiment #42 does not change AIMn.",
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
        "EXPERIMENT #42 — NVDA V SEQUENCE + PEAK PROGRESSION"
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

    df = load_transitions()

    print()
    print("DATA")
    print_line()

    print(
        f"Experiment #41 transitions: {len(df)}"
    )

    print(
        f"Unique NVDA trades       : "
        f"{df['trade_id'].nunique()}"
    )

    # -------------------------------------------------------------------------
    # CLASSIFY
    # -------------------------------------------------------------------------

    df = classify_relationship(df)

    relationship_summary = (
        build_relationship_summary(df)
    )

    divergence_summary = (
        build_divergence_summary(df)
    )

    trade_summary = (
        build_trade_summary(df)
    )

    # -------------------------------------------------------------------------
    # OUTPUT
    # -------------------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        TRANSITION_OUTPUT,
        index=False,
    )

    trade_summary.to_csv(
        TRADE_OUTPUT,
        index=False,
    )

    summary_parts = [
        relationship_summary.assign(
            summary_type="relationship"
        )
    ]

    if not divergence_summary.empty:

        summary_parts.append(
            divergence_summary.assign(
                summary_type="divergence"
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

    write_metadata(df)

    # -------------------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------------------

    print()
    print("P&L / PEAK RELATIONSHIP")
    print_line()

    for _, row in relationship_summary.iterrows():

        print(
            f"{row['pnl_peak_relationship']:<25} "
            f"n={int(row['transition_count']):>3} "
            f"trades={int(row['unique_trades']):>3} "
            f"avg_dP&L="
            f"{row['avg_pnl_change_pct']:>8.4f}% "
            f"avg_dPeak="
            f"{row['avg_peak_change_pct']:>8.4f}% "
            f"eventual="
            f"{row['avg_eventual_pnl_pct']:>8.4f}%"
        )

    print()
    print("PREVIOUS V RECOVERY")
    print_line()

    for _, row in relationship_summary.iterrows():

        print(
            f"{row['pnl_peak_relationship']:<25} "
            f"recovered="
            f"{row['previous_v_recovered_pct']:>6.2f}% "
            f"avg_dGiveback="
            f"{row['avg_giveback_change_points']:>8.2f}"
        )

    print()
    print("DIVERGENCE CASES")
    print_line()

    if divergence_summary.empty:

        print("No divergence cases found.")

    else:

        for _, row in divergence_summary.iterrows():

            print(
                f"{row['relationship_type']:<35} "
                f"n={int(row['transition_count']):>3} "
                f"trades={int(row['unique_trades']):>3} "
                f"avg_dP&L="
                f"{row['avg_pnl_change_pct']:>8.4f}% "
                f"avg_dPeak="
                f"{row['avg_peak_change_pct']:>8.4f}% "
                f"eventual="
                f"{row['avg_eventual_pnl_pct']:>8.4f}%"
            )

    print()
    print("TRADE-LEVEL RELATIONSHIP PATHS")
    print_line()

    for _, row in trade_summary.iterrows():

        print(
            f"{row['trade_id']:<12} "
            f"transitions={int(row['transition_count']):>2} "
            f"path={row['relationship_path']:<90} "
            f"eventual="
            f"{row['eventual_pnl_hindsight_pct']:>8.4f}%"
        )

    print()
    print("IMPORTANT")
    print_line()

    print(
        "This experiment describes P&L and favorable-peak relationships."
    )

    print(
        "It does not tell AIMn to exit."
    )

    print(
        "It does not establish a threshold."
    )

    print(
        "It does not establish minor, medium, or major V events."
    )

    print(
        "It does not change the trading system."
    )

    print()
    print("OUTPUT")
    print_line()

    print(TRANSITION_OUTPUT)
    print(SUMMARY_OUTPUT)
    print(TRADE_OUTPUT)
    print(METADATA_OUTPUT)

    print()
    print("=" * 90)
    print("EXPERIMENT #42 COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
