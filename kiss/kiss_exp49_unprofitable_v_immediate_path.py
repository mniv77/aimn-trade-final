#!/usr/bin/env python3

"""
AIMn KISS — Experiment #49
UNPROFITABLE V: IMMEDIATE PRICE PATH

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

We inspect the REAL raw 5-minute trajectory immediately after
the causal V reversal candle.

SOURCE
------
RAW 5-MINUTE TRAJECTORY:
    kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv

EXPERIMENT #46 EVENTS:
    kiss/results/exp46_not_yet_profitable_v/
        nvda_not_yet_profitable_v_events.csv

IMPORTANT
---------
Experiment #46 uses:

    v_reversal_candle_utc

as the exact causal V candle.

Experiment #49 MUST use that field.

For every qualifying V we inspect:

    V
    +5m
    +10m
    +15m
    +30m
    +60m

We calculate actual trade P&L from the raw close price and
the real entry price.

No decision rule is created.
"""

from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# PATHS
# ============================================================

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
    / "kiss/results/exp49_unprofitable_v_immediate_path"
)

OUT_EVENTS = OUT_DIR / "nvda_unprofitable_v_immediate_path_events.csv"
OUT_SUMMARY = OUT_DIR / "nvda_unprofitable_v_immediate_path_summary.csv"
OUT_METADATA = OUT_DIR / "exp49_metadata.txt"


# ============================================================
# HELPERS
# ============================================================

def money_pnl_pct(entry_price, close_price, direction):
    """
    Trade P&L based only on entry price and current close.

    LONG:
        (close / entry - 1) * 100

    SHORT:
        (entry / close - 1) * 100
    """

    if pd.isna(entry_price) or pd.isna(close_price):
        return np.nan

    if entry_price == 0 or close_price == 0:
        return np.nan

    direction = str(direction).upper().strip()

    if direction == "LONG":
        return ((close_price / entry_price) - 1.0) * 100.0

    if direction == "SHORT":
        return ((entry_price / close_price) - 1.0) * 100.0

    return np.nan


def fmt(value):
    if pd.isna(value):
        return "--"
    return f"{float(value):.4f}%"


def required_columns(df, required, name):
    missing = [c for c in required if c not in df.columns]

    if missing:
        print("=" * 120)
        print("ERROR")
        print("=" * 120)
        print(f"{name} is missing required columns:")
        print(missing)
        print("Actual columns:")
        print(list(df.columns))
        raise SystemExit(1)


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("=" * 120)
    print("AIMn KISS — EXPERIMENT #49")
    print("UNPROFITABLE V: IMMEDIATE PRICE PATH")
    print("=" * 120)

    print()
    print("=" * 120)
    print("RAW 5-MINUTE TRAJECTORY")
    print("=" * 120)

    if not RAW_PATH.exists():
        print("ERROR: Raw trajectory file does not exist:")
        print(RAW_PATH)
        raise SystemExit(1)

    raw = pd.read_csv(RAW_PATH)

    print(f"Selected: {RAW_PATH}")
    print(f"Rows:     {len(raw):,}")
    print(f"Columns:  {list(raw.columns)}")

    required_columns(
        raw,
        [
            "case_id",
            "symbol",
            "direction",
            "candle_utc",
            "minutes_after_known",
            "open",
            "high",
            "low",
            "close",
        ],
        "RAW TRAJECTORY",
    )

    print()
    print("=" * 120)
    print("EXPERIMENT #46 EVENTS")
    print("=" * 120)

    if not EVENT_PATH.exists():
        print("ERROR: Experiment #46 event file does not exist:")
        print(EVENT_PATH)
        raise SystemExit(1)

    events = pd.read_csv(EVENT_PATH)

    print(f"Selected: {EVENT_PATH}")
    print(f"Rows:     {len(events):,}")
    print(f"Columns:  {list(events.columns)}")

    required_columns(
        events,
        [
            "case_id",
            "symbol",
            "direction",
            "trade_id",
            "entry_time_utc",
            "entry_price",
            "v_reversal_candle_utc",
            "pnl_at_v_pct",
            "eventual_pnl_hindsight_pct",
            "exit_now_pnl_pct",
            "stay_actual_pnl_pct",
            "stay_minus_exit_pct",
        ],
        "EXPERIMENT #46 EVENT FILE",
    )

    # --------------------------------------------------------
    # Normalize timestamps
    # --------------------------------------------------------

    raw["candle_utc"] = pd.to_datetime(
        raw["candle_utc"],
        utc=True,
        errors="coerce",
    )

    events["v_reversal_candle_utc"] = pd.to_datetime(
        events["v_reversal_candle_utc"],
        utc=True,
        errors="coerce",
    )

    events["entry_time_utc"] = pd.to_datetime(
        events["entry_time_utc"],
        utc=True,
        errors="coerce",
    )

    raw = raw.dropna(subset=["candle_utc"]).copy()
    events = events.dropna(
        subset=["v_reversal_candle_utc"]
    ).copy()

    # Make numeric fields numeric
    for col in [
        "open",
        "high",
        "low",
        "close",
        "entry_price",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
        "exit_now_pnl_pct",
        "stay_actual_pnl_pct",
        "stay_minus_exit_pct",
    ]:
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")

        if col in events.columns:
            events[col] = pd.to_numeric(events[col], errors="coerce")

    raw = raw.sort_values(
        ["case_id", "candle_utc"]
    ).reset_index(drop=True)

    events = events.sort_values(
        ["case_id", "v_reversal_candle_utc"]
    ).reset_index(drop=True)

    return raw, events


