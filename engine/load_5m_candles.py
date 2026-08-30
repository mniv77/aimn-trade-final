"""Load 5-minute candles for the isolated KISS 30m/5m execution test.

This is deliberately separate from the existing 30m loader so the existing
broker/symbol/direction selection and 30m data path are not changed.

Yahoo Finance limits 5m history to a recent window, so use 60 days.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import yfinance as yf

from db import get_db_connection

STOCKS = ["SPY", "QQQ", "NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL"]


def load_symbol(cur, sym):
    print(f"\n=== Downloading {sym} 5m (60d) ===")
    df = yf.download(
        sym,
        period="60d",
        interval="5m",
        auto_adjust=False,
        progress=False,
    )
    if len(df) == 0:
        print(f"{sym}: no 5m data returned")
        return 0

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)
    count = 0
    for _, row in df.iterrows():
        dt = row["Datetime"] if "Datetime" in df.columns else row["Date"]
        ts = pd.to_datetime(dt).to_pydatetime()
        close = float(row["Close"])
        if close <= 0:
            continue

        cur.execute(
            """
            INSERT INTO candles
                (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES
                (%s, '5m', %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                open=VALUES(open), high=VALUES(high), low=VALUES(low),
                close=VALUES(close), volume=VALUES(volume)
            """,
            (
                sym,
                ts,
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                close,
                float(row["Volume"]),
            ),
        )
        count += 1

    print(f"{sym}: saved {count} 5m bars")
    return count


def main():
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")

    try:
        total = 0
        for sym in STOCKS:
            try:
                total += load_symbol(cur, sym)
                conn.commit()
                time.sleep(1)
            except Exception as exc:
                print(f"{sym}: FAILED: {exc}")

        print("\n=== VERIFY 5m DATA ===")
        cur.execute(
            """
            SELECT symbol, timeframe, COUNT(*) AS cnt,
                   MIN(timestamp) AS first_bar, MAX(timestamp) AS last_bar
            FROM candles
            WHERE symbol IN ('SPY','QQQ','NVDA','AAPL','TSLA','MSFT','AMZN','GOOGL')
              AND timeframe='5m'
            GROUP BY symbol, timeframe
            ORDER BY symbol
            """
        )
        for row in cur.fetchall():
            print(row)
        print(f"\nTOTAL 5m bars saved/updated: {total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
