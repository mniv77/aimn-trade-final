"""
Experiment #45 — Flat Peak + P&L Behavior

QUESTION
--------
When the favorable peak is flat, what is P&L doing?

We observe:

    PEAK_FLAT
        |
        +-- P&L IMPROVING
        +-- P&L STABLE
        +-- P&L DECLINING

Then we observe what happens afterward.

PURE OBSERVATION ONLY.

No trading rule.
No threshold.
No optimization.
No production change.

SOURCE:
Experiment #42 actual transition file.
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
    / "exp45_flat_pnl_behavior"
)

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD
# ============================================================

print("=" * 100)
print("EXPERIMENT #45 — FLAT PEAK + P&L BEHAVIOR")
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
    "pnl_at_v_pct",
    "eventual_pnl_hindsight_pct",
    "v_number",
    "total_v_events_in_trade",
    "pnl_change_from_previous_v_pct",
    "prior_peak_change_from_previous_v_pct",
    "pnl_peak_relationship",
    "relationship_type",
    "sequence_position",
    "next_v_pnl_higher",
    "next_v_pnl_lower",
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
# SORT
# ============================================================

df["event_time_utc"] = pd.to_datetime(
    df["event_time_utc"],
    utc=True
)

df = df.sort_values(
    [
        "trade_id",
        "event_time_utc",
        "v_number"
    ]
).reset_index(drop=True)


# ============================================================
# VERIFY FLAT DATA
# ============================================================

flat_mask = (
    df["pnl_peak_relationship"]
    .astype(str)
    .str.strip()
    == "PEAK_FLAT"
)

flat = df.loc[
    flat_mask
].copy()

print("\n" + "=" * 100)
print("FLAT DATA CHECK")
print("=" * 100)

print(
    "\nPEAK_FLAT rows:",
    len(flat)
)

print(
    "PEAK_FLAT trades:",
    flat["trade_id"].nunique()
)

if flat.empty:
    raise RuntimeError(
        "No PEAK_FLAT rows found."
    )


# ============================================================
# P&L BEHAVIOR
# ============================================================
#
# IMPORTANT:
#
# We do NOT invent a numeric threshold.
#
# We use the actual sequential P&L information already
# contained in #42.
#
# For a flat episode:
#
#   first P&L
#   last P&L
#
# If there is only one flat V, there is no within-flat
# P&L movement observable.
#
# For multi-V flat sequences:
#
#   delta > 0  = IMPROVING
#   delta < 0  = DECLINING
#   delta == 0 = STABLE
#
# ============================================================

episodes = []

for trade_id, trade_df in df.groupby(
    "trade_id",
    sort=False
):

    trade_df = trade_df.sort_values(
        [
            "event_time_utc",
            "v_number"
        ]
    ).reset_index(drop=True)

    flat_positions = [
        i
        for i, value in enumerate(
            trade_df["pnl_peak_relationship"]
            .astype(str)
        )
        if value.strip() == "PEAK_FLAT"
    ]

    if not flat_positions:
        continue

    # --------------------------------------------------------
    # Group consecutive flat V events.
    # --------------------------------------------------------

    groups = []

    current = [
        flat_positions[0]
    ]

    for pos in flat_positions[1:]:

        if pos == current[-1] + 1:

            current.append(pos)

        else:

            groups.append(current)

            current = [pos]

    groups.append(current)


    # --------------------------------------------------------
    # Process each flat episode.
    # --------------------------------------------------------

    for episode_number, positions in enumerate(
        groups,
        start=1
    ):

        first_pos = positions[0]
        last_pos = positions[-1]

        first = trade_df.iloc[
            first_pos
        ]

        last = trade_df.iloc[
            last_pos
        ]

        pnl_start = float(
            first["pnl_at_v_pct"]
        )

        pnl_end = float(
            last["pnl_at_v_pct"]
        )

        pnl_delta = (
            pnl_end
            - pnl_start
        )

        flat_count = len(
            positions
        )

        # ----------------------------------------------------
        # P&L behavior.
        #
        # For a one-V flat episode, no P&L movement occurred
        # between flat observations.
        # ----------------------------------------------------

        if flat_count == 1:

            pnl_behavior = (
                "SINGLE_FLAT_OBSERVATION"
            )

        elif pnl_delta > 0:

            pnl_behavior = (
                "P&L_IMPROVING"
            )

        elif pnl_delta < 0:

            pnl_behavior = (
                "P&L_DECLINING"
            )

        else:

            pnl_behavior = (
                "P&L_STABLE"
            )


        # ----------------------------------------------------
        # What comes next?
        # ----------------------------------------------------

        next_pos = (
            last_pos + 1
        )

        if next_pos < len(
            trade_df
        ):

            next_row = trade_df.iloc[
                next_pos
            ]

            next_relationship = str(
                next_row[
                    "pnl_peak_relationship"
                ]
            ).strip()

            next_pnl = float(
                next_row[
                    "pnl_at_v_pct"
                ]
            )

            next_pnl_change = float(
                next_row[
                    "pnl_change_from_previous_v_pct"
                ]
            )

            peak_resumed = (
                next_relationship
                == "A_PNL_UP_PEAK_UP"
            )

            if peak_resumed:

                next_outcome = (
                    "PEAK_RESUMED"
                )

            elif next_relationship == (
                "B_PNL_DOWN_PEAK_UP"
            ):

                next_outcome = (
                    "PEAK_DECLINED_AFTER_FLAT"
                )

            elif next_relationship == (
                "PEAK_FLAT"
            ):

                next_outcome = (
                    "FLAT_CONTINUED"
                )

            else:

                next_outcome = (
                    "OTHER"
                )

        else:

            next_relationship = (
                "NO_NEXT_V"
            )

            next_pnl = np.nan

            next_pnl_change = np.nan

            peak_resumed = False

            next_outcome = (
                "NO_NEXT_V"
            )


        # ----------------------------------------------------
        # Eventual result.
        # ----------------------------------------------------

        eventual_pnl = float(
            first[
                "eventual_pnl_hindsight_pct"
            ]
        )


        if eventual_pnl > 0:

            eventual_result = (
                "EVENTUAL_POSITIVE"
            )

        elif eventual_pnl < 0:

            eventual_result = (
                "EVENTUAL_NEGATIVE"
            )

        else:

            eventual_result = (
                "EVENTUAL_ZERO"
            )


        # ----------------------------------------------------
        # Save episode.
        # ----------------------------------------------------

        episodes.append(
            {
                "trade_id":
                    trade_id,

                "case_id":
                    first["case_id"],

                "symbol":
                    first["symbol"],

                "direction":
                    first["direction"],

                "flat_episode_number":
                    episode_number,

                "first_flat_v_number":
                    int(
                        first["v_number"]
                    ),

                "last_flat_v_number":
                    int(
                        last["v_number"]
                    ),

                "flat_v_count":
                    flat_count,

                "flat_start_time_utc":
                    first[
                        "event_time_utc"
                    ],

                "flat_end_time_utc":
                    last[
                        "event_time_utc"
                    ],

                "pnl_at_flat_start_pct":
                    pnl_start,

                "pnl_at_flat_end_pct":
                    pnl_end,

                "pnl_change_during_flat_pct":
                    pnl_delta,

                "pnl_behavior":
                    pnl_behavior,

                "next_relationship":
                    next_relationship,

                "next_pnl_pct":
                    next_pnl,

                "next_pnl_change_pct":
                    next_pnl_change,

                "next_outcome":
                    next_outcome,

                "peak_resumed":
                    peak_resumed,

                "eventual_pnl_hindsight_pct":
                    eventual_pnl,

                "eventual_result":
                    eventual_result,
            }
        )


episodes_df = pd.DataFrame(
    episodes
)


# ============================================================
# SAVE RAW EPISODES
# ============================================================

episodes_file = (
    OUT_DIR
    / "nvda_flat_pnl_behavior_episodes.csv"
)

episodes_df.to_csv(
    episodes_file,
    index=False
)


# ============================================================
# BASIC COUNTS
# ============================================================

print("\n" + "=" * 100)
print("P&L BEHAVIOR COUNTS")
print("=" * 100)

print(
    episodes_df[
        "pnl_behavior"
    ]
    .value_counts(
        dropna=False
    )
    .to_string()
)


print("\n" + "=" * 100)
print("NEXT OUTCOME COUNTS")
print("=" * 100)

print(
    episodes_df[
        "next_outcome"
    ]
    .value_counts(
        dropna=False
    )
    .to_string()
)


print("\n" + "=" * 100)
print("EVENTUAL RESULT COUNTS")
print("=" * 100)

print(
    episodes_df[
        "eventual_result"
    ]
    .value_counts(
        dropna=False
    )
    .to_string()
)


# ============================================================
# SUMMARY BY P&L BEHAVIOR
# ============================================================

summary_rows = []

for behavior, group in episodes_df.groupby(
    "pnl_behavior",
    dropna=False
):

    summary_rows.append(
        {
            "pnl_behavior":
                behavior,

            "episodes":
                len(group),

            "unique_trades":
                group[
                    "trade_id"
                ].nunique(),

            "peak_resumed_count":
                int(
                    group[
                        "peak_resumed"
                    ].sum()
                ),

            "peak_resumed_pct":
                group[
                    "peak_resumed"
                ].mean() * 100,

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

            "eventual_positive_pct":
                (
                    group[
                        "eventual_pnl_hindsight_pct"
                    ] > 0
                ).mean() * 100,

            "eventual_negative_pct":
                (
                    group[
                        "eventual_pnl_hindsight_pct"
                    ] < 0
                ).mean() * 100,
        }
    )


summary_df = pd.DataFrame(
    summary_rows
)

summary_file = (
    OUT_DIR
    / "nvda_flat_pnl_behavior_summary.csv"
)

summary_df.to_csv(
    summary_file,
    index=False
)


# ============================================================
# PRINT SUMMARY
# ============================================================

print("\n" + "=" * 100)
print("SUMMARY BY P&L BEHAVIOR")
print("=" * 100)

print(
    summary_df.to_string(
        index=False
    )
)


# ============================================================
# CROSS TAB
# ============================================================

print("\n" + "=" * 100)
print("P&L BEHAVIOR × NEXT OUTCOME")
print("=" * 100)

cross = pd.crosstab(
    episodes_df[
        "pnl_behavior"
    ],
    episodes_df[
        "next_outcome"
    ]
)

print(
    cross.to_string()
)


print("\n" + "=" * 100)
print("P&L BEHAVIOR × EVENTUAL RESULT")
print("=" * 100)

cross2 = pd.crosstab(
    episodes_df[
        "pnl_behavior"
    ],
    episodes_df[
        "eventual_result"
    ]
)

print(
    cross2.to_string()
)


# ============================================================
# DETAILED EPISODES
# ============================================================

print("\n" + "=" * 100)
print("DETAILED FLAT EPISODES")
print("=" * 100)

detail_columns = [
    "trade_id",
    "flat_episode_number",
    "first_flat_v_number",
    "last_flat_v_number",
    "flat_v_count",
    "pnl_at_flat_start_pct",
    "pnl_at_flat_end_pct",
    "pnl_change_during_flat_pct",
    "pnl_behavior",
    "next_relationship",
    "next_pnl_pct",
    "next_outcome",
    "eventual_pnl_hindsight_pct",
    "eventual_result",
]

print(
    episodes_df[
        detail_columns
    ].to_string(index=False)
)


# ============================================================
# TRADE-LEVEL PATHS
# ============================================================

print("\n" + "=" * 100)
print("TRADE-LEVEL P&L BEHAVIOR")
print("=" * 100)

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
            f"P&L "
            f"{row['pnl_at_flat_start_pct']:.4f}"
            f" -> "
            f"{row['pnl_at_flat_end_pct']:.4f} "
            f"delta="
            f"{row['pnl_change_during_flat_pct']:.4f} "
            f"[{row['pnl_behavior']}] "
            f"next="
            f"{row['next_outcome']} "
            f"eventual="
            f"{row['eventual_pnl_hindsight_pct']:.4f}"
        )


# ============================================================
# METADATA
# ============================================================

metadata_file = (
    OUT_DIR
    / "exp45_metadata.txt"
)

with open(
    metadata_file,
    "w"
) as f:

    f.write(
        "Experiment #45 — Flat Peak + P&L Behavior\n"
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
        f"PEAK_FLAT rows: {len(flat)}\n"
    )

    f.write(
        f"Flat episodes: {len(episodes_df)}\n"
    )

    f.write(
        f"Flat trades: "
        f"{episodes_df['trade_id'].nunique()}\n"
    )

    f.write(
        "\nP&L behavior is descriptive only.\n"
    )

    f.write(
        "No numeric threshold was introduced.\n"
    )

    f.write(
        "No trading rule was created.\n"
    )

    f.write(
        "No production logic was changed.\n"
    )


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 100)
print("FILES WRITTEN")
print("=" * 100)

print(
    episodes_file
)

print(
    summary_file
)

print(
    metadata_file
)

print("\nEXPERIMENT #45 COMPLETE")

print(
    "No rule was created."
)

print(
    "No threshold was tested."
)

print(
    "No production logic was changed."
)

print("=" * 100)
