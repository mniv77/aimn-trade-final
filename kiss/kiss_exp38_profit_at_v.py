#!/usr/bin/env python3

"""
EXPERIMENT #38
NVDA PROFIT-AT-V — PURE OBSERVATION

Research only.

Question:

    When an existing NVDA trade is profitable and price begins to pull
    back from a favorable peak, what actually happens afterward?

This experiment does NOT:
    - create an entry rule
    - create an exit rule
    - select a V threshold
    - classify V's as minor/medium/major
    - optimize parameters
    - change production code
    - place orders
    - train AI

The experiment only records observations from completed 5-minute candles.

Causal sequence:

    ENTRY
       |
       v
    PROFIT
       |
       v
    FAVORABLE PEAK
       |
       v
    FIRST ADVERSE CANDLE
       |
       v
    OBSERVE
       |
       +--------------------+
       |                    |
       v                    v
    RECOVERY            CONTINUED
                        GIVE-BACK

Source population:
    Experiment #30
    NVDA
    0.25% entry trail
    1.50% exit trail

Price path:
    Experiment #32 raw 5-minute trajectory.

Important:
    The trajectory file uses transition_known_utc, NOT transition_time_utc.
    The geometry file supplies transition_time_utc and transition_close.

No hindsight information is used to identify an event.
Final trade outcome is recorded only as a reference field.
"""

from pathlib import Path
import argparse
import sys

import numpy as np
import pandas as pd


ROOT = Path.cwd()

TRAJ = ROOT / "kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv"
GEOM = ROOT / "kiss/results/exp32_raw_candle_v_geometry/raw_v_geometry.csv"
TRADES = ROOT / "kiss/results/exp30_nvda_transition_match/nvda_trades_entry_025.csv"

OUT = ROOT / "kiss/results/exp38_profit_at_v"


# ============================================================================
# HELPERS
# ============================================================================

def need(path):
    if not path.exists():
        print(f"ERROR: missing file: {path}")
        sys.exit(1)


def numeric(df, columns):
    """
    Force selected columns to numeric.
    Invalid values become NaN.
    """
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )
    return df


def dates(df, columns):
    """
    Force selected columns to UTC timestamps.
    """
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col],
                utc=True,
                errors="coerce",
            )
    return df