# ============================================================
# CLASSIFY IMMEDIATE PATH
# ============================================================

def immediate_path_label(d5, d10, d15):

    """
    Descriptive only.

    No percentage threshold is used.

    CONTINUING_REVERSAL:
        First three observed post-V P&L changes are all negative.

    IMMEDIATE_RECOVERY:
        First post-V P&L change is positive.

    TURNED_AFTER_INITIAL_WEAKNESS:
        First change negative, but a later checkpoint improves.

    MIXED:
        Everything else.

    INSUFFICIENT:
        Not enough observations.
    """

    vals = [d5, d10, d15]

    available = [x for x in vals if not pd.isna(x)]

    if len(available) == 0:
        return "INSUFFICIENT"

    if d5 is not None and not pd.isna(d5):

        if d5 > 0:
            return "IMMEDIATE_RECOVERY"

        if d5 < 0:
            later = [
                x for x in [d10, d15]
                if not pd.isna(x)
            ]

            if len(later) >= 2 and all(x < 0 for x in later):
                return "CONTINUING_REVERSAL"

            if any(x > 0 for x in later):
                return "TURNED_AFTER_INITIAL_WEAKNESS"

    return "MIXED"


# ============================================================
# BUILD EVENT PATH
# ============================================================

def build_event_rows(raw, events):

    output = []

    print()
    print("=" * 120)
    print("BUILDING REAL 5-MINUTE POST-V PATHS")
    print("=" * 120)

    print(
        "V timestamp source: v_reversal_candle_utc"
    )
    print(
        "Post-V source:      raw candle_utc"
    )

    for _, ev in events.iterrows():

        case_id = str(ev["case_id"])
        direction = str(ev["direction"]).upper().strip()
        trade_id = ev["trade_id"]

        v_time = ev["v_reversal_candle_utc"]

        entry_price = ev["entry_price"]

        if pd.isna(v_time):
            continue

        case_raw = raw[
            raw["case_id"].astype(str) == case_id
        ].copy()

        if case_raw.empty:
            print(
                f"WARNING: no raw rows for {case_id}"
            )
            continue

        # ----------------------------------------------------
        # Find the exact V candle.
        # ----------------------------------------------------

        exact = case_raw[
            case_raw["candle_utc"] == v_time
        ].copy()

        if exact.empty:
            print()
            print("WARNING: exact V candle not found")
            print(f"Case: {case_id}")
            print(f"V:    {v_time}")
            print("Available raw time range:")
            print(
                case_raw["candle_utc"].min(),
                "to",
                case_raw["candle_utc"].max(),
            )
            continue

        # ----------------------------------------------------
        # Build 0,5,10,15,30,60 minute checkpoints.
        # ----------------------------------------------------

        checkpoints = {}

        for minutes in [0, 5, 10, 15, 30, 60]:

            target = v_time + pd.Timedelta(
                minutes=minutes
            )

            row = case_raw[
                case_raw["candle_utc"] == target
            ]

            if row.empty:
                checkpoints[minutes] = None
            else:
                checkpoints[minutes] = row.iloc[0]

        # ----------------------------------------------------
        # Actual P&L path.
        # ----------------------------------------------------

        pnls = {}

        closes = {}

        for minutes, row in checkpoints.items():

            if row is None:
                pnls[minutes] = np.nan
                closes[minutes] = np.nan
                continue

            close_price = row["close"]

            closes[minutes] = close_price

            pnls[minutes] = money_pnl_pct(
                entry_price,
                close_price,
                direction,
            )

        # ----------------------------------------------------
        # P&L changes FROM V
        # ----------------------------------------------------

        pnl_v = pnls.get(0, np.nan)

        d5 = (
            pnls[5] - pnl_v
            if not pd.isna(pnls.get(5))
            and not pd.isna(pnl_v)
            else np.nan
        )

        d10 = (
            pnls[10] - pnl_v
            if not pd.isna(pnls.get(10))
            and not pd.isna(pnl_v)
            else np.nan
        )

        d15 = (
            pnls[15] - pnl_v
            if not pd.isna(pnls.get(15))
            and not pd.isna(pnl_v)
            else np.nan
        )

        d30 = (
            pnls[30] - pnl_v
            if not pd.isna(pnls.get(30))
            and not pd.isna(pnl_v)
            else np.nan
        )

        d60 = (
            pnls[60] - pnl_v
            if not pd.isna(pnls.get(60))
            and not pd.isna(pnl_v)
            else np.nan
        )

        path_label = immediate_path_label(
            d5,
            d10,
            d15,
        )

        # ----------------------------------------------------
        # Direction of P&L movement after V
        # ----------------------------------------------------

        changes = [
            x
            for x in [d5, d10, d15, d30, d60]
            if not pd.isna(x)
        ]

        worsening = sum(x < 0 for x in changes)
        improving = sum(x > 0 for x in changes)

        # ----------------------------------------------------
        # Actual STAY versus EXIT
        # ----------------------------------------------------

        exit_now = ev["exit_now_pnl_pct"]

        stay_actual = ev["stay_actual_pnl_pct"]

        stay_minus_exit = ev["stay_minus_exit_pct"]

        # ----------------------------------------------------
        # Cross-check P&L at V
        # ----------------------------------------------------

        pnl_difference = (
            pnl_v - ev["pnl_at_v_pct"]
            if not pd.isna(pnl_v)
            and not pd.isna(ev["pnl_at_v_pct"])
            else np.nan
        )

        output.append(
            {
                "case_id": case_id,
                "trade_id": trade_id,
                "symbol": ev["symbol"],
                "direction": direction,
                "entry_time_utc": ev["entry_time_utc"],
                "entry_price": entry_price,
                "v_reversal_candle_utc": v_time,

                "pnl_at_v_pct": pnl_v,

                "pnl_after_5m_pct": pnls[5],
                "pnl_after_10m_pct": pnls[10],
                "pnl_after_15m_pct": pnls[15],
                "pnl_after_30m_pct": pnls[30],
                "pnl_after_60m_pct": pnls[60],

                "change_from_v_after_5m_pct": d5,
                "change_from_v_after_10m_pct": d10,
                "change_from_v_after_15m_pct": d15,
                "change_from_v_after_30m_pct": d30,
                "change_from_v_after_60m_pct": d60,

                "close_at_v": closes[0],
                "close_after_5m": closes[5],
                "close_after_10m": closes[10],
                "close_after_15m": closes[15],
                "close_after_30m": closes[30],
                "close_after_60m": closes[60],

                "post_v_worsening_checkpoints": worsening,
                "post_v_improving_checkpoints": improving,

                "immediate_path": path_label,

                "exit_now_pnl_pct": exit_now,
                "stay_actual_pnl_pct": stay_actual,
                "stay_minus_exit_pct": stay_minus_exit,

                "stay_vs_exit": ev["stay_vs_exit"],

                "eventual_pnl_hindsight_pct":
                    ev["eventual_pnl_hindsight_pct"],

                "pnl_crosscheck_difference_pct":
                    pnl_difference,
            }
        )

    return pd.DataFrame(output)


