#!/usr/bin/env python3

"""
AIMn KISS — Experiment #46 INDIVIDUAL TRADE CHARTS

Purpose
-------
Plot each of the five NOT-YET-PROFITABLE V trades from Experiment #46.

RESEARCH ONLY
-------------
No strategy changes.
No orders.
No AI training.
No threshold promotion.
No re-entry simulation.

Each chart shows:

    5-minute candles
    ENTRY
    V DETECTION
    EXIT CANDLE

Important:
-----------
Experiment #46 does NOT contain an exit_price column.

Therefore the chart uses:

    exit_time_utc
    and the CLOSE of the raw 5-minute candle at/nearest the exit time

This is explicitly labeled as:

    EXIT CANDLE CLOSE

It is NOT claimed to be the actual execution/fill price.

All displayed timestamps are UTC.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# =====================================================================
# FILES
# =====================================================================

RAW_PATH = (
    "kiss/results/exp32_raw_candle_v_geometry/"
    "raw_v_trajectory.csv"
)

EVENT_PATH = (
    "kiss/results/exp46_not_yet_profitable_v/"
    "nvda_not_yet_profitable_v_events.csv"
)

OUTPUT_DIR = (
    "kiss/results/exp46_not_yet_profitable_v/charts"
)


# =====================================================================
# SETTINGS
# =====================================================================

LOOKBACK_MINUTES = 30
LOOKAHEAD_MINUTES = 90


# =====================================================================
# HELPERS
# =====================================================================

def clean_timestamp(series):
    return pd.to_datetime(series, utc=True, errors="coerce")


def nearest_row(df, timestamp):
    """
    Return the raw trajectory row nearest to timestamp.
    """
    if df.empty:
        return None

    work = df.copy()

    work["_distance"] = (
        (work["candle_utc"] - timestamp)
        .abs()
        .dt.total_seconds()
    )

    row = work.sort_values("_distance").iloc[0]

    return row


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


# =====================================================================
# LOAD DATA
# =====================================================================

def load_data():

    print("=" * 100)
    print("AIMn KISS — EXPERIMENT #46 TRADE CHARTS")
    print("=" * 100)

    print()
    print("RAW SOURCE:")
    print(os.path.abspath(RAW_PATH))

    print("EVENT SOURCE:")
    print(os.path.abspath(EVENT_PATH))

    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            f"Raw trajectory file not found:\n{RAW_PATH}"
        )

    if not os.path.exists(EVENT_PATH):
        raise FileNotFoundError(
            f"Experiment #46 event file not found:\n{EVENT_PATH}"
        )

    raw = pd.read_csv(RAW_PATH)
    events = pd.read_csv(EVENT_PATH)

    print()
    print(f"Raw rows:    {len(raw):,}")
    print(f"Event rows:  {len(events):,}")

    print()
    print("Raw columns:")
    print(list(raw.columns))

    print()
    print("Event columns:")
    print(list(events.columns))

    # ---------------------------------------------------------------
    # Required raw columns
    # ---------------------------------------------------------------

    required_raw = [
        "case_id",
        "symbol",
        "direction",
        "transition_known_utc",
        "candle_utc",
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
        raise ValueError(
            "RAW TRAJECTORY is missing required columns:\n"
            + "\n".join(missing_raw)
        )

    # ---------------------------------------------------------------
    # Required event columns
    # ---------------------------------------------------------------

    required_events = [
        "case_id",
        "trade_id",
        "direction",
        "event_time_utc",
        "entry_time_utc",
        "entry_price",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
        "exit_time_utc",
    ]

    missing_events = [
        c for c in required_events
        if c not in events.columns
    ]

    if missing_events:
        raise ValueError(
            "Experiment #46 event file is missing required columns:\n"
            + "\n".join(missing_events)
        )

    # ---------------------------------------------------------------
    # Normalize timestamps
    # ---------------------------------------------------------------

    raw["transition_known_utc"] = clean_timestamp(
        raw["transition_known_utc"]
    )

    raw["candle_utc"] = clean_timestamp(
        raw["candle_utc"]
    )

    events["event_time_utc"] = clean_timestamp(
        events["event_time_utc"]
    )

    events["entry_time_utc"] = clean_timestamp(
        events["entry_time_utc"]
    )

    events["exit_time_utc"] = clean_timestamp(
        events["exit_time_utc"]
    )

    # ---------------------------------------------------------------
    # Numeric fields
    # ---------------------------------------------------------------

    for column in [
        "open",
        "high",
        "low",
        "close",
    ]:
        raw[column] = pd.to_numeric(
            raw[column],
            errors="coerce"
        )

    for column in [
        "entry_price",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
    ]:
        events[column] = pd.to_numeric(
            events[column],
            errors="coerce"
        )

    raw = raw.dropna(
        subset=[
            "case_id",
            "candle_utc",
            "close",
        ]
    ).copy()

    events = events.dropna(
        subset=[
            "case_id",
            "event_time_utc",
            "entry_time_utc",
        ]
    ).copy()

    return raw, events


# =====================================================================
# BUILD ONE CHART
# =====================================================================

def make_chart(raw, event):

    case_id = str(event["case_id"])
    trade_id = str(event["trade_id"])
    direction = str(event["direction"]).upper()

    event_time = event["event_time_utc"]
    entry_time = event["entry_time_utc"]
    exit_time = event["exit_time_utc"]

    entry_price = safe_float(event["entry_price"])
    pnl_at_v = safe_float(event["pnl_at_v_pct"])
    eventual_pnl = safe_float(
        event["eventual_pnl_hindsight_pct"]
    )

    # ---------------------------------------------------------------
    # Select raw trajectory
    # ---------------------------------------------------------------

    case_raw = raw[
        raw["case_id"].astype(str) == case_id
    ].copy()

    if case_raw.empty:
        print(
            f"WARNING: no raw trajectory for {case_id}"
        )
        return

    case_raw = case_raw.sort_values(
        "candle_utc"
    ).reset_index(drop=True)

    # ---------------------------------------------------------------
    # Determine chart window
    # ---------------------------------------------------------------

    start_time = entry_time - pd.Timedelta(
        minutes=LOOKBACK_MINUTES
    )

    end_time = event_time + pd.Timedelta(
        minutes=LOOKAHEAD_MINUTES
    )

    # Include exit if it extends beyond the normal window
    if pd.notna(exit_time):
        end_time = max(
            end_time,
            exit_time + pd.Timedelta(minutes=15)
        )

    chart = case_raw[
        (case_raw["candle_utc"] >= start_time)
        &
        (case_raw["candle_utc"] <= end_time)
    ].copy()

    if chart.empty:
        print(
            f"WARNING: no chart candles for {case_id}"
        )
        return

    # ---------------------------------------------------------------
    # Locate event candles
    # ---------------------------------------------------------------

    entry_row = nearest_row(
        case_raw,
        entry_time
    )

    v_row = nearest_row(
        case_raw,
        event_time
    )

    exit_row = None

    if pd.notna(exit_time):
        exit_row = nearest_row(
            case_raw,
            exit_time
        )

    # ---------------------------------------------------------------
    # Create figure
    # ---------------------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(15, 8)
    )

    # ---------------------------------------------------------------
    # Plot close
    # ---------------------------------------------------------------

    ax.plot(
        chart["candle_utc"],
        chart["close"],
        linewidth=1.8,
        label="5m Close"
    )

    # ---------------------------------------------------------------
    # Entry
    # ---------------------------------------------------------------

    if entry_row is not None:

        entry_chart_time = entry_row["candle_utc"]
        entry_chart_price = entry_row["close"]

        if entry_price is not None:
            entry_marker_price = entry_price
        else:
            entry_marker_price = entry_chart_price

        ax.scatter(
            entry_chart_time,
            entry_marker_price,
            s=90,
            marker="o",
            label="ENTRY"
        )

        ax.annotate(
            "ENTRY",
            (
                entry_chart_time,
                entry_marker_price
            ),
            xytext=(8, 12),
            textcoords="offset points",
            fontsize=10,
            fontweight="bold"
        )

    # ---------------------------------------------------------------
    # V DETECTION
    # ---------------------------------------------------------------

    if v_row is not None:

        v_chart_time = v_row["candle_utc"]
        v_chart_price = v_row["close"]

        ax.scatter(
            v_chart_time,
            v_chart_price,
            s=120,
            marker="^",
            label="V DETECTION"
        )

        ax.annotate(
            "V DETECTED",
            (
                v_chart_time,
                v_chart_price
            ),
            xytext=(8, -22),
            textcoords="offset points",
            fontsize=10,
            fontweight="bold"
        )

        # Vertical line showing exact causal decision point
        ax.axvline(
            v_chart_time,
            linestyle="--",
            linewidth=1.2,
            alpha=0.7
        )

    # ---------------------------------------------------------------
    # EXIT CANDLE
    # ---------------------------------------------------------------

    if exit_row is not None:

        exit_chart_time = exit_row["candle_utc"]
        exit_chart_price = exit_row["close"]

        ax.scatter(
            exit_chart_time,
            exit_chart_price,
            s=110,
            marker="X",
            label="EXIT CANDLE CLOSE"
        )

        ax.annotate(
            "EXIT CANDLE\nCLOSE",
            (
                exit_chart_time,
                exit_chart_price
            ),
            xytext=(8, 12),
            textcoords="offset points",
            fontsize=10,
            fontweight="bold"
        )

        ax.axvline(
            exit_chart_time,
            linestyle=":",
            linewidth=1.0,
            alpha=0.7
        )

    # ---------------------------------------------------------------
    # Title
    # ---------------------------------------------------------------

    pnl_text = (
        f"V P&L: {pnl_at_v:.4f}%"
        if pnl_at_v is not None
        else "V P&L: n/a"
    )

    stay_text = (
        f"STAY actual: {eventual_pnl:.4f}%"
        if eventual_pnl is not None
        else "STAY actual: n/a"
    )

    title = (
        f"Experiment #46 — {trade_id} — {direction}\n"
        f"{pnl_text}   |   {stay_text}"
    )

    ax.set_title(
        title,
        fontsize=14,
        fontweight="bold"
    )

    ax.set_xlabel(
        "UTC Time"
    )

    ax.set_ylabel(
        "Price"
    )

    ax.grid(
        True,
        alpha=0.25
    )

    # ---------------------------------------------------------------
    # UTC date formatting
    # ---------------------------------------------------------------

    ax.xaxis.set_major_formatter(
        mdates.DateFormatter(
            "%Y-%m-%d\n%H:%M UTC"
        )
    )

    fig.autofmt_xdate()

    ax.legend(
        loc="best"
    )

    # ---------------------------------------------------------------
    # Research note
    # ---------------------------------------------------------------

    fig.text(
        0.01,
        0.01,
        "RESEARCH ONLY — EXIT marker is the raw 5-minute "
        "candle close nearest exit_time_utc; "
        "it is NOT claimed to be the actual fill price.",
        fontsize=9
    )

    plt.tight_layout(
        rect=[0, 0.035, 1, 1]
    )

    # ---------------------------------------------------------------
    # Save
    # ---------------------------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{trade_id}_{direction}.png"
    )

    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close(fig)

    print(
        f"CREATED: {output_path}"
    )


# =====================================================================
# MAIN
# =====================================================================

def main():

    raw, events = load_data()

    print()
    print("=" * 100)
    print("BUILDING INDIVIDUAL TRADE CHARTS")
    print("=" * 100)

    print(
        f"Trades to chart: {len(events)}"
    )

    print()

    for _, event in events.iterrows():

        print(
            f"Charting "
            f"{event['trade_id']} "
            f"({event['direction']})..."
        )

        make_chart(
            raw,
            event
        )

    print()
    print("=" * 100)
    print("DONE")
    print("=" * 100)
    print()
    print(
        "Charts saved to:"
    )
    print(
        os.path.abspath(OUTPUT_DIR)
    )


if __name__ == "__main__":
    main()
