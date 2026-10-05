"""
Experiment #44 — Peak Resumption After Flat

Purpose
-------
Experiment #43 studied the persistence/resolution of PEAK_FLAT.

Experiment #44 studies the opposite side:

    When favorable peak stops advancing,
    then starts advancing again,
    what happened to P&L during the flat period
    and what happens after the peak resumes?

This experiment is PURE OBSERVATION.

No trading rule.
No threshold.
No optimization.
No hindsight-based decision logic.

IMPORTANT
---------
This script is built directly from the ACTUAL Experiment #42 CSV columns.

Source:
    kiss/results/exp42_v_peak_divergence/
        nvda_v_peak_divergence_transitions.csv

Core actual #42 columns used:
    trade_id
    symbol
    direction
    event_time_utc
    entry_time_utc
    pnl_at_v_pct
    profit_giveback_pct_of_peak
    eventual_pnl_hindsight_pct
    v_number
    total_v_events_in_trade
    previous_v_time_utc
    previous_v_pnl_pct
    previous_prior_peak_pct
    minutes_since_previous_v
    pnl_change_from_previous_v_pct
    giveback_change_from_previous_v_pct_points
    prior_peak_change_from_previous_v_pct
    sequence_position
    v_to_v_transition
    pnl_peak_relationship
    relationship_type

Definition of PEAK_FLAT
-----------------------
The actual #42 relationship_type is:

    PEAK_FLAT

Definition of PEAK RESUMPTION
-----------------------------
A PEAK_FLAT observation is followed by a V where:

    prior_peak_change_from_previous_v_pct > 0

This means the favorable peak has started advancing again.

We do NOT invent a percentage threshold.

The actual measured change from #42 is used.

Flat episode
------------
A flat episode consists of one or more consecutive PEAK_FLAT
observations within the same trade.

Example:

    A_PNL_UP_PEAK_UP
    PEAK_FLAT
    PEAK_FLAT
    PEAK_FLAT
    A_PNL_UP_PEAK_UP

This becomes:

    PEAK_FLAT RUN
        start = first flat V
        end   = last flat V
        next  = first V after flat run
        result = RESUMED

If there is no following V:

    result = NO_RESUMPTION

If the next V exists but its favorable peak did not increase:

    result = NO_RESUMPTION

Outputs
-------
1. nvda_peak_resumption_after_flat_episodes.csv
2. nvda_peak_resumption_after_flat_summary.csv
3. nvda_peak_resumption_after_flat_resolution_summary.csv
4. nvda_peak_resumption_after_flat_trade_summary.csv
5. exp44_metadata.txt

Research only.
"""

from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# PATHS
# ============================================================

ROOT = Path.home() / "aimn-trade-final"

INPUT_FILE = (
    ROOT
    / "kiss"
    / "results"
    / "exp42_v_peak_divergence"
    / "nvda_v_peak_divergence_transitions.csv"
)

OUTPUT_DIR = (
    ROOT
    / "kiss"
    / "results"
    / "exp44_peak_resumption_after_flat"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# REQUIRED ACTUAL #42 COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "case_id",
    "trade_id",
    "symbol",
    "direction",
    "event_time_utc",
    "entry_time_utc",
    "pnl_at_v_pct",
    "profit_giveback_pct_of_peak",
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
    "sequence_position",
    "v_to_v_transition",
    "pnl_peak_relationship",
    "relationship_type",
]


# ============================================================
# HELPERS
# ============================================================

def safe_mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()) if len(s) else np.nan


def safe_median(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.median()) if len(s) else np.nan


def safe_sum(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.sum()) if len(s) else np.nan


def positive_pct(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float((s > 0).mean() * 100.0) if len(s) else np.nan


def bool_count(series):
    return int(series.fillna(False).astype(bool).sum())


def fmt(value, digits=4):
    if pd.isna(value):
        return "NaN"
    return f"{value:.{digits}f}"


# ============================================================
# LOAD ACTUAL #42 FILE
# ============================================================

print("=" * 110)
print("EXPERIMENT #44 — PEAK RESUMPTION AFTER FLAT")
print("=" * 110)

print(f"\nINPUT:")
print(INPUT_FILE)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Experiment #42 source file not found:\n{INPUT_FILE}"
    )

df = pd.read_csv(INPUT_FILE)

