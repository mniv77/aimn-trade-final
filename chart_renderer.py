"""
chart_renderer.py
Generates candlestick + volume chart images from the AiMN candles table,
mimicking the TradingView-style charts used for manual review.

Standalone module - no dependency on the live trading engine.
Part of the AI Vision Confirmation initiative (see Doc 3).
"""

import pandas as pd
import mplfinance as mpf
from db import get_db_connection


def render_chart(symbol, timeframe, n_candles=50, outpath="/tmp/chart.png", title=None):
    """
    Render a candlestick + volume chart image for the given symbol/timeframe,
    using the last n_candles rows from the candles table.
    """
    conn, cur = get_db_connection()
    try:
        cur.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s AND timeframe=%s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (symbol, timeframe, n_candles),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    rows = rows[::-1]

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)

    chart_title = title or f"{symbol}  {timeframe}"

    mpf.plot(
        df,
        type="candle",
        volume=True,
        style="charles",
        title=chart_title,
        figsize=(10, 6),
        savefig=dict(fname=outpath, dpi=100, bbox_inches="tight"),
    )

    return outpath


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC/USD"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "5m"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    out = sys.argv[4] if len(sys.argv) > 4 else "/tmp/chart_test.png"

    result = render_chart(symbol, timeframe, n_candles=n, outpath=out)
    if result:
        print(f"Chart saved to {result}")
    else:
        print(f"No candle data found for {symbol} {timeframe}")