# ============================================================================
# MAIN
# ============================================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--round-trip-cost-pct",
        type=float,
        default=0.0,
        help="Round-trip commission + slippage in percent.",
    )

    args = parser.parse_args()

    if args.round_trip_cost_pct < 0:
        sys.exit("Round-trip cost cannot be negative.")

    # ------------------------------------------------------------------------
    # Required files
    # ------------------------------------------------------------------------

    for f in (TRAJ, GEOM, TRADES):
        need(f)

    # ------------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------------

    traj = pd.read_csv(TRAJ)
    geom = pd.read_csv(GEOM)
    trades = pd.read_csv(TRADES)

    # ------------------------------------------------------------------------
    # Date conversion
    # ------------------------------------------------------------------------

    traj = dates(
        traj,
        [
            "transition_known_utc",
            "candle_utc",
        ],
    )

    geom = dates(
        geom,
        [
            "transition_time_utc",
            "transition_known_utc",
        ],
    )

    trades = dates(
        trades,
        [
            "transition_time_utc",
            "transition_known_utc",
            "entry_time_utc",
            "exit_time_utc",
        ],
    )

    # ------------------------------------------------------------------------
    # Numeric conversion
    # ------------------------------------------------------------------------

    traj = numeric(
        traj,
        [
            "minutes_after_known",
            "open",
            "high",
            "low",
            "close",
            "adverse_from_transition_pct",
            "favorable_from_transition_pct",
            "recovery_from_raw_extreme_pct",
        ],
    )

    geom = numeric(
        geom,
        [
            "transition_close",
            "v_depth_pct",
            "max_favorable_from_transition_pct",
            "max_adverse_from_transition_pct",
        ],
    )

    trades = numeric(
        trades,
        [
            "entry_price",
            "exit_price",
            "pnl_pct",
            "max_favorable_pct",
            "max_adverse_pct",
            "entry_wait_minutes",
            "trade_minutes",
        ],
    )

    # ------------------------------------------------------------------------
    # NVDA only
    # ------------------------------------------------------------------------

    traj = traj[
        traj["symbol"].eq("NVDA")
    ].copy()

    geom = geom[
        geom["symbol"].eq("NVDA")
    ].copy()

    trades = trades[
        trades["symbol"].eq("NVDA")
    ].copy()

    if traj.empty:
        sys.exit("No NVDA trajectory data.")

    if geom.empty:
        sys.exit("No NVDA geometry data.")

    if trades.empty:
        sys.exit("No NVDA trade data.")

    # =========================================================================
    # STEP 1
    #
    # Attach transition information to every 5m trajectory candle.
    #
    # IMPORTANT:
    #
    # raw_v_trajectory.csv:
    #     transition_known_utc
    #
    # raw_v_geometry.csv:
    #     transition_time_utc
    #     transition_known_utc
    #     transition_close
    #
    # Therefore the join is:
    #
    #     case_id
    #     symbol
    #     direction
    #     transition_known_utc
    # =========================================================================

    transition_info = (
        geom[
            [
                "case_id",
                "symbol",
                "direction",
                "transition_time_utc",
                "transition_known_utc",
                "transition_close",
            ]
        ]
        .drop_duplicates("case_id")
    )

    path = traj.merge(
        transition_info,
        on=[
            "case_id",
            "symbol",
            "direction",
            "transition_known_utc",
        ],
        how="left",
        validate="many_to_one",
    )

    # =========================================================================
    # STEP 2
    #
    # Attach the actual Experiment #30 trade.
    # =========================================================================

    trade_info = (
        trades[
            [
                "trade_id",
                "symbol",
                "direction",
                "transition_time_utc",
                "transition_known_utc",
                "entry_time_utc",
                "entry_price",
                "exit_time_utc",
                "exit_price",
                "pnl_pct",
                "max_favorable_pct",
                "max_adverse_pct",
                "exit_reason",
            ]
        ]
        .drop_duplicates(
            [
                "symbol",
                "direction",
                "transition_time_utc",
            ]
        )
    )

    path = path.merge(
        trade_info,
        on=[
            "symbol",
            "direction",
            "transition_time_utc",
            "transition_known_utc",
        ],
        how="left",
        validate="many_to_one",
    )

    # =========================================================================
    # STEP 3
    #
    # Sort candles.
    # =========================================================================

    path = path.sort_values(
        [
            "case_id",
            "candle_utc",
        ]
    ).reset_index(drop=True)

    # =========================================================================
    # STEP 4
    #
    # Explicitly make the merged numeric columns numeric AGAIN.
    #
    # This protects against CSV/merge dtype behavior.
    # =========================================================================

    path = numeric(
        path,
        [
            "open",
            "high",
            "low",
            "close",
            "transition_close",
            "entry_price",
            "exit_price",
            "pnl_pct",
            "max_favorable_pct",
            "max_adverse_pct",
        ],
    )

    # =========================================================================
    # STEP 5
    #
    # Determine when the actual trade is active.
    #
    # This is causal:
    #
    #     candle_time >= entry_time
    # =========================================================================

    path["trade_active"] = (
        path["entry_time_utc"].notna()
        &
        path["candle_utc"].ge(
            path["entry_time_utc"]
        )
    )

    active = path["trade_active"]

    path["minutes_from_entry"] = np.nan

    path.loc[
        active,
        "minutes_from_entry",
    ] = (
        (
            path.loc[active, "candle_utc"]
            -
            path.loc[active, "entry_time_utc"]
        )
        .dt.total_seconds()
        / 60.0
    )

    # =========================================================================
    # STEP 6
    #
    # Current trade P&L.
    # =========================================================================

    path["current_pnl_pct"] = np.nan

    long_active = (
        active
        &
        path["direction"].eq("LONG")
    )

    short_active = (
        active
        &
        path["direction"].eq("SHORT")
    )

    path.loc[
        long_active,
        "current_pnl_pct",
    ] = (
        path.loc[long_active, "close"]
        /
        path.loc[long_active, "entry_price"]
        -
        1.0
    ) * 100.0

    path.loc[
        short_active,
        "current_pnl_pct",
    ] = (
        path.loc[short_active, "entry_price"]
        /
        path.loc[short_active, "close"]
        -
        1.0
    ) * 100.0

    path = numeric(
        path,
        [
            "current_pnl_pct",
        ],
    )

    # =========================================================================
    # STEP 7
    #
    # Cost observation.
    # =========================================================================

    path["net_pnl_after_cost_pct"] = (
        path["current_pnl_pct"]
        -
        args.round_trip_cost_pct
    )

    path["cost_covered"] = (
        path["current_pnl_pct"]
        >=
        args.round_trip_cost_pct
    )

    # =========================================================================
    # STEP 8
    #
    # Favorable close P&L.
    #
    # LONG:
    #     rising price = favorable
    #
    # SHORT:
    #     falling price = favorable
    # =========================================================================

    path["favorable_close_pct"] = np.nan

    path.loc[
        long_active,
        "favorable_close_pct",
    ] = (
        path.loc[long_active, "close"]
        /
        path.loc[long_active, "entry_price"]
        -
        1.0
    ) * 100.0

    path.loc[
        short_active,
        "favorable_close_pct",
    ] = (
        path.loc[short_active, "entry_price"]
        /
        path.loc[short_active, "close"]
        -
        1.0
    ) * 100.0

    path = numeric(
        path,
        [
            "favorable_close_pct",
        ],
    )

    # =========================================================================
    # STEP 9
    #
    # Running favorable peak.
    # =========================================================================

    path["favorable_peak_pct"] = np.nan

    for case_id, gp in path.groupby(
        "case_id",
        sort=False,
    ):

        gp = gp.sort_values(
            "candle_utc"
        ).copy()

        peak = np.nan
        values = []

        for value in gp[
            "favorable_close_pct"
        ]:

            if pd.isna(value):

                values.append(peak)
                continue

            if pd.isna(peak):

                peak = float(value)

            else:

                peak = max(
                    float(peak),
                    float(value),
                )

            values.append(peak)

        path.loc[
            gp.index,
            "favorable_peak_pct",
        ] = values

    path = numeric(
        path,
        [
            "favorable_peak_pct",
        ],
    )

    # =========================================================================
    # STEP 10
    #
    # Pullback from favorable peak.
    # =========================================================================

    path["pullback_pct"] = (
        path["favorable_peak_pct"]
        -
        path["favorable_close_pct"]
    )

    path["pullback_pct"] = (
        pd.to_numeric(
            path["pullback_pct"],
            errors="coerce",
        )
        .clip(lower=0)
    )

    # =========================================================================
    # STEP 11
    #
    # Identify first adverse candle after a profitable candle.
    #
    # PURE OBSERVATION.
    #
    # We are NOT saying:
    #
    #     "This is a V."
    #
    # We are saying:
    #
    #     "A profitable favorable move has just started pulling back."
    # =========================================================================

    path["profit_pullback_start"] = False

    for case_id, gp in path.groupby(
        "case_id",
        sort=False,
    ):

        gp = gp.sort_values(
            "candle_utc"
        ).copy()

        previous_favorable = (
            gp[
                "favorable_close_pct"
            ]
            .shift(1)
        )

        event_mask = (
            gp["trade_active"]
            &
            gp["current_pnl_pct"].gt(0)
            &
            previous_favorable.notna()
            &
            gp["favorable_close_pct"].notna()
            &
            gp["favorable_close_pct"].lt(
                previous_favorable
            )
        )

        path.loc[
            gp.index,
            "profit_pullback_start",
        ] = event_mask.to_numpy()

    # =========================================================================
    # STEP 12
    #
    # Collect observation events.
    #
    # To avoid counting every candle of one continuous pullback,
    # we wait until either:
    #
    #     recovery to the prior peak
    #
    # OR
    #
    #     P&L falls to zero
    #
    # before allowing another event.
    # =========================================================================

    events = []

    for case_id, gp in path.groupby(
        "case_id",
        sort=False,
    ):
        gp = gp.sort_values(
            "candle_utc"
        ).reset_index(drop=True)

        locked = False

        for i in range(
            len(gp)
        ):

            row = gp.iloc[i]

            if not row["trade_active"]:
                continue

            if not row[
                "profit_pullback_start"
            ]:
                continue

            if locked:
                continue

            prior_peak = float(
                row["favorable_peak_pct"]
            )

            events.append(
                {
                    "case_id":
                        case_id,

                    "trade_id":
                        row["trade_id"],

                    "symbol":
                        row["symbol"],

                    "direction":
                        row["direction"],

                    "event_time_utc":
                        row["candle_utc"],

                    "entry_time_utc":
                        row["entry_time_utc"],

                    "entry_price":
                        row["entry_price"],

                    "pnl_at_v_pct":
                        float(
                            row["current_pnl_pct"]
                        ),

                    "net_pnl_at_v_pct":
                        float(
                            row[
                                "net_pnl_after_cost_pct"
                            ]
                        ),

                    "cost_covered_at_v":
                        bool(
                            row["cost_covered"]
                        ),

                    "favorable_peak_before_v_pct":
                        prior_peak,

                    "initial_pullback_pct":
                        float(
                            row["pullback_pct"]
                        ),

                    "eventual_pnl_hindsight_pct":
                        row["pnl_pct"],

                    "exit_time_utc":
                        row["exit_time_utc"],
                }
            )

            # ---------------------------------------------------------------
            # Observe subsequent candles.
            # ---------------------------------------------------------------

            for j in range(
                i + 1,
                len(gp)
            ):

                future = gp.iloc[j]

                if not future[
                    "trade_active"
                ]:

                    locked = False
                    break

                recovered = (
                    pd.notna(
                        future[
                            "favorable_close_pct"
                        ]
                    )
                    &
                    (
                        float(
                            future[
                                "favorable_close_pct"
                            ]
                        )
                        >=
                        prior_peak
                    )
                )

                lost_profit = (
                    pd.notna(
                        future[
                            "current_pnl_pct"
                        ]
                    )
                    &
                    (
                        float(
                            future[
                                "current_pnl_pct"
                            ]
                        )
                        <=
                        0.0
                    )
                )

                if recovered or lost_profit:

                    locked = False
                    break

                locked = True

    events = pd.DataFrame(
        events
    )

    # =========================================================================
    # STEP 13
    #
    # Analyze what happened AFTER each event.
    #
    # This is hindsight labeling ONLY.
    # It does not create the event.
    # =========================================================================

    analyzed = []

    for _, event in events.iterrows():

        case_id = event["case_id"]
        event_time = event[
            "event_time_utc"
        ]

        gp = path[
            (path["case_id"] == case_id)
            &
            (path["candle_utc"] >= event_time)
            &
            path["trade_active"]
        ].sort_values(
            "candle_utc"
        ).copy()

        if gp.empty:
            continue

        prior_peak = float(
            event[
                "favorable_peak_before_v_pct"
            ]
        )

        # ---------------------------------------------------------------
        # Recovery
        # ---------------------------------------------------------------

        recovery = gp[
            pd.to_numeric(
                gp["favorable_close_pct"],
                errors="coerce",
            )
            >=
            prior_peak
        ]

        recovered = not recovery.empty

        if recovered:

            recovery_time = recovery.iloc[0][
                "candle_utc"
            ]

            recovery_minutes = (
                recovery_time
                -
                event_time
            ).total_seconds() / 60.0

        else:

            recovery_time = pd.NaT
            recovery_minutes = np.nan

        # ---------------------------------------------------------------
        # Maximum/minimum after event
        # ---------------------------------------------------------------

        pnl_series = pd.to_numeric(
            gp["current_pnl_pct"],
            errors="coerce",
        )

        max_profit_after = (
            pnl_series.max()
        )

        min_pnl_after = (
            pnl_series.min()
        )

        max_pullback_after = (
            pd.to_numeric(
                gp["pullback_pct"],
                errors="coerce",
            ).max()
        )

        # ---------------------------------------------------------------
        # Fixed observation checkpoints
        # ---------------------------------------------------------------

        checkpoint_values = {}

        for minutes in (
            5,
            10,
            15,
            30,
            60,
        ):

            target = (
                event_time
                +
                pd.Timedelta(
                    minutes=minutes
                )
            )

            later = gp[
                gp["candle_utc"] >= target
            ]

            if later.empty:

                checkpoint_values[
                    f"pnl_after_{minutes}m_pct"
                ] = np.nan

            else:

                checkpoint_values[
                    f"pnl_after_{minutes}m_pct"
                ] = float(
                    pd.to_numeric(
                        later.iloc[0][
                            "current_pnl_pct"
                        ],
                        errors="coerce",
                    )
                )

        # ---------------------------------------------------------------
        # Observation label
        # ---------------------------------------------------------------

        if recovered:

            if (
                min_pnl_after
                <
                event["pnl_at_v_pct"]
            ):

                outcome = (
                    "RECOVERED_WITH_GIVEBACK"
                )

            else:

                outcome = (
                    "RECOVERED_CONTINUED"
                )

        else:

            if min_pnl_after <= 0:

                outcome = (
                    "PROFIT_GIVEN_BACK_OR_LOSS"
                )

            else:

                outcome = (
                    "DID_NOT_RECOVER_WITHIN_OBSERVATION"
                )

        row = event.to_dict()

        row.update(
            {
                "max_profit_after_v_pct":
                    max_profit_after,

                "minimum_pnl_after_v_pct":
                    min_pnl_after,

                "max_pullback_after_v_pct":
                    max_pullback_after,

                "recovered_previous_peak":
                    recovered,

                "recovery_time_utc":
                    recovery_time,

                "recovery_minutes":
                    recovery_minutes,

                "observation_outcome":
                    outcome,
            }
        )

        row.update(
            checkpoint_values
        )

        analyzed.append(
            row
        )

    events = pd.DataFrame(
        analyzed
    )

    # =========================================================================
    # STEP 14
    #
    # Per-trade summary.
    # =========================================================================

    matched_trades = (
        path[
            path["trade_id"].notna()
        ][
            [
                "case_id",
                "trade_id",
                "symbol",
                "direction",
                "transition_time_utc",
                "entry_time_utc",
                "exit_time_utc",
                "entry_price",
                "pnl_pct",
            ]
        ]
        .drop_duplicates(
            "case_id"
        )
    )

    summary_rows = []

    for _, trade in matched_trades.iterrows():

        if events.empty:

            ce = pd.DataFrame()

        else:

            ce = events[
                events["case_id"].eq(
                    trade["case_id"]
                )
            ]

        row = {
            "case_id":
                trade["case_id"],

            "trade_id":
                trade["trade_id"],

            "symbol":
                trade["symbol"],

            "direction":
                trade["direction"],

            "transition_time_utc":
                trade["transition_time_utc"],

            "entry_time_utc":
                trade["entry_time_utc"],

            "exit_time_utc":
                trade["exit_time_utc"],

            "eventual_pnl_hindsight_pct":
                trade["pnl_pct"],

            "profit_at_v_event_count":
                len(ce),
        }

        if not ce.empty:

            first = ce.iloc[0]

            row.update(
                {
                    "first_profit_at_v_pnl_pct":
                        first["pnl_at_v_pct"],

                    "first_profit_at_v_cost_covered":
                        first["cost_covered_at_v"],

                    "first_profit_at_v_peak_pct":
                        first[
                            "favorable_peak_before_v_pct"
                        ],

                    "first_profit_at_v_pullback_pct":
                        first[
                            "initial_pullback_pct"
                        ],

                    "first_v_outcome":
                        first[
                            "observation_outcome"
                        ],

                    "first_v_recovered":
                        first[
                            "recovered_previous_peak"
                        ],

                    "first_v_recovery_minutes":
                        first[
                            "recovery_minutes"
                        ],
                }
            )

        else:

            row.update(
                {
                    "first_profit_at_v_pnl_pct":
                        np.nan,

                    "first_profit_at_v_cost_covered":
                        np.nan,

                    "first_profit_at_v_peak_pct":
                        np.nan,

                    "first_profit_at_v_pullback_pct":
                        np.nan,

                    "first_v_outcome":
                        "",

                    "first_v_recovered":
                        np.nan,

                    "first_v_recovery_minutes":
                        np.nan,
                }
            )

        summary_rows.append(
            row
        )

    summary = pd.DataFrame(
        summary_rows
    )

    # =========================================================================
    # STEP 15
    #
    # Save.
    # =========================================================================

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    path_out = (
        OUT /
        "nvda_profit_at_v_path.csv"
    )

    events_out = (
        OUT /
        "nvda_profit_at_v_events.csv"
    )

    summary_out = (
        OUT /
        "nvda_profit_at_v_summary.csv"
    )

    metadata_out = (
        OUT /
        "exp38_metadata.txt"
    )

    path.to_csv(
        path_out,
        index=False,
    )

    events.to_csv(
        events_out,
        index=False,
    )

    summary.to_csv(
        summary_out,
        index=False,
    )

    metadata_out.write_text(
        """
Experiment #38 — NVDA Profit-at-V Pure Observation

Research only.

No entry rule.
No exit rule.
No V threshold.
No minor/medium/major classification.
No optimization.
No production changes.
No orders.
No AI training.

Raw trajectory source:
    Experiment #32

Trade population:
    Experiment #30
    NVDA 0.25% entry trail
    1.50% exit trail

Causal observation:
    A completed candle where the existing trade is profitable
    and the favorable close begins moving adversely.

The event is descriptive.
It is not a trading signal.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    # =========================================================================
    # REPORT
    # =========================================================================

    print()
    print("=" * 90)
    print("EXPERIMENT #38 — NVDA PROFIT-AT-V")
    print("PURE OBSERVATION")
    print("=" * 90)

    print()
    print("RESEARCH ONLY")
    print("-" * 90)
    print("No entry rule")
    print("No exit rule")
    print("No V threshold")
    print("No minor/medium/major classification")
    print("No optimization")
    print("No production changes")
    print("No orders")
    print("No AI training")

    print()
    print("DATA")
    print("-" * 90)

    print(
        f"NVDA transition cases : "
        f"{path['case_id'].nunique()}"
    )

    print(
        f"Matched NVDA trades   : "
        f"{matched_trades['trade_id'].nunique()}"
    )

    print(
        f"5m trajectory rows    : "
        f"{len(path)}"
    )

    print(
        f"Round-trip cost       : "
        f"{args.round_trip_cost_pct:.4f}%"
    )

    print()

    if events.empty:

        print(
            "NO PROFITABLE PULLBACK EVENTS FOUND."
        )

    else:

        print("PROFIT-AT-V EVENTS")
        print("-" * 90)

        print(
            f"Total events          : "
            f"{len(events)}"
        )

        print(
            f"Trades with events    : "
            f"{events['case_id'].nunique()}"
        )

        print()
        print("OBSERVED OUTCOMES")
        print("-" * 90)

        counts = (
            events[
                "observation_outcome"
            ]
            .value_counts()
            .sort_index()
        )

        for name, count in counts.items():

            print(
                f"{name:<45} {count:>5}"
            )

        print()
        print("P&L AT V")
        print("-" * 90)

        print(
            f"Average P&L at V     : "
            f"{events['pnl_at_v_pct'].mean():.4f}%"
        )

        print(
            f"Median P&L at V      : "
            f"{events['pnl_at_v_pct'].median():.4f}%"
        )

        print(
            f"Average prior peak   : "
            f"{events['favorable_peak_before_v_pct'].mean():.4f}%"
        )

        print(
            f"Median prior peak    : "
            f"{events['favorable_peak_before_v_pct'].median():.4f}%"
        )

        print()
        print("PULLBACK")
        print("-" * 90)

        print(
            f"Average initial pullback : "
            f"{events['initial_pullback_pct'].mean():.4f}%"
        )

        print(
            f"Median initial pullback  : "
            f"{events['initial_pullback_pct'].median():.4f}%"
        )

        print()
        print("RECOVERY")
        print("-" * 90)

        recovered = int(
            events[
                "recovered_previous_peak"
            ]
            .fillna(False)
            .sum()
        )

        print(
            f"Recovered previous peak : "
            f"{recovered}/{len(events)}"
        )

        rt = events[
            events[
                "recovered_previous_peak"
            ].eq(True)
            &
            events[
                "recovery_minutes"
            ].notna()
        ]["recovery_minutes"]

        if not rt.empty:

            print(
                f"Average recovery time  : "
                f"{rt.mean():.2f} minutes"
            )

            print(
                f"Median recovery time   : "
                f"{rt.median():.2f} minutes"
            )

        print()
        print("P&L AFTER V")
        print("-" * 90)

        for minutes in (
            5,
            10,
            15,
            30,
            60,
        ):

            col = (
                f"pnl_after_{minutes}m_pct"
            )

            if col not in events.columns:
                continue

            values = events[
                col
            ].dropna()

            if values.empty:
                continue

            print(
                f"{minutes:>2}m  "
                f"n={len(values):>3}  "
                f"avg={values.mean():>8.4f}%  "
                f"median={values.median():>8.4f}%"
            )

    print()
    print("IMPORTANT")
    print("-" * 90)
    print(
        "This experiment describes what happened."
    )
    print(
        "It does not tell AIMn to exit."
    )
    print(
        "It does not establish a V threshold."
    )

    print()
    print("OUTPUT")
    print("-" * 90)
    print(path_out)
    print(events_out)
    print(summary_out)
    print(metadata_out)

    print()
    print("=" * 90)
    print("EXPERIMENT #38 COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()