# ============================================================
# PRINT RESULTS
# ============================================================

def print_results(df):

    print()
    print("=" * 120)
    print("EXPERIMENT #49 — CORE RESULT")
    print("=" * 120)

    if df.empty:
        print("NO EVENTS PRODUCED")
        return

    print(
        f"Events analyzed: {len(df)}"
    )

    print(
        f"Unique trades:   {df['trade_id'].nunique()}"
    )

    print()

    print(
        "IMMEDIATE PATH CLASSIFICATION"
    )

    print(
        df["immediate_path"]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "CASE-BY-CASE REAL POST-V PATH"
    )
    print("-" * 120)

    show_cols = [
        "case_id",
        "trade_id",
        "direction",
        "v_reversal_candle_utc",
        "pnl_at_v_pct",
        "pnl_after_5m_pct",
        "pnl_after_10m_pct",
        "pnl_after_15m_pct",
        "pnl_after_30m_pct",
        "pnl_after_60m_pct",
        "change_from_v_after_5m_pct",
        "change_from_v_after_10m_pct",
        "change_from_v_after_15m_pct",
        "change_from_v_after_30m_pct",
        "change_from_v_after_60m_pct",
        "immediate_path",
        "exit_now_pnl_pct",
        "stay_actual_pnl_pct",
        "stay_minus_exit_pct",
    ]

    show_cols = [
        c for c in show_cols
        if c in df.columns
    ]

    print(
        df[show_cols].to_string(
            index=False
        )
    )

    print()
    print("=" * 120)
    print("STAY vs EXIT")
    print("=" * 120)

    better_stay = (
        df["stay_minus_exit_pct"] > 0
    ).sum()

    better_exit = (
        df["stay_minus_exit_pct"] < 0
    ).sum()

    same = (
        df["stay_minus_exit_pct"] == 0
    ).sum()

    print(
        f"STAY better : {better_stay}"
    )
    print(
        f"EXIT better : {better_exit}"
    )
    print(
        f"Same        : {same}"
    )

    print(
        f"Average STAY - EXIT: "
        f"{df['stay_minus_exit_pct'].mean():.4f}%"
    )

    print(
        f"Median STAY - EXIT : "
        f"{df['stay_minus_exit_pct'].median():.4f}%"
    )

    print()
    print("=" * 120)
    print("PATH × STAY vs EXIT")
    print("=" * 120)

    grouped = (
        df.groupby("immediate_path")
        .agg(
            events=("trade_id", "count"),
            stay_better=(
                "stay_minus_exit_pct",
                lambda s: int((s > 0).sum()),
            ),
            exit_better=(
                "stay_minus_exit_pct",
                lambda s: int((s < 0).sum()),
            ),
            same=(
                "stay_minus_exit_pct",
                lambda s: int((s == 0).sum()),
            ),
            avg_stay_minus_exit=(
                "stay_minus_exit_pct",
                "mean",
            ),
            median_stay_minus_exit=(
                "stay_minus_exit_pct",
                "median",
            ),
        )
        .sort_values(
            "events",
            ascending=False,
        )
    )

    print(
        grouped.to_string()
    )

    print()
    print("=" * 120)
    print("DIRECTION × STAY vs EXIT")
    print("=" * 120)

    direction_summary = (
        df.groupby("direction")
        .agg(
            events=("trade_id", "count"),
            stay_better=(
                "stay_minus_exit_pct",
                lambda s: int((s > 0).sum()),
            ),
            exit_better=(
                "stay_minus_exit_pct",
                lambda s: int((s < 0).sum()),
            ),
            avg_stay_minus_exit=(
                "stay_minus_exit_pct",
                "mean",
            ),
            median_stay_minus_exit=(
                "stay_minus_exit_pct",
                "median",
            ),
        )
    )

    print(
        direction_summary.to_string()
    )

    print()
    print("=" * 120)
    print("IMPORTANT OBSERVATION")
    print("=" * 120)

    print(
        "The path label is descriptive research only."
    )

    print(
        "No percentage threshold was selected."
    )

    print(
        "No trading rule was created."
    )

    print(
        "The purpose is to see whether the first few "
        "5-minute candles after an unprofitable V "
        "look different when STAY eventually beats "
        "EXIT versus when EXIT eventually beats STAY."
    )


