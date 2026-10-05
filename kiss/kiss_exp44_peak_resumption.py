"""
Experiment #44 — Peak Resumption After Flat

QUESTION
--------
When the favorable peak stops advancing, then advances again,
what happened to P&L during the flat period?

SOURCE
------
Experiment #42 actual output:

kiss/results/exp42_v_peak_divergence/
    nvda_v_peak_divergence_transitions.csv

IMPORTANT
---------
This is PURE OBSERVATION.

No trading rule.
No threshold.
No optimization.
No production change.

The categorical field used for flat peak behavior is:

    pnl_peak_relationship == "PEAK_FLAT"

NOT:

    relationship_type == "PEAK_FLAT"

The latter contains "FLAT_OR_MIXED".
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

ROOT = Path.home() / "aimn-trade-final"

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
    / "exp44_peak_resumption"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOAD
# ============================================================

print("=" * 100)
print("EXPERIMENT #44 — PEAK RESUMPTION AFTER FLAT")
print("=" * 100)

print("\nSOURCE:")
print(SOURCE)

df = pd.read_csv(SOURCE)

print("\nSOURCE SHAPE:")
print(df.shape)


# ============================================================
# REQUIRED COLUMNS
# ============================================================

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
    "eventual_pnl_hindsight_pct",
    "v_number",
    "total_v_events_in_trade",
    "previous_v_time_utc",
    "previous_v_pnl_pct",
    "previous_giveback_pct_of_peak",
    "previous_prior_peak_pct",
    "minutes_since_previous_v",
    "pnl_change_from_previous_v_pct",
    "giveback_change_from_previous_v_pct_points",
    "prior_peak_change_from_previous_v_pct",
    "pnl_sequence_direction",
    "giveback_sequence_direction",
    "prior_peak_sequence_direction",
    "previous_v_had_recovered",
    "sequence_position",
    "v_to_v_transition",
    "previous_v_recovery_state",
    "next_v_pnl_higher",
    "next_v_pnl_lower",
    "pnl_peak_relationship",
    "relationship_type",
]

missing = [
    c for c in required
    if c not in df.columns
]

if missing:
    raise RuntimeError(
        "Missing required columns:\n"
        + "\n".join(missing)
    )

print("\nREQUIRED COLUMN CHECK: PASSED")


# ============================================================
# VERIFY ACTUAL #42 STRUCTURE
# ============================================================

print("\n" + "=" * 100)
print("VERIFY PEAK FLAT FIELD")
print("=" * 100)

print(
    "\npnl_peak_relationship value counts:"
)

print(
    df["pnl_peak_relationship"]
    .value_counts(dropna=False)
    .to_string()
)

flat_mask = (
    df["pnl_peak_relationship"]
    .astype(str)
    .str.strip()
    == "PEAK_FLAT"
)

flat_rows = df.loc[flat_mask].copy()

print(
    "\nPEAK_FLAT ROWS:",
    len(flat_rows)
)

print(
    "PEAK_FLAT TRADES:",
    flat_rows["trade_id"].nunique()
)


if len(flat_rows) == 0:
    raise RuntimeError(
        "PEAK_FLAT rows = 0. "
        "The source file does not match the verified #42 structure."
    )


# ============================================================
# SORT
# ============================================================

df["event_time_utc"] = pd.to_datetime(
    df["event_time_utc"],
    utc=True,
)

df = df.sort_values(
    ["trade_id", "event_time_utc", "v_number"]
).reset_index(drop=True)


# ============================================================
# BUILD FLAT EPISODES
# ============================================================

episodes = []

for trade_id, trade_df in df.groupby(
    "trade_id",
    sort=False
):

    trade_df = trade_df.sort_values(
        ["event_time_utc", "v_number"]
    ).reset_index(drop=True)

    flat_positions = [
        i
        for i, value in enumerate(
            trade_df["pnl_peak_relationship"].astype(str)
        )
        if value.strip() == "PEAK_FLAT"
    ]

    if not flat_positions:
        continue

    # --------------------------------------------------------
    # Group consecutive PEAK_FLAT rows into one flat episode.
    # --------------------------------------------------------

    groups = []

    current = [flat_positions[0]]

    for pos in flat_positions[1:]:

        if pos == current[-1] + 1:
            current.append(pos)
        else:
            groups.append(current)
            current = [pos]

    groups.append(current)

    for episode_number, positions in enumerate(
        groups,
        start=1
    ):

        first_pos = positions[0]
        last_pos = positions[-1]

        first = trade_df.iloc[first_pos]
        last = trade_df.iloc[last_pos]

        # ----------------------------------------------------
        # What comes immediately after the flat sequence?
        # ----------------------------------------------------

        next_pos = last_pos + 1

        if next_pos < len(trade_df):

            next_row = trade_df.iloc[next_pos]

            next_relationship = str(
                next_row["pnl_peak_relationship"]
            ).strip()

            peak_resumed = (
                next_relationship == "A_PNL_UP_PEAK_UP"
            )

            next_event_time = (
                next_row["event_time_utc"]
            )

            pnl_at_resumption = (
                float(next_row["pnl_at_v_pct"])
            )

            peak_change_at_resumption = (
                float(
                    next_row[
                        "prior_peak_change_from_previous_v_pct"
                    ]
                )
            )

            pnl_change_at_resumption = (
                float(
                    next_row[
                        "pnl_change_from_previous_v_pct"
                    ]
                )

            )

        else:

            next_relationship = "NO_NEXT_V"

            peak_resumed = False

            next_event_time = pd.NaT

            pnl_at_resumption = np.nan

            peak_change_at_resumption = np.nan

            pnl_change_at_resumption = np.nan


        # ----------------------------------------------------
        # Flat-period measurements
        # ----------------------------------------------------

        pnl_begin = float(
            first["pnl_at_v_pct"]
        )

        pnl_end = float(
            last["pnl_at_v_pct"]
        )

        pnl_change_during_flat = (
            pnl_end - pnl_begin
        )

        flat_v_count = len(positions)

        flat_start = first["event_time_utc"]

        flat_end = last["event_time_utc"]

        flat_duration_minutes = (
            (flat_end - flat_start)
            .total_seconds()
            / 60.0
        )

        eventual_pnl = float(
            first["eventual_pnl_hindsight_pct"]
        )

        # ----------------------------------------------------
        # Classify only descriptively.
        # ----------------------------------------------------

        if peak_resumed:

            resolution = "FLAT_TO_RESUME"

        else:

            if next_relationship == "NO_NEXT_V":

                resolution = "FLAT_NO_NEXT_V"

            else:

                resolution = "FLAT_NO_RESUMPTION"


        episodes.append(
            {
                "trade_id": trade_id,
                "case_id": first["case_id"],
                "symbol": first["symbol"],
                "direction": first["direction"],

                "flat_episode_number":
                    episode_number,

                "flat_start_time_utc":
                    flat_start,

                "flat_end_time_utc":
                    flat_end,

                "flat_duration_minutes":
                    flat_duration_minutes,

                "first_flat_v_number":
                    int(first["v_number"]),

                "last_flat_v_number":
                    int(last["v_number"]),

                "flat_v_count":
                    flat_v_count,

                "pnl_at_flat_start_pct":
                    pnl_begin,

                "pnl_at_flat_end_pct":
                    pnl_end,

                "pnl_change_during_flat_pct":
                    pnl_change_during_flat,

                "eventual_pnl_hindsight_pct":
                    eventual_pnl,

                "next_relationship":
                    next_relationship,

                "peak_resumed":
                    peak_resumed,

                "resumption_time_utc":
                    next_event_time,

                "pnl_at_resumption_pct":
                    pnl_at_resumption,

                "peak_change_at_resumption_pct":
                    peak_change_at_resumption,

                "pnl_change_at_resumption_pct":
                    pnl_change_at_resumption,

                "resolution":
                    resolution,
            }
        )


episodes_df = pd.DataFrame(episodes)


# ============================================================
# FAIL SAFE
# ============================================================

if episodes_df.empty:

    raise RuntimeError(
        "No flat episodes were constructed even though "
        "PEAK_FLAT rows exist. "
        "Stop here and inspect the sequence logic."
    )


# ============================================================
# SAVE EPISODES
# ============================================================

episodes_file = (
    OUT_DIR
    / "nvda_peak_flat_episodes.csv"
)

episodes_df.to_csv(
    episodes_file,
    index=False
)


# ============================================================
# BASIC SUMMARY
# ============================================================

print("\n" + "=" * 100)
print("FLAT EPISODE SUMMARY")
print("=" * 100)

print(
    "\nFlat episodes:",
    len(episodes_df)
)

print(
    "Unique trades:",
    episodes_df["trade_id"].nunique()
)

print(
    "\nResolution:"
)

print(
    episodes_df["resolution"]
    .value_counts(dropna=False)
    .to_string()
)


# ============================================================
# SUMMARY BY RESOLUTION
# ============================================================

summary_rows = []

for resolution, group in episodes_df.groupby(
    "resolution",
    dropna=False
):

    summary_rows.append(
        {
            "resolution":
                resolution,

            "episodes":
                len(group),

            "unique_trades":
                group["trade_id"].nunique(),

            "avg_flat_v_count":
                group["flat_v_count"].mean(),

            "median_flat_v_count":
                group["flat_v_count"].median(),

            "avg_flat_duration_minutes":
                group["flat_duration_minutes"].mean(),

            "median_flat_duration_minutes":
                group["flat_duration_minutes"].median(),

            "avg_pnl_change_during_flat_pct":
                group[
                    "pnl_change_during_flat_pct"
                ].mean(),

            "median_pnl_change_during_flat_pct":
                group[
                    "pnl_change_during_flat_pct"
                ].median(),

            "avg_pnl_at_flat_start_pct":
                group[
                    "pnl_at_flat_start_pct"
                ].mean(),

            "avg_pnl_at_flat_end_pct":
                group[
                    "pnl_at_flat_end_pct"
                ].mean(),

            "avg_eventual_pnl_pct":
                group[
                    "eventual_pnl_hindsight_pct"
                ].mean(),

            "median_eventual_pnl_pct":
                group[
                    "eventual_pnl_hindsight_pct"
                ].median(),

            "positive_eventual_pct":
                (
                    group[
                        "eventual_pnl_hindsight_pct"
                    ] > 0
                ).mean() * 100,
        }
    )


summary_df = pd.DataFrame(
    summary_rows
)

summary_file = (
    OUT_DIR
    / "nvda_peak_flat_summary.csv"
)

summary_df.to_csv(
    summary_file,
    index=False
)


# ============================================================
# PRINT SUMMARY
# ============================================================

print(
    "\n" + "=" * 100
)

print(
    "SUMMARY BY FLAT RESOLUTION"
)

print(
    "=" * 100
)

if not summary_df.empty:

    print(
        summary_df.to_string(
            index=False
        )
    )


# ============================================================
# FLAT SEQUENCE DETAILS
# ============================================================

print(
    "\n" + "=" * 100
)

print(
    "FLAT EPISODES — DETAILED"
)

print(
    "=" * 100
)

detail_columns = [
    "trade_id",
    "flat_episode_number",
    "first_flat_v_number",
    "last_flat_v_number",
    "flat_v_count",
    "flat_duration_minutes",
    "pnl_at_flat_start_pct",
    "pnl_at_flat_end_pct",
    "pnl_change_during_flat_pct",
    "next_relationship",
    "peak_resumed",
    "pnl_at_resumption_pct",
    "eventual_pnl_hindsight_pct",
    "resolution",
]

print(
    episodes_df[
        detail_columns
    ].to_string(index=False)
)


# ============================================================
# TRADE-LEVEL PATHS
# ============================================================

print(
    "\n" + "=" * 100
)

print(
    "TRADE-LEVEL FLAT PATHS"
)

print(
    "=" * 100
)

for trade_id, group in episodes_df.groupby(
    "trade_id",
    sort=False
):

    print(
        f"\n{trade_id}"
    )

    for _, row in group.iterrows():

        print(
            "  "
            f"flat#{int(row['flat_episode_number'])} "
            f"V{int(row['first_flat_v_number'])}"
            f"-V{int(row['last_flat_v_number'])} "
            f"count={int(row['flat_v_count'])} "
            f"duration={row['flat_duration_minutes']:.1f}m "
            f"P&L "
            f"{row['pnl_at_flat_start_pct']:.4f}"
            f" -> "
            f"{row['pnl_at_flat_end_pct']:.4f} "
            f"delta="
            f"{row['pnl_change_during_flat_pct']:.4f} "
            f"next="
            f"{row['next_relationship']} "
            f"eventual="
            f"{row['eventual_pnl_hindsight_pct']:.4f} "
            f"{row['resolution']}"
        )


# ============================================================
# OBSERVATION COUNTS
# ============================================================

print(
    "\n" + "=" * 100
)

print(
    "OBSERVATION COUNTS"
)

print(
    "=" * 100
)

resume = episodes_df[
    episodes_df["resolution"]
    == "FLAT_TO_RESUME"
]

no_resume = episodes_df[
    episodes_df["resolution"]
    == "FLAT_NO_RESUMPTION"
]

no_next = episodes_df[
    episodes_df["resolution"]
    == "FLAT_NO_NEXT_V"
]


print(
    "\nFLAT -> RESUME:"
)

print(
    "Episodes:",
    len(resume)
)

print(
    "Trades:",
    resume["trade_id"].nunique()
)


print(
    "\nFLAT -> NO RESUMPTION:"
)

print(
    "Episodes:",
    len(no_resume)
)

print(
    "Trades:",
    no_resume["trade_id"].nunique()
)


print(
    "\nFLAT -> NO NEXT V:"
)

print(
    "Episodes:",
    len(no_next)
)

print(
    "Trades:",
    no_next["trade_id"].nunique()
)


# ============================================================
# METADATA
# ============================================================

metadata_file = (
    OUT_DIR
    / "exp44_metadata.txt"
)

with open(
    metadata_file,
    "w"
) as f:

    f.write(
        "Experiment #44 — Peak Resumption After Flat\n"
    )

    f.write(
        "Pure observation only.\n\n"
    )

    f.write(
        f"Source: {SOURCE}\n"
    )

    f.write(
        f"Source rows: {len(df)}\n"
    )

    f.write(
        "Flat field: pnl_peak_relationship\n"
    )

    f.write(
        "Flat value: PEAK_FLAT\n"
    )

    f.write(
        f"PEAK_FLAT rows: {len(flat_rows)}\n"
    )

    f.write(
        f"Flat episodes: {len(episodes_df)}\n"
    )

    f.write(
        f"Flat trades: "
        f"{episodes_df['trade_id'].nunique()}\n"
    )

    f.write(
        "\nNo trading rule was created.\n"
    )


# ============================================================
# FINAL
# ============================================================

print(
    "\n" + "=" * 100
)

print(
    "FILES WRITTEN"
)

print(
    "=" * 100
)

print(
    episodes_file
)

print(
    summary_file
)

print(
    metadata_file
)

print(
    "\nEXPERIMENT #44 COMPLETE"
)

print(
    "No rule was created."
)

print(
    "No threshold was tested."
)

print(
    "No production logic was changed."
)

print(
    "=" * 100
)
