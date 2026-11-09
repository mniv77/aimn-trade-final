
#!/usr/bin/env python3
"""
AIMn Experiment 53 — Classic SuperTrend Research
-------------------------------------------------
Research only. No trading, orders, or production changes.

Calculates:
    ATR using Wilder's smoothing
    Classic SuperTrend bands
    Trend state: LONG / SHORT
    Trend transitions

The current candle is evaluated using current and previous
completed candles. No future candles are used.
"""

from typing import Any, Dict, List, Sequence

import math
import pandas as pd


def calculate_supertrend(
    rows: Sequence[Dict[str, Any]],
    atr_period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """Calculate a causal, ATR-based SuperTrend."""

    if atr_period < 1:
        raise ValueError("atr_period must be at least 1")

    if multiplier <= 0:
        raise ValueError("multiplier must be positive")

    df = pd.DataFrame(rows).copy()

    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    if df.empty:
        return df

    df = df.sort_values("timestamp").reset_index(drop=True)

    for column in ("open", "high", "low", "close"):
        df[column] = pd.to_numeric(df[column], errors="raise")

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)

    n = len(df)

    true_ranges = [0.0] * n
    atr = [math.nan] * n

    upper_basic = [math.nan] * n
    lower_basic = [math.nan] * n

    upper_final = [math.nan] * n
    lower_final = [math.nan] * n

    supertrend = [math.nan] * n
    trend = ["UNKNOWN"] * n
    transition = [""] * n

    # True range
    for i in range(n):
        if i == 0:
            true_ranges[i] = highs[i] - lows[i]
        else:
            true_ranges[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

    # Wilder ATR initialization
    if n >= atr_period:
        atr[atr_period - 1] = (
            sum(true_ranges[:atr_period]) / atr_period
        )

        for i in range(atr_period, n):
            atr[i] = (
                atr[i - 1] * (atr_period - 1)
                + true_ranges[i]
            ) / atr_period

    first = atr_period - 1

    if n > first:
        for i in range(first, n):
            midpoint = (highs[i] + lows[i]) / 2.0

            upper_basic[i] = midpoint + multiplier * atr[i]
            lower_basic[i] = midpoint - multiplier * atr[i]

            if i == first:
                upper_final[i] = upper_basic[i]
                lower_final[i] = lower_basic[i]

                trend[i] = (
                    "LONG"
                    if closes[i] >= midpoint
                    else "SHORT"
                )

            else:
                upper_final[i] = (
                    upper_basic[i]
                    if (
                        upper_basic[i] < upper_final[i - 1]
                        or closes[i - 1] > upper_final[i - 1]
                    )
                    else upper_final[i - 1]
                )

                lower_final[i] = (
                    lower_basic[i]
                    if (
                        lower_basic[i] > lower_final[i - 1]
                        or closes[i - 1] < lower_final[i - 1]
                    )
                    else lower_final[i - 1]
                )

                if trend[i - 1] == "LONG":
                    trend[i] = (
                        "SHORT"
                        if closes[i] < lower_final[i - 1]
                        else "LONG"
                    )
                else:
                    trend[i] = (
                        "LONG"
                        if closes[i] > upper_final[i - 1]
                        else "SHORT"
                    )

                if trend[i] != trend[i - 1]:
                    transition[i] = (
                        f"{trend[i - 1]}->{trend[i]}"
                    )

            supertrend[i] = (
                lower_final[i]
                if trend[i] == "LONG"
                else upper_final[i]
            )

    df["atr"] = atr
    df["supertrend"] = supertrend
    df["st_trend"] = trend
    df["st_transition"] = transition

    return df


def summarize_supertrend(df: pd.DataFrame) -> None:
    """Print a compact research summary."""

    valid = df[df["st_trend"] != "UNKNOWN"]

    print("AIMn EXP53 — SUPERTREND")
    print("Candles:", len(df))
    print("Valid trend candles:", len(valid))

    for direction in ("LONG", "SHORT"):
        count = int((valid["st_trend"] == direction).sum())
        print(direction + " candles:", count)

    changes = df[df["st_transition"] != ""]

    print("Trend changes:", len(changes))

    print("\nFirst 10 transitions:")

    for _, row in changes.head(10).iterrows():
        print(
            row["timestamp"],
            row["st_transition"],
            "close=",
            round(float(row["close"]), 4),
            "supertrend=",
            round(float(row["supertrend"]), 4),
        )


if __name__ == "__main__":
    from kiss_backtest_routes import _db_rows, _row_dicts

    rows = _row_dicts(_db_rows("NVDA", "5m", "2"))

    result = calculate_supertrend(
        rows,
        atr_period=10,
        multiplier=3.0,
    )

    summarize_supertrend(result)