# ============================================================
# WRITE FILES
# ============================================================

def write_outputs(df):

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUT_EVENTS,
        index=False,
    )

    summary_rows = []

    for label, g in df.groupby(
        "immediate_path",
        dropna=False,
    ):

        summary_rows.append(
            {
                "immediate_path": label,
                "events": len(g),
                "unique_trades": g["trade_id"].nunique(),

                "stay_better": int(
                    (g["stay_minus_exit_pct"] > 0).sum()
                ),

                "exit_better": int(
                    (g["stay_minus_exit_pct"] < 0).sum()
                ),

                "same": int(
                    (g["stay_minus_exit_pct"] == 0).sum()
                ),

                "avg_stay_minus_exit_pct":
                    g["stay_minus_exit_pct"].mean(),

                "median_stay_minus_exit_pct":
                    g["stay_minus_exit_pct"].median(),

                "avg_pnl_at_v_pct":
                    g["pnl_at_v_pct"].mean(),

                "median_pnl_at_v_pct":
                    g["pnl_at_v_pct"].median(),

                "avg_change_after_5m_pct":
                    g["change_from_v_after_5m_pct"].mean(),

                "avg_change_after_10m_pct":
                    g["change_from_v_after_10m_pct"].mean(),

                "avg_change_after_15m_pct":
                    g["change_from_v_after_15m_pct"].mean(),

                "avg_change_after_30m_pct":
                    g["change_from_v_after_30m_pct"].mean(),

                "avg_change_after_60m_pct":
                    g["change_from_v_after_60m_pct"].mean(),
            }
        )

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        OUT_SUMMARY,
        index=False,
    )

    metadata = []

    metadata.append(
        "AIMn KISS — Experiment #49\n"
    )

    metadata.append(
        "QUESTION: At an unprofitable V, is price noise "
        "or a continuing reversal?\n"
    )

    metadata.append(
        "RESEARCH ONLY — no production changes, no orders, "
        "no AI, no thresholds, no re-entry simulation.\n"
    )

    metadata.append(
        f"Raw source: {RAW_PATH}\n"
    )

    metadata.append(
        f"Event source: {EVENT_PATH}\n"
    )

    metadata.append(
        "Causal V timestamp field: v_reversal_candle_utc\n"
    )

    metadata.append(
        "Raw price timestamp field: candle_utc\n"
    )

    metadata.append(
        f"Events analyzed: {len(df)}\n"
    )

    metadata.append(
        f"Unique trades: {df['trade_id'].nunique()}\n"
    )

    metadata.append(
        "No threshold promoted.\n"
    )

    metadata.append(
        "No trading rule created.\n"
    )

    OUT_METADATA.write_text(
        "".join(metadata),
        encoding="utf-8",
    )

    print()
    print("=" * 120)
    print("FILES WRITTEN")
    print("=" * 120)

    print(OUT_EVENTS)
    print(OUT_SUMMARY)
    print(OUT_METADATA)


# ============================================================
# MAIN
# ============================================================

def main():

    raw, events = load_data()

    df = build_event_rows(
        raw,
        events,
    )

    if df.empty:
        print()
        print("=" * 120)
        print("ERROR")
        print("=" * 120)
        print(
            "No qualifying event could be matched "
            "to the raw 5-minute trajectory."
        )
        print(
            "This means the exact V timestamps did not "
            "match raw candle timestamps."
        )
        raise SystemExit(1)

    print_results(df)

    write_outputs(df)

    print()
    print("=" * 120)
    print("EXPERIMENT #49 COMPLETE")
    print("=" * 120)

    print(
        "Research only. No rule was created."
    )


if __name__ == "__main__":
    main()
