import pandas as pd
from db import get_db_connection

summary_path = "kiss/results/exp37_nvda_causal/nvda_causal_summary.csv"
summary = pd.read_csv(summary_path)

summary["direction"] = summary["direction"].astype(str).str.upper()
shorts = summary[summary["direction"] == "SHORT"].copy()
shorts["transition_known_utc"] = pd.to_datetime(
    shorts["transition_known_utc"], utc=True
)

result = get_db_connection()
conn, cur = result[0], result[1]

try:
    cur.execute("""
        SELECT timestamp
        FROM candles
        WHERE symbol = 'NVDA' AND timeframe = '5m'
        ORDER BY timestamp
    """)
    timestamps = pd.to_datetime([row["timestamp"] for row in cur.fetchall()], utc=True)

    print("=== NVDA SHORT TRANSITION COVERAGE ===")
    print("SHORT transition cases:", len(shorts))
    print("Available 5m database candles:", len(timestamps))

    if len(timestamps) == 0:
        print("No 5m candles found.")
    else:
        print("First 5m candle:", timestamps.min())
        print("Last 5m candle:", timestamps.max())

        for lookback_minutes in [30, 60, 120]:
            covered = (
                (shorts["transition_known_utc"] - pd.Timedelta(minutes=lookback_minutes)
                 >= timestamps.min()) &
                (shorts["transition_known_utc"] <= timestamps.max())
            )
            print(
                f"Cases within database date range with "
                f"{lookback_minutes}-minute prior window: "
                f"{int(covered.sum())}/{len(shorts)}"
            )
finally:
    cur.close()
    conn.close()
