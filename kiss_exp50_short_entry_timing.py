#!/usr/bin/env python3
"""
AIMn KISS Experiment 50
SHORT Entry Timing vs Previous Peak

READ-ONLY RESEARCH
Does not modify the trading engine or database.
"""

import pandas as pd
from pathlib import Path
from db import get_db_connection

BASE = Path("kiss/results/exp37_nvda_causal")
SUMMARY = BASE / "nvda_causal_summary.csv"
OUTPUT = BASE / "nvda_exp50_short_entry_timing.csv"

LOOKBACKS = [30, 60, 120]

summary = pd.read_csv(SUMMARY)
summary = summary[
    summary["direction"].astype(str).str.upper() == "SHORT"
].copy()

summary["entry_time_utc"] = pd.to_datetime(
    summary["entry_time_utc"], utc=True
)

summary["transition_known_utc"] = pd.to_datetime(
    summary["transition_known_utc"], utc=True
)

summary["outcome"] = summary[
    "eventual_trade_winner_hindsight"
].map({True: "WINNER", False: "LOSER"})

result = get_db_connection()
conn, cur = result[0], result[1]

try:
    cur.execute("""
        SELECT timestamp, open, high, low, close
        FROM candles
        WHERE symbol = 'NVDA'
          AND timeframe = '5m'
        ORDER BY timestamp
    """)
    candles = pd.DataFrame(cur.fetchall())
finally:
    cur.close()
    conn.close()

if candles.empty:
    raise RuntimeError("No NVDA candles found.")

candles["timestamp"] = (
    pd.to_datetime(candles["timestamp"])
    .dt.tz_localize("America/New_York")
    .dt.tz_convert("UTC")
)

candles = candles.sort_values("timestamp")

for col in ["open", "high", "low", "close"]:
    candles[col] = pd.to_numeric(candles[col])

results = []

for _, trade in summary.iterrows():

    entry_time = trade["entry_time_utc"]
    transition_time = trade["transition_known_utc"]

    row = {
        "case_id": trade["case_id"],
        "trade_id": trade["trade_id"],
        "outcome": trade["outcome"],
        "eventual_pnl_pct": trade[
            "eventual_trade_pnl_pct_hindsight"
        ],
        "entry_time_utc": entry_time,
        "entry_price": trade["entry_price"],
        "entry_delay_minutes": None,
        "pre_entry_15m_change_pct": None,
        "pre_entry_30m_change_pct": None,
        "status": "OK",
    }

    if pd.isna(entry_time) or pd.isna(trade["entry_price"]):
        row["status"] = "NO_MATCHED_ENTRY"
        results.append(row)
        continue

    entry_price = float(trade["entry_price"])

    row["entry_delay_minutes"] = (
        entry_time - transition_time
    ).total_seconds() / 60

    # Exclude the candle beginning at entry time.
    # For a start-stamped 5m candle, it is not yet complete.
    completed = candles[
        candles["timestamp"] + pd.Timedelta(minutes=5)
        <= entry_time
    ]

    for minutes in LOOKBACKS:

        start = entry_time - pd.Timedelta(minutes=minutes)

        window = completed[
            (completed["timestamp"] >= start)
            & (completed["timestamp"] < entry_time)
        ]

        key = str(minutes) + "m"

        row["peak_" + key] = None
        row["entry_below_peak_" + key + "_pct"] = None
        row["bars_" + key] = len(window)

        if window.empty:
            continue

        peak = float(window["high"].max())

        row["peak_" + key] = peak

        row["entry_below_peak_" + key + "_pct"] = (
            (peak - entry_price) / peak * 100
        )

    for minutes in [15, 30]:

        start = entry_time - pd.Timedelta(minutes=minutes)

        window = completed[
            (completed["timestamp"] >= start)
            & (completed["timestamp"] < entry_time)
        ]

        if len(window) < 2:
            continue

        first_close = float(window.iloc[0]["close"])
        last_close = float(window.iloc[-1]["close"])

        if first_close:
            row[
                "pre_entry_" + str(minutes) + "m_change_pct"
            ] = (last_close / first_close - 1) * 100

    results.append(row)

df = pd.DataFrame(results)
df.to_csv(OUTPUT, index=False)

print()
print("=== AIMn EXPERIMENT 50 ===")
print("SHORT cases:", len(df))
print("Output:", OUTPUT)

print()
print("OUTCOMES")
print(df["outcome"].value_counts(dropna=False).to_string())

print()
print("ENTRY DISTANCE FROM PREVIOUS PEAK")
columns = [
    "entry_below_peak_30m_pct",
    "entry_below_peak_60m_pct",
    "entry_below_peak_120m_pct",
    "pre_entry_15m_change_pct",
    "pre_entry_30m_change_pct",
    "entry_delay_minutes",
]

print(
    df.groupby("outcome")[columns]
    .agg(["count", "median", "mean"])
    .round(4)
    .to_string()
)

print()
print("CASE DETAILS")
print(
    df[
        ["case_id", "outcome", "entry_delay_minutes"]
        + columns[:-1]
        + ["status"]
    ].to_string(index=False)
)