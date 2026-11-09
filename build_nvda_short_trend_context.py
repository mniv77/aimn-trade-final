import pandas as pd
from db import get_db_connection

SUMMARY = "kiss/results/exp37_nvda_causal/nvda_causal_summary.csv"
OUTPUT = "kiss/results/exp37_nvda_causal/nvda_short_trend_context.csv"

summary = pd.read_csv(SUMMARY)
summary = summary[
    summary["direction"].astype(str).str.upper() == "SHORT"
].copy()
summary["transition_known_utc"] = pd.to_datetime(
    summary["transition_known_utc"], utc=True
)

result = get_db_connection()
conn, cur = result[0], result[1]

try:
    cur.execute("""
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        WHERE symbol = 'NVDA' AND timeframe = '5m'
        ORDER BY timestamp
    """)
    rows = cur.fetchall()

    candles = pd.DataFrame(rows)
    if candles.empty:
        raise RuntimeError("No NVDA 5m candles found.")

    # Database timestamps are New York local times stored without timezone.
    candles["timestamp"] = (
        pd.to_datetime(candles["timestamp"])
        .dt.tz_localize("America/New_York")
        .dt.tz_convert("UTC")
    )
    candles = candles.sort_values("timestamp").reset_index(drop=True)

    output = []
    for _, event in summary.iterrows():
        t = event["transition_known_utc"]
        prior = candles[candles["timestamp"] < t]
        at_or_before = candles[candles["timestamp"] <= t]

        row = {
            "case_id": event.get("case_id"),
            "transition_known_utc": t,
            "transition_price": None,
            "trend_30m_pct": None,
            "trend_60m_pct": None,
            "trend_120m_pct": None,
            "prior_candles_available": len(prior),
            "status": "OK",
        }

        if at_or_before.empty:
            row["status"] = "NO_CANDLE_AT_OR_BEFORE_TRANSITION"
            output.append(row)
            continue

        # Use the latest candle at or before the transition.
        transition_candle = at_or_before.iloc[-1]
        transition_price = float(transition_candle["close"])
        row["transition_price"] = transition_price

        for minutes in [30, 60, 120]:
            target = t - pd.Timedelta(minutes=minutes)
            earlier = prior[prior["timestamp"] <= target]

            if earlier.empty:
                continue

            start_price = float(earlier.iloc[-1]["close"])
            if start_price:
                row[f"trend_{minutes}m_pct"] = (
                    (transition_price / start_price) - 1
                ) * 100

        if all(row[f"trend_{m}m_pct"] is None for m in [30, 60, 120]):
            row["status"] = "INSUFFICIENT_PRIOR_HISTORY"

        output.append(row)

finally:
    cur.close()
    conn.close()

result_df = pd.DataFrame(output)
result_df.to_csv(OUTPUT, index=False)

print("=== NVDA SHORT PRE-TRANSITION TREND CONTEXT ===")
print("Transition cases:", len(result_df))
print("Output:", OUTPUT)
print("\nStatus counts:")
print(result_df["status"].value_counts(dropna=False).to_string())

for col in ["trend_30m_pct", "trend_60m_pct", "trend_120m_pct"]:
    values = pd.to_numeric(result_df[col], errors="coerce")
    print(f"\n{col}:")
    print("  Available:", int(values.notna().sum()))
    print("  Median:", round(values.median(), 4) if values.notna().any() else "N/A")
    print("  Positive:", int((values > 0).sum()))
    print("  Negative:", int((values < 0).sum()))

print("\nFirst 10 cases:")
print(result_df[
    ["case_id", "transition_known_utc",
     "trend_30m_pct", "trend_60m_pct", "trend_120m_pct", "status"]
].head(10).to_string(index=False))
