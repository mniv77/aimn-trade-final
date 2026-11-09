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

IMPORTANT
---------
We do NOT create a trading rule here.

We simply observe what the REAL 5-minute price trajectory
does AFTER the causal V reversal.

DATA
----
Experiment #46 provides the causal V events.

Raw 5-minute trajectory provides the actual candles after
the V.

The causal V timestamp is:

    v_reversal_candle_utc

NOT:

    event_time_utc
"""


from pathlib import Path
import pandas as pd
import numpy as np


BASE = Path.home() / "aimn-trade-final"

RAW_PATH = (
    BASE
    / "kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv"
)

EVENT_PATH = (
    BASE
    / "kiss/results/exp46_not_yet_profitable_v/"
    / "nvda_not_yet_profitable_v_events.csv"
)

OUT_DIR = (
    BASE
    / "kiss/results/exp47_v_noise_vs_continuation"
)

OUT_EVENTS = OUT_DIR / "nvda_v_noise_vs_continuation_events.csv"
OUT_SUMMARY = OUT_DIR / "nvda_v_noise_vs_continuation_summary.csv"
OUT_META = OUT_DIR / "exp47_metadata.txt"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def pct_change_from_v(v_price, future_price, direction):
    """
    Trade-relative price change after the V.

    LONG:
        price rising  -> positive
        price falling -> negative

    SHORT:
        price falling  -> positive
        price rising   -> negative
    """

    if pd.isna(v_price) or pd.isna(future_price):
        return np.nan

    if v_price == 0:
        return np.nan

    raw = (future_price / v_price - 1.0) * 100.0

    if str(direction).upper() == "SHORT":
        raw = -raw

    return raw


def find_candle_at_or_after(group, target_time):
    """
    Find the first raw 5-minute candle at or after the causal V.

    Exact timestamp is preferred.
    If exact timestamp is absent, use the next available
    completed candle.

    This avoids silently using a candle from BEFORE the V.
    """

    g = group[group["candle_utc"] >= target_time].copy()

    if g.empty:
        return None

    return g.iloc[0]


def get_minutes_row(group, target_minutes):
    """
    Get the first available raw candle at or after the requested
    number of minutes after the V.
    """

    g = group[group["minutes_after_known"] >= target_minutes].copy()

    if g.empty:
        return None

    return g.iloc[0]


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():

    print("=" * 110)
    print("AIMn KISS — EXPERIMENT #47")
    print("UNPROFITABLE V: NOISE vs CONTINUING REVERSAL")
    print("=" * 110)

    print()
    print("Research only.")
    print("No production strategy changes.")
    print("No orders.")
    print("No AI.")
    print("No threshold promotion.")
    print("No re-entry simulation.")
    print()

    # ------------------------------------------------------------------
    # Load raw trajectory
    # ------------------------------------------------------------------

    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"RAW TRAJECTORY FILE NOT FOUND:\n{RAW_PATH}"
        )

    raw = pd.read_csv(RAW_PATH)

    print("=" * 110)
    print("RAW 5-MINUTE TRAJECTORY")
    print("-" * 110)
    print(f"File: {RAW_PATH}")
    print(f"Rows: {len(raw)}")
    print(f"Columns: {list(raw.columns)}")
    print()

    required_raw = [
        "case_id",
        "symbol",
        "direction",
        "transition_known_utc",
        "candle_utc",
        "minutes_after_known",
        "open",
        "high",
        "low",
        "close",
    ]

    missing_raw = [
        c for c in required_raw
        if c not in raw.columns
    ]

    if missing_raw:
        raise RuntimeError(
            "RAW TRAJECTORY is missing required columns:\n"
            + "\n".join(missing_raw)
        )

    # ------------------------------------------------------------------
    # Load #46 events
    # ------------------------------------------------------------------

    if not EVENT_PATH.exists():
        raise FileNotFoundError(
            f"EXPERIMENT #46 EVENT FILE NOT FOUND:\n{EVENT_PATH}"
        )

    events = pd.read_csv(EVENT_PATH)

    print("=" * 110)
    print("EXPERIMENT #46 UNPROFITABLE V EVENTS")
    print("-" * 110)
    print(f"File: {EVENT_PATH}")
    print(f"Rows: {len(events)}")
    print(f"Columns: {list(events.columns)}")
    print()

    required_events = [
        "case_id",
        "trade_id",
        "direction",
        "entry_time_utc",
        "entry_price",
        "transition_known_utc",
        "v_reversal_candle_utc",
        "v_peak_candle_utc",
        "pnl_at_v_pct",
        "exit_now_pnl_pct",
        "eventual_pnl_hindsight_pct",
    ]

    missing_events = [
        c for c in required_events
        if c not in events.columns
    ]

    if missing_events:
        raise RuntimeError(
            "EXPERIMENT #46 EVENTS are missing required columns:\n"
            + "\n".join(missing_events)
        )

    # ------------------------------------------------------------------
    # Parse timestamps
    # ------------------------------------------------------------------

    raw["candle_utc"] = pd.to_datetime(
        raw["candle_utc"],
        utc=True,
        errors="coerce",
    )

    raw["transition_known_utc"] = pd.to_datetime(
        raw["transition_known_utc"],
        utc=True,
        errors="coerce",
    )

    events["v_reversal_candle_utc"] = pd.to_datetime(
        events["v_reversal_candle_utc"],
        utc=True,
        errors="coerce",
    )

    events["v_peak_candle_utc"] = pd.to_datetime(
        events["v_peak_candle_utc"],
        utc=True,
        errors="coerce",
    )

    # ------------------------------------------------------------------
    # Clean numeric fields
    # ------------------------------------------------------------------

    for col in [
        "minutes_after_known",
        "open",
        "high",
        "low",
        "close",
    ]:
        raw[col] = pd.to_numeric(
            raw[col],
            errors="coerce",
        )

    # ------------------------------------------------------------------
    # Group raw trajectory by case
    # ------------------------------------------------------------------

    raw_groups = {
        case_id: group.sort_values("candle_utc").copy()
        for case_id, group in raw.groupby("case_id")
    }

    # ------------------------------------------------------------------
    # Analyze each unprofitable V
    # ------------------------------------------------------------------

    results = []

    print("=" * 110)
    print("CASE-BY-CASE ANALYSIS")
    print("=" * 110)

    for _, event in events.iterrows():

        case_id = event["case_id"]
        trade_id = event["trade_id"]
        direction = str(event["direction"]).upper()

        v_time = event["v_reversal_candle_utc"]

        if case_id not in raw_groups:
            print(
                f"{case_id} {trade_id}: "
                "RAW CASE MISSING"
            )
            continue

        group = raw_groups[case_id]

        # --------------------------------------------------------------
        # Find causal V candle
        # --------------------------------------------------------------

        v_rows = group[
            group["candle_utc"] == v_time
        ].copy()

        if v_rows.empty:
            # Never use a candle BEFORE the V.
            v_rows = group[
                group["candle_utc"] >= v_time
            ].copy()

        if v_rows.empty:
            print(
                f"{case_id} {trade_id}: "
                "NO RAW CANDLE AT/AFTER V"
            )
            continue

        v_row = v_rows.iloc[0]

        actual_v_time = v_row["candle_utc"]
        v_close = float(v_row["close"])

        # --------------------------------------------------------------
        # Future checkpoints
        # --------------------------------------------------------------

        checkpoint_data = {}

        for minutes in [5, 10, 15, 30, 60]:

            future = group[
                group["candle_utc"] > actual_v_time
            ].copy()

            if future.empty:
                checkpoint_data[
                    f"post_{minutes}m_trade_change_pct"
                ] = np.nan

                checkpoint_data[
                    f"post_{minutes}m_price"
                ] = np.nan

                checkpoint_data[
                    f"post_{minutes}m_candle_utc"
                ] = pd.NaT

                continue

            # Find first candle at least N minutes after V.
            target_time = (
                actual_v_time
                + pd.Timedelta(minutes=minutes)
            )

            candidate = future[
                future["candle_utc"] >= target_time
            ]

            if candidate.empty:
                checkpoint_data[
                    f"post_{minutes}m_trade_change_pct"
                ] = np.nan

                checkpoint_data[
                    f"post_{minutes}m_price"
                ] = np.nan

                checkpoint_data[
                    f"post_{minutes}m_candle_utc"
                ] = pd.NaT

                continue

            row = candidate.iloc[0]

            future_price = float(row["close"])

            trade_change = pct_change_from_v(
                v_close,
                future_price,
                direction,
            )

            checkpoint_data[
                f"post_{minutes}m_trade_change_pct"
            ] = trade_change

            checkpoint_data[
                f"post_{minutes}m_price"
            ] = future_price

            checkpoint_data[
                f"post_{minutes}m_candle_utc"
            ] = row["candle_utc"]

        # --------------------------------------------------------------
        # Full post-V path
        # --------------------------------------------------------------

        after = group[
            group["candle_utc"] > actual_v_time
        ].copy()

        post_changes = []

        for _, row in after.iterrows():

            change = pct_change_from_v(
                v_close,
                float(row["close"]),
                direction,
            )

            post_changes.append(change)

        post_changes = pd.Series(
            post_changes,
            dtype="float64",
        )

        # --------------------------------------------------------------
        # Descriptive behavior
        #
        # NO threshold.
        #
        # We simply look at whether the immediate path:
        #
        #   moves toward trade
        #   moves against trade
        #   or changes direction.
        # --------------------------------------------------------------

        first_5 = checkpoint_data[
            "post_5m_trade_change_pct"
        ]

        first_10 = checkpoint_data[
            "post_10m_trade_change_pct"
        ]

        first_15 = checkpoint_data[
            "post_15m_trade_change_pct"
        ]

        if pd.isna(first_5):
            immediate_behavior = "INSUFFICIENT"

        elif first_5 > 0:
            immediate_behavior = "TOWARD_TRADE"

        elif first_5 < 0:
            immediate_behavior = "AGAINST_TRADE"

        else:
            immediate_behavior = "FLAT"

        # --------------------------------------------------------------
        # Determine whether direction persists.
        #
        # Still descriptive — NOT a rule.
        # --------------------------------------------------------------

        available = [
            x for x in [
                first_5,
                first_10,
                first_15,
            ]
            if not pd.isna(x)
        ]

        if len(available) < 2:

            persistence = "INSUFFICIENT"

        else:

            positive_count = sum(
                x > 0 for x in available
            )

            negative_count = sum(
                x < 0 for x in available
            )

            if positive_count == len(available):

                persistence = "PERSISTENT_TOWARD_TRADE"

            elif negative_count == len(available):

                persistence = "PERSISTENT_AGAINST_TRADE"

            else:

                persistence = "MIXED"

        # --------------------------------------------------------------
        # Build result
        # --------------------------------------------------------------

        result = {
            "case_id": case_id,
            "trade_id": trade_id,
            "symbol": event.get("symbol", "NVDA"),
            "direction": direction,

            "transition_known_utc":
                event["transition_known_utc"],

            "v_peak_candle_utc":
                event["v_peak_candle_utc"],

            "v_reversal_candle_utc":
                v_time,

            "actual_raw_v_candle_utc":
                actual_v_time,

            "v_close":
                v_close,

            "pnl_at_v_pct":
                event["pnl_at_v_pct"],

            "exit_now_pnl_pct":
                event["exit_now_pnl_pct"],

            "eventual_stay_pnl_pct":
                event["eventual_pnl_hindsight_pct"],

            "stay_minus_exit_pct":
                event["eventual_pnl_hindsight_pct"]
                - event["exit_now_pnl_pct"],

            "immediate_behavior":
                immediate_behavior,

            "persistence":
                persistence,
        }

        result.update(checkpoint_data)

        # --------------------------------------------------------------
        # Post-V extremes
        # --------------------------------------------------------------

        if not post_changes.empty:

            result[
                "best_post_v_trade_change_pct"
            ] = post_changes.max()

            result[
                "worst_post_v_trade_change_pct"
            ] = post_changes.min()

        else:

            result[
                "best_post_v_trade_change_pct"
            ] = np.nan

            result[
                "worst_post_v_trade_change_pct"
            ] = np.nan

        results.append(result)

        # --------------------------------------------------------------
        # Print case
        # --------------------------------------------------------------

        print()
        print(
            f"{case_id}  {trade_id}  {direction}"
        )

        print(
            f"  V P&L:       "
            f"{event['pnl_at_v_pct']:.4f}%"
        )

        print(
            f"  EXIT NOW:    "
            f"{event['exit_now_pnl_pct']:.4f}%"
        )

        print(
            f"  STAY:        "
            f"{event['eventual_pnl_hindsight_pct']:.4f}%"
        )

        print(
            f"  STAY-EXIT:   "
            f"{event['eventual_pnl_hindsight_pct'] - event['exit_now_pnl_pct']:.4f}%"
        )

        print(
            f"  V close:     "
            f"{v_close:.4f}"
        )

        print(
            f"  +5m:         "
            f"{first_5:.4f}%"
            if not pd.isna(first_5)
            else "  +5m:         unavailable"
        )

        print(
            f"  +10m:        "
            f"{first_10:.4f}%"
            if not pd.isna(first_10)
            else "  +10m:        unavailable"
        )

        print(
            f"  +15m:        "
            f"{first_15:.4f}%"
            if not pd.isna(first_15)
            else "  +15m:        unavailable"
        )

        print(
            f"  +30m:        "
            f"{checkpoint_data['post_30m_trade_change_pct']:.4f}%"
            if not pd.isna(
                checkpoint_data["post_30m_trade_change_pct"]
            )
            else "  +30m:        unavailable"
        )

        print(
            f"  +60m:        "
            f"{checkpoint_data['post_60m_trade_change_pct']:.4f}%"
            if not pd.isna(
                checkpoint_data["post_60m_trade_change_pct"]
            )
            else "  +60m:        unavailable"
        )

        print(
            f"  Immediate:   {immediate_behavior}"
        )

        print(
            f"  Persistence: {persistence}"
        )

    # ------------------------------------------------------------------
    # Final dataframe
    # ------------------------------------------------------------------

    if not results:

        print()
        print("=" * 110)
        print("NO ANALYZABLE EVENTS")
        print("=" * 110)
        return

    result_df = pd.DataFrame(results)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUT_EVENTS,
        index=False,
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    print()
    print("=" * 110)
    print("EXPERIMENT #47 — SUMMARY")
    print("=" * 110)

    print(
        f"Unprofitable V events: "
        f"{len(result_df)}"
    )

    print(
        f"Unique trades: "
        f"{result_df['trade_id'].nunique()}"
    )

    print()

    print("IMMEDIATE BEHAVIOR")
    print("-" * 110)

    immediate_counts = (
        result_df["immediate_behavior"]
        .value_counts()
    )

    for name, count in immediate_counts.items():

        pct = (
            count
            / len(result_df)
            * 100.0
        )

        print(
            f"{name:<32}"
            f"{count:>5}"
            f" ({pct:>6.2f}%)"
        )

    print()
    print("POST-V PERSISTENCE")
    print("-" * 110)

    persistence_counts = (
        result_df["persistence"]
        .value_counts()
    )

    for name, count in persistence_counts.items():

        pct = (
            count
            / len(result_df)
            * 100.0
        )

        print(
            f"{name:<32}"
            f"{count:>5}"
            f" ({pct:>6.2f}%)"
        )

    print()
    print("CHECKPOINT AVERAGES")
    print("-" * 110)

    for minutes in [5, 10, 15, 30, 60]:

        col = (
            f"post_{minutes}m_trade_change_pct"
        )

        if col not in result_df.columns:
            continue

        values = result_df[col].dropna()

        if values.empty:
            print(
                f"+{minutes:>2}m: unavailable"
            )
        else:
            print(
                f"+{minutes:>2}m: "
                f"avg {values.mean():+.4f}%   "
                f"median {values.median():+.4f}%"
            )

    print()
    print("STAY vs EXIT")
    print("-" * 110)

    stay_exit = (
        result_df["stay_minus_exit_pct"]
    )

    print(
        f"Average STAY - EXIT: "
        f"{stay_exit.mean():+.4f}%"
    )

    print(
        f"Median STAY - EXIT:  "
        f"{stay_exit.median():+.4f}%"
    )

    print(
        f"STAY better:         "
        f"{(stay_exit > 0).sum()}"
    )

    print(
        f"EXIT better:         "
        f"{(stay_exit < 0).sum()}"
    )

    print(
        f"Same:                "
        f"{(stay_exit == 0).sum()}"
    )

    # ------------------------------------------------------------------
    # Behavior x decision
    # ------------------------------------------------------------------

    print()
    print("BEHAVIOR × STAY vs EXIT")
    print("-" * 110)

    for behavior, group in result_df.groupby(
        "immediate_behavior"
    ):

        diff = group[
            "stay_minus_exit_pct"
        ]

        print()
        print(
            f"[{behavior}]"
        )

        print(
            f"  Events:       {len(group)}"
        )

        print(
            f"  STAY better:  {(diff > 0).sum()}"
        )

        print(
            f"  EXIT better:  {(diff < 0).sum()}"
        )

        print(
            f"  Same:         {(diff == 0).sum()}"
        )

        print(
            f"  Avg STAY-EXIT:"
            f" {diff.mean():+.4f}%"
        )

    # ------------------------------------------------------------------
    # Save summary
    # ------------------------------------------------------------------

    summary_rows = []

    for behavior, group in result_df.groupby(
        "immediate_behavior"
    ):

        diff = group[
            "stay_minus_exit_pct"
        ]

        summary_rows.append({
            "behavior": behavior,
            "events": len(group),
            "unique_trades":
                group["trade_id"].nunique(),
            "stay_better":
                int((diff > 0).sum()),
            "exit_better":
                int((diff < 0).sum()),
            "same":
                int((diff == 0).sum()),
            "avg_stay_minus_exit_pct":
                diff.mean(),
            "median_stay_minus_exit_pct":
                diff.median(),
            "avg_v_pnl_pct":
                group["pnl_at_v_pct"].mean(),
            "avg_stay_pnl_pct":
                group["eventual_stay_pnl_pct"].mean(),
            "avg_post_5m_trade_change_pct":
                group[
                    "post_5m_trade_change_pct"
                ].mean(),
            "avg_post_10m_trade_change_pct":
                group[
                    "post_10m_trade_change_pct"
                ].mean(),
            "avg_post_15m_trade_change_pct":
                group[
                    "post_15m_trade_change_pct"
                ].mean(),
            "avg_post_30m_trade_change_pct":
                group[
                    "post_30m_trade_change_pct"
                ].mean(),
            "avg_post_60m_trade_change_pct":
                group[
                    "post_60m_trade_change_pct"
                ].mean(),
        })

    summary_df = pd.DataFrame(
        summary_rows
    )

    summary_df.to_csv(
        OUT_SUMMARY,
        index=False,
    )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    with open(
        OUT_META,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "AIMn KISS Experiment #47\n"
        )

        f.write(
            "UNPROFITABLE V: "
            "NOISE vs CONTINUING REVERSAL\n\n"
        )

        f.write(
            "Research only.\n"
        )

        f.write(
            "No production changes.\n"
        )

        f.write(
            "No orders.\n"
        )

        f.write(
            "No AI training.\n"
        )

        f.write(
            "No threshold promotion.\n"
        )

        f.write(
            "No re-entry simulation.\n\n"
        )

        f.write(
            f"Raw trajectory: {RAW_PATH}\n"
        )

        f.write(
            f"Experiment #46 events: {EVENT_PATH}\n"
        )

        f.write(
            f"Events analyzed: {len(result_df)}\n"
        )

        f.write(
            "\nCausal V timestamp used:\n"
        )

        f.write(
            "v_reversal_candle_utc\n"
        )

        f.write(
            "\nPost-V observations use the first completed "
            "raw 5-minute candle at or after each checkpoint.\n"
        )

    print()
    print("=" * 110)
    print("OUTPUTS")
    print("=" * 110)

    print(
        f"Events : {OUT_EVENTS}"
    )

    print(
        f"Summary: {OUT_SUMMARY}"
    )

    print(
        f"Meta   : {OUT_META}"
    )

    print("=" * 110)


if __name__ == "__main__":
    main()