print(f"\nSOURCE ROWS: {len(df)}")
print(f"SOURCE COLUMNS: {len(df.columns)}")


# ============================================================
# VERIFY ACTUAL #42 COLUMNS
# ============================================================

missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]

if missing:
    print("\nERROR — REQUIRED ACTUAL #42 COLUMNS ARE MISSING:")
    for c in missing:
        print(f"  {c}")
    raise ValueError(
        "The #42 CSV structure does not match the expected actual file."
    )

print("\nACTUAL #42 COLUMN CHECK: PASSED")


# ============================================================
# PARSE TYPES
# ============================================================

for col in [
    "event_time_utc",
    "entry_time_utc",
    "previous_v_time_utc",
]:
    df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

numeric_columns = [
    "pnl_at_v_pct",
    "profit_giveback_pct_of_peak",
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

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# ============================================================
# SORT INTO ACTUAL V SEQUENCE
# ============================================================

df = df.sort_values(
    ["trade_id", "event_time_utc", "v_number"]
).reset_index(drop=True)


# ============================================================
# BASIC SOURCE DESCRIPTION
# ============================================================

print("\nSOURCE DESCRIPTION")
print("-" * 110)

print(
    "Unique trades:",
    df["trade_id"].nunique()
)

print(
    "PEAK_FLAT rows:",
    int((df["relationship_type"] == "PEAK_FLAT").sum())
)

print(
    "PEAK_FLAT trades:",
    df.loc[
        df["relationship_type"] == "PEAK_FLAT",
        "trade_id"
    ].nunique()
)


# ============================================================
# BUILD FLAT EPISODES
# ============================================================

episodes = []

for trade_id, trade in df.groupby("trade_id", sort=False):

    trade = (
        trade
        .sort_values(["event_time_utc", "v_number"])
        .reset_index(drop=True)
    )

    i = 0

    while i < len(trade):

        row = trade.iloc[i]

        # ----------------------------------------------------
        # We only begin an episode at PEAK_FLAT.
        # ----------------------------------------------------

        if row["relationship_type"] != "PEAK_FLAT":
            i += 1
            continue

        start_idx = i
        end_idx = i

        # ----------------------------------------------------
        # Consume consecutive PEAK_FLAT observations.
        # ----------------------------------------------------

        while (
            end_idx + 1 < len(trade)
            and trade.iloc[end_idx + 1]["relationship_type"]
            == "PEAK_FLAT"
        ):
            end_idx += 1

        start = trade.iloc[start_idx]
        end = trade.iloc[end_idx]

        # ----------------------------------------------------
        # Look at the FIRST V after the flat run.
        # ----------------------------------------------------

        next_idx = end_idx + 1

        if next_idx < len(trade):
            next_row = trade.iloc[next_idx]
            has_next = True
        else:
            next_row = None
            has_next = False

        # ----------------------------------------------------
        # Peak resumption definition:
        #
        # The next V must have a positive
        # prior_peak_change_from_previous_v_pct.
        #
        # This is an ACTUAL #42 field.
        # No invented threshold.
        # ----------------------------------------------------

        if has_next:
            next_peak_change = next_row[
                "prior_peak_change_from_previous_v_pct"
            ]

            if (
                pd.notna(next_peak_change)
                and next_peak_change > 0
            ):
                resolution = "RESUMED"
            else:
                resolution = "NO_RESUMPTION"
        else:
            resolution = "NO_RESUMPTION"

        # ----------------------------------------------------
        # Flat-period measurements
        # ----------------------------------------------------

        flat_observations = end_idx - start_idx + 1

        start_time = start["event_time_utc"]
        end_time = end["event_time_utc"]

        if pd.notna(start_time) and pd.notna(end_time):
            flat_duration_minutes = (
                end_time - start_time
            ).total_seconds() / 60.0
        else:
            flat_duration_minutes = np.nan

        pnl_start = start["pnl_at_v_pct"]
        pnl_end = end["pnl_at_v_pct"]

        if pd.notna(pnl_start) and pd.notna(pnl_end):
            pnl_change_during_flat = pnl_end - pnl_start
        else:
            pnl_change_during_flat = np.nan

        giveback_start = start["profit_giveback_pct_of_peak"]
        giveback_end = end["profit_giveback_pct_of_peak"]

        if (
            pd.notna(giveback_start)
            and pd.notna(giveback_end)
        ):
            giveback_change_during_flat = (
                giveback_end - giveback_start
            )
        else:
            giveback_change_during_flat = np.nan

        peak_start = start["previous_prior_peak_pct"]
        peak_end = end["previous_prior_peak_pct"]

        if pd.notna(peak_start) and pd.notna(peak_end):
            peak_change_during_flat = peak_end - peak_start
        else:
            peak_change_during_flat = np.nan

        # ----------------------------------------------------
        # Information about resumed V
        # ----------------------------------------------------

        if has_next:

            resumed_peak_change = next_row[
                "prior_peak_change_from_previous_v_pct"
            ]

            resumed_pnl_change = next_row[
                "pnl_change_from_previous_v_pct"
            ]

            resumed_pnl = next_row[
                "pnl_at_v_pct"
            ]

            resumed_giveback = next_row[
                "profit_giveback_pct_of_peak"
            ]

            resumed_relationship = next_row[
                "relationship_type"
            ]

            resumed_event_time = next_row[
                "event_time_utc"
            ]

            if (
                pd.notna(resumed_event_time)
                and pd.notna(end_time)
            ):
                minutes_flat_to_resume = (
                    resumed_event_time - end_time
                ).total_seconds() / 60.0
            else:
                minutes_flat_to_resume = np.nan

            resumed_case_id = next_row["case_id"]
            resumed_v_number = next_row["v_number"]

            # ------------------------------------------------
            # How much P&L changed from the LAST FLAT V
            # to the resumed V.
            # ------------------------------------------------

            if (
                pd.notna(resumed_pnl)
                and pd.notna(pnl_end)
            ):
                pnl_change_flat_to_resume = (
                    resumed_pnl - pnl_end
                )
            else:
                pnl_change_flat_to_resume = np.nan

            if (
                pd.notna(resumed_giveback)
                and pd.notna(giveback_end)
            ):
                giveback_change_flat_to_resume = (
                    resumed_giveback - giveback_end
                )
            else:
                giveback_change_flat_to_resume = np.nan

        else:

            resumed_peak_change = np.nan
            resumed_pnl_change = np.nan
            resumed_pnl = np.nan
            resumed_giveback = np.nan
            resumed_relationship = ""
            resumed_event_time = pd.NaT
            minutes_flat_to_resume = np.nan
            resumed_case_id = ""
            resumed_v_number = np.nan
            pnl_change_flat_to_resume = np.nan
            giveback_change_flat_to_resume = np.nan

        # ----------------------------------------------------
        # Eventual trade result is already present in #42.
        # We use the value carried by the trade's V row.
        # ----------------------------------------------------

        eventual_pnl = end[
            "eventual_pnl_hindsight_pct"
        ]

        # ----------------------------------------------------
        # Append episode.
        # ----------------------------------------------------

        episodes.append({
            "trade_id": trade_id,
            "symbol": start["symbol"],
            "direction": start["direction"],

            "flat_start_case_id": start["case_id"],
            "flat_end_case_id": end["case_id"],
            "resume_case_id": resumed_case_id,

            "flat_start_time_utc": start["event_time_utc"],
            "flat_end_time_utc": end["event_time_utc"],
            "resume_time_utc": resumed_event_time,

            "flat_start_v_number": start["v_number"],
            "flat_end_v_number": end["v_number"],
            "resume_v_number": resumed_v_number,

            "flat_observations": flat_observations,
            "flat_duration_minutes": flat_duration_minutes,
            "minutes_flat_to_resume": minutes_flat_to_resume,

            "pnl_at_flat_start_pct": pnl_start,
            "pnl_at_flat_end_pct": pnl_end,
            "pnl_change_during_flat_pct": pnl_change_during_flat,

            "giveback_at_flat_start_pct_of_peak": giveback_start,
            "giveback_at_flat_end_pct_of_peak": giveback_end,
            "giveback_change_during_flat_points":
                giveback_change_during_flat,

            "peak_at_flat_start_pct": peak_start,
            "peak_at_flat_end_pct": peak_end,
            "peak_change_during_flat_pct":
                peak_change_during_flat,

            "resolution": resolution,

            "resumed_peak_change_pct":
                resumed_peak_change,

            "pnl_at_resumed_v_pct":
                resumed_pnl,

            "pnl_change_from_previous_v_at_resume_pct":
                resumed_pnl_change,

            "pnl_change_flat_to_resume_pct":
                pnl_change_flat_to_resume,

            "giveback_at_resumed_v_pct_of_peak":
                resumed_giveback,

            "giveback_change_flat_to_resume_points":
                giveback_change_flat_to_resume,

            "resume_relationship_type":
                resumed_relationship,

            "eventual_pnl_hindsight_pct":
                eventual_pnl,
        })

        # Move beyond the current flat run.
        i = end_idx + 1


episodes_df = pd.DataFrame(episodes)


# ============================================================
# SAVE RAW EPISODES
# ============================================================

episodes_file = (
    OUTPUT_DIR
    / "nvda_peak_resumption_after_flat_episodes.csv"
)

episodes_df.to_csv(
    episodes_file,
    index=False
)


# ============================================================
# SUMMARY 1 — OVERALL
# ============================================================

summary_rows = []

for resolution, group in episodes_df.groupby(
    "resolution",
    dropna=False
):

    summary_rows.append({
        "resolution": resolution,
        "episodes": len(group),
        "unique_trades":
            group["trade_id"].nunique(),

        "avg_flat_observations":
            safe_mean(group["flat_observations"]),

        "median_flat_observations":
            safe_median(group["flat_observations"]),

        "avg_flat_duration_minutes":
            safe_mean(group["flat_duration_minutes"]),

        "median_flat_duration_minutes":
            safe_median(group["flat_duration_minutes"]),

        "avg_pnl_change_during_flat_pct":
            safe_mean(
                group["pnl_change_during_flat_pct"]
            ),

        "median_pnl_change_during_flat_pct":
            safe_median(
                group["pnl_change_during_flat_pct"]
            ),

        "avg_giveback_change_during_flat_points":
            safe_mean(
                group[
                    "giveback_change_during_flat_points"
                ]
            ),

        "median_giveback_change_during_flat_points":
            safe_median(
                group[
                    "giveback_change_during_flat_points"
                ]
            ),

        "avg_eventual_pnl_pct":
            safe_mean(
                group["eventual_pnl_hindsight_pct"]
            ),

        "median_eventual_pnl_pct":
            safe_median(
                group["eventual_pnl_hindsight_pct"]
            ),

        "positive_eventual_pct":
            positive_pct(
                group["eventual_pnl_hindsight_pct"]
            ),

        "avg_pnl_change_flat_to_resume_pct":
            safe_mean(
                group["pnl_change_flat_to_resume_pct"]
            ),

        "median_pnl_change_flat_to_resume_pct":
            safe_median(
                group["pnl_change_flat_to_resume_pct"]
            ),

        "avg_resumed_peak_change_pct":
            safe_mean(
                group["resumed_peak_change_pct"]
            ),

        "median_resumed_peak_change_pct":
            safe_median(
                group["resumed_peak_change_pct"]
            ),
    })


summary_df = pd.DataFrame(summary_rows)

summary_file = (
    OUTPUT_DIR
    / "nvda_peak_resumption_after_flat_summary.csv"
)

summary_df.to_csv(
    summary_file,
    index=False
)


# ============================================================
# SUMMARY 2 — FLAT LENGTH / RESOLUTION
# ============================================================

length_summary = (
    episodes_df
    .groupby(
        [
            "resolution",
            "flat_observations",
        ],
        dropna=False
    )
    .agg(
        episodes=("trade_id", "size"),
        unique_trades=("trade_id", "nunique"),

        avg_flat_duration_minutes=(
            "flat_duration_minutes",
            "mean"
        ),

        avg_pnl_change_during_flat_pct=(
            "pnl_change_during_flat_pct",
            "mean"
        ),

        avg_giveback_change_during_flat_points=(
            "giveback_change_during_flat_points",
            "mean"
        ),

        avg_eventual_pnl_pct=(
            "eventual_pnl_hindsight_pct",
            "mean"
        ),

        positive_eventual_count=(
            "eventual_pnl_hindsight_pct",
            lambda s: int((s.dropna() > 0).sum())
        ),
    )
    .reset_index()
)

length_summary["positive_eventual_pct"] = (
    length_summary["positive_eventual_count"]
    / length_summary["episodes"]
    * 100.0
)

length_file = (
    OUTPUT_DIR
    / "nvda_peak_resumption_after_flat_resolution_summary.csv"
)

length_summary.to_csv(
    length_file,
    index=False
)


# ============================================================
# SUMMARY 3 — TRADE LEVEL
# ============================================================

trade_rows = []

for trade_id, group in episodes_df.groupby(
    "trade_id",
    sort=False
):

    eventual_values = pd.to_numeric(
        group["eventual_pnl_hindsight_pct"],
        errors="coerce"
    ).dropna()

    trade_rows.append({
        "trade_id": trade_id,
        "symbol": group.iloc[0]["symbol"],
        "direction": group.iloc[0]["direction"],

        "flat_episodes": len(group),

        "resumed_flat_episodes": int(
            (group["resolution"] == "RESUMED").sum()
        ),

        "no_resumption_flat_episodes": int(
            (group["resolution"] == "NO_RESUMPTION").sum()
        ),

        "max_flat_observations":
            group["flat_observations"].max(),

        "avg_flat_observations":
            group["flat_observations"].mean(),

        "avg_pnl_change_during_flat_pct":
            group["pnl_change_during_flat_pct"].mean(),

        "avg_pnl_change_flat_to_resume_pct":
            group["pnl_change_flat_to_resume_pct"].mean(),

        "avg_resumed_peak_change_pct":
            group["resumed_peak_change_pct"].mean(),

        "eventual_pnl_hindsight_pct":
            eventual_values.iloc[0]
            if len(eventual_values)
            else np.nan,
    })


trade_summary_df = pd.DataFrame(trade_rows)

trade_summary_file = (
    OUTPUT_DIR
    / "nvda_peak_resumption_after_flat_trade_summary.csv"
)

trade_summary_df.to_csv(
    trade_summary_file,
    index=False
)


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n")
print("=" * 110)
print("EXPERIMENT #44 RESULTS")
print("=" * 110)

print(
    f"\nFlat episodes: {len(episodes_df)}"
)

print(
    f"Trades containing flat episodes: "
    f"{episodes_df['trade_id'].nunique()}"
)

if len(episodes_df):

    resumed = episodes_df[
        episodes_df["resolution"] == "RESUMED"
    ]

    no_resume = episodes_df[
        episodes_df["resolution"] == "NO_RESUMPTION"
    ]

    print("\nRESOLUTION COUNTS")
    print("-" * 110)

    print(
        f"RESUMED: "
        f"{len(resumed)} episodes / "
        f"{resumed['trade_id'].nunique()} trades"
    )

    print(
        f"NO_RESUMPTION: "
        f"{len(no_resume)} episodes / "
        f"{no_resume['trade_id'].nunique()} trades"
    )

    print("\nRESUMED")
    print("-" * 110)

    if len(resumed):

        print(
            f"Avg flat observations: "
            f"{fmt(safe_mean(resumed['flat_observations']))}"
        )

        print(
            f"Avg flat duration: "
            f"{fmt(safe_mean(resumed['flat_duration_minutes']))} min"
        )

        print(
            f"Avg P&L change during flat: "
            f"{fmt(safe_mean(resumed['pnl_change_during_flat_pct']))}%"
        )

        print(
            f"Avg giveback change during flat: "
            f"{fmt(safe_mean(resumed['giveback_change_during_flat_points']))} points"
        )

        print(
            f"Avg peak change at resumption: "
            f"{fmt(safe_mean(resumed['resumed_peak_change_pct']))}%"
        )

        print(
            f"Avg P&L change flat -> resumed V: "
            f"{fmt(safe_mean(resumed['pnl_change_flat_to_resume_pct']))}%"
        )

        print(
            f"Avg eventual P&L: "
            f"{fmt(safe_mean(resumed['eventual_pnl_hindsight_pct']))}%"
        )

        print(
            f"Median eventual P&L: "
            f"{fmt(safe_median(resumed['eventual_pnl_hindsight_pct']))}%"
        )

        print(
            f"Positive eventual P&L: "
            f"{fmt(positive_pct(resumed['eventual_pnl_hindsight_pct']), 2)}%"
        )

    print("\nNO RESUMPTION")
    print("-" * 110)

    if len(no_resume):

        print(
            f"Avg flat observations: "
            f"{fmt(safe_mean(no_resume['flat_observations']))}"
        )

        print(
            f"Avg flat duration: "
            f"{fmt(safe_mean(no_resume['flat_duration_minutes']))} min"
        )

        print(
            f"Avg P&L change during flat: "
            f"{fmt(safe_mean(no_resume['pnl_change_during_flat_pct']))}%"
        )

        print(
            f"Avg giveback change during flat: "
            f"{fmt(safe_mean(no_resume['giveback_change_during_flat_points']))} points"
        )

        print(
            f"Avg eventual P&L: "
            f"{fmt(safe_mean(no_resume['eventual_pnl_hindsight_pct']))}%"
        )

        print(
            f"Median eventual P&L: "
            f"{fmt(safe_median(no_resume['eventual_pnl_hindsight_pct']))}%"
        )

        print(
            f"Positive eventual P&L: "
            f"{fmt(positive_pct(no_resume['eventual_pnl_hindsight_pct']), 2)}%"
        )


# ============================================================
# SHOW EPISODES
# ============================================================

print("\n")
print("=" * 110)
print("FLAT EPISODES")
print("=" * 110)

display_columns = [
    "trade_id",
    "flat_start_v_number",
    "flat_end_v_number",
    "flat_observations",
    "resolution",
    "pnl_at_flat_start_pct",
    "pnl_at_flat_end_pct",
    "pnl_change_during_flat_pct",
    "resumed_peak_change_pct",
    "pnl_change_flat_to_resume_pct",
    "eventual_pnl_hindsight_pct",
]

if len(episodes_df):

    print(
        episodes_df[
            display_columns
        ].to_string(index=False)
    )


# ============================================================
# METADATA
# ============================================================

metadata_file = (
    OUTPUT_DIR
    / "exp44_metadata.txt"
)

with open(metadata_file, "w", encoding="utf-8") as f:

    f.write(
        "EXPERIMENT #44 — PEAK RESUMPTION AFTER FLAT\n"
    )
    f.write(
        "============================================\n\n"
    )

    f.write(
        "Purpose:\n"
    )
    f.write(
        "Observe what happens when favorable peak stops advancing "
        "and later resumes advancing.\n\n"
    )

    f.write(
        "Source:\n"
    )
    f.write(
        str(INPUT_FILE)
        + "\n\n"
    )

    f.write(
        "Source is the actual Experiment #42 CSV.\n\n"
    )

    f.write(
        "PEAK_FLAT definition:\n"
    )
    f.write(
        "relationship_type == PEAK_FLAT\n\n"
    )

    f.write(
        "PEAK RESUMPTION definition:\n"
    )
    f.write(
        "The first V after a PEAK_FLAT run has "
        "prior_peak_change_from_previous_v_pct > 0.\n\n"
    )

    f.write(
        "NO_RESUMPTION definition:\n"
    )
    f.write(
        "No next V exists, or the next V does not have a "
        "positive prior_peak_change_from_previous_v_pct.\n\n"
    )

    f.write(
        "Important:\n"
    )
    f.write(
        "No threshold was invented.\n"
    )
    f.write(
        "No production rule was created.\n"
    )
    f.write(
        "No entry or exit rule was changed.\n"
    )
    f.write(
        "This is pure observation.\n\n"
    )

    f.write(
        f"Source rows: {len(df)}\n"
    )

    f.write(
        f"Unique trades: {df['trade_id'].nunique()}\n"
    )

    f.write(
        f"Flat episodes: {len(episodes_df)}\n"
    )

    if len(episodes_df):

        f.write(
            f"Resumed episodes: "
            f"{int((episodes_df['resolution'] == 'RESUMED').sum())}\n"
        )

        f.write(
            f"No-resumption episodes: "
            f"{int((episodes_df['resolution'] == 'NO_RESUMPTION').sum())}\n"
        )


# ============================================================
# FINAL
# ============================================================

print("\n")
print("=" * 110)
print("EXPERIMENT #44 COMPLETE")
print("=" * 110)

print("\nOUTPUT DIRECTORY:")
print(OUTPUT_DIR)

print("\nFILES:")
print(f"  {episodes_file}")
print(f"  {summary_file}")
print(f"  {length_file}")
print(f"  {trade_summary_file}")
print(f"  {metadata_file}")

print("\n")
print("IMPORTANT:")
print("This experiment is observation only.")
print("No threshold has been promoted.")
print("No production strategy has been changed.")
print("No entry/exit rule has been created.")

print("\nNEXT STEP:")
print("Inspect the actual #44 output before deciding what #45 should test.")
