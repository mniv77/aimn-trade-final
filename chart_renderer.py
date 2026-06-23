"""
chart_renderer.py
Generates candlestick + volume chart images from live API or AiMN candles table.
"""

import pandas as pd
import mplfinance as mpf
from db import get_db_connection


def render_chart(symbol, timeframe, n_candles=50, outpath="/tmp/chart.png", title=None):
    rows = []

    if "/" in symbol:
        try:
            from engine.tuning.candle_fetcher import fetch_candles
            candles = fetch_candles(symbol, timeframe=timeframe, limit=n_candles, broker="Gemini")
            if candles:
                candles.sort(key=lambda x: x["timestamp"])
                rows = [{"timestamp": c["timestamp"], "open": c["open"],
                         "high": c["high"], "low": c["low"],
                         "close": c["close"], "volume": c["volume"]}
                        for c in candles[-n_candles:]]  # keep only last n_candles
                print(f"[chart_renderer] Live Gemini: {len(rows)} candles for {symbol}/{timeframe}")
        except Exception as e:
            print(f"[chart_renderer] Gemini failed: {e}")

    if not rows:
        conn, cur = get_db_connection()
        try:
            cur.execute(
                "SELECT timestamp, open, high, low, close, volume FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY timestamp DESC LIMIT %s",
                (symbol, timeframe, n_candles),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

    if not rows:
        try:
            from engine.tuning.candle_fetcher import fetch_candles
            candles = fetch_candles(symbol, timeframe=timeframe, limit=n_candles, broker="Alpaca")
            if candles:
                candles.sort(key=lambda x: x["timestamp"])
                rows = [{"timestamp": c["timestamp"], "open": c["open"],
                         "high": c["high"], "low": c["low"],
                         "close": c["close"], "volume": c["volume"]}
                        for c in candles[-n_candles:]]  # keep only last n_candles
        except Exception as e:
            return None

    if not rows:
        return None

    rows = rows[::-1]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    chart_title = title or f"{symbol}  {timeframe}"

    import os as _os
    if _os.path.exists(outpath):
        _os.remove(outpath)

    mpf.plot(df, type="candle", volume=True, style="charles", title=chart_title,
             figsize=(10, 6), savefig=dict(fname=outpath, dpi=100, bbox_inches="tight"))
    return outpath


if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC/USD"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "5m"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    out = sys.argv[4] if len(sys.argv) > 4 else "/tmp/chart_test.png"
    result = render_chart(symbol, timeframe, n_candles=n, outpath=out)
    print(f"Chart saved to {result}" if result else f"No data for {symbol} {timeframe}")
