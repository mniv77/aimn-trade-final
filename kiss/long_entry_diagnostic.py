from engine.kiss_execution_5m import (
    run_kiss_30m_5m,
    get_market_state,
    rsi_wilder,
    TREND_WINDOW,
    TREND_BAND,
)

from db import get_db_connection


SYMBOL = "NVDA"
LIMIT_30M = 5000
LIMIT_5M = 5000


def load_rows(symbol, timeframe, limit):
    conn, cursor = get_db_connection()

    if not conn:
        raise RuntimeError("Database connection failed")

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s AND timeframe=%s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (symbol, timeframe, limit),
        )

        rows = cursor.fetchall()

        result = []

        for r in rows:
            if isinstance(r, dict):
                result.append({
                    "timestamp": r.get("timestamp"),
                    "open": float(r.get("open")),
                    "high": float(r.get("high")),
                    "low": float(r.get("low")),
                    "close": float(r.get("close")),
                })
            else:
                result.append({
                    "timestamp": r[0],
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                })

        return result

    finally:
        conn.close()


def pct(a, b):
    if b == 0:
        return 0.0
    return (a / b - 1.0) * 100.0


def main():

    trend_rows = load_rows(SYMBOL, "30m", LIMIT_30M)
    execution_rows = load_rows(SYMBOL, "5m", LIMIT_5M)

    print()
    print("=" * 110)
    print("KISS LONG ENTRY DIAGNOSTIC")
    print("=" * 110)
    print(f"Symbol       : {SYMBOL}")
    print(f"30m candles  : {len(trend_rows)}")
    print(f"5m candles   : {len(execution_rows)}")
    print(f"TREND_WINDOW : {TREND_WINDOW}")
    print(f"TREND_BAND   : {TREND_BAND * 100:.3f}%")
    print("=" * 110)

    # Run the exact current KISS backtest.
    result = run_kiss_30m_5m(
        trend_rows,
        execution_rows,
        SYMBOL,
        "LONG",
    )

    trades = result.get("trades", [])

    closes_30 = [r["close"] for r in trend_rows]
    states = [
        get_market_state(closes_30, i)
        for i in range(len(closes_30))
    ]

    closes_5 = [r["close"] for r in execution_rows]
    rsis = rsi_wilder(closes_5)

    print()
    print(f"TOTAL LONG TRADES: {len(trades)}")
    print()

    for n, trade in enumerate(trades, 1):

        entry_time = trade["entry_time"]

        # Find exact 5m entry candle.
        entry_i = None

        for i, row in enumerate(execution_rows):
            if str(row["timestamp"]) == entry_time:
                entry_i = i
                break

        if entry_i is None:
            continue

        entry_price = execution_rows[entry_i]["close"]

        # Find nearest 30m candle at or immediately before entry.
        trend_i = None

        for i, row in enumerate(trend_rows):
            if row["timestamp"] <= execution_rows[entry_i]["timestamp"]:
                trend_i = i
            else:
                break

        print()
        print("=" * 110)
        print(
            f"LONG TRADE #{n}   "
            f"{trade['trade_id']}   "
            f"P&L {trade['pnl_pct']:+.3f}%"
        )
        print("=" * 110)

        print(f"Entry time       : {trade['entry_time']}")
        print(f"Entry price      : {trade['entry_price']:.4f}")
        print(f"Entry transition : {trade['entry_transition']}")
        print(f"Shape            : {trade.get('transition_shape')}")
        print(f"Entry RSI        : {trade.get('entry_rsi')}")
        print(f"Exit reason      : {trade['exit_reason']}")
        print()

        if trend_i is not None:

            print("30M CONTEXT")
            print("-" * 110)

            start = max(TREND_WINDOW, trend_i - 5)
            end = min(len(trend_rows), trend_i + 2)

            print(
                f"{'IDX':>6} "
                f"{'TIME':>22} "
                f"{'CLOSE':>11} "
                f"{'MA20':>11} "
                f"{'DIST%':>9} "
                f"{'STATE':>8}"
            )

            for j in range(start, end):

                if j >= TREND_WINDOW:
                    ma = sum(
                        closes_30[j - TREND_WINDOW:j]
                    ) / TREND_WINDOW

                    dist = pct(closes_30[j], ma)
                else:
                    ma = float("nan")
                    dist = float("nan")

                marker = ""

                if j == trend_i:
                    marker = "  <-- ENTRY AREA"

                print(
                    f"{j:6d} "
                    f"{str(trend_rows[j]['timestamp']):>22} "
                    f"{closes_30[j]:11.4f} "
                    f"{ma:11.4f} "
                    f"{dist:+9.3f} "
                    f"{states[j]:>8}"
                    f"{marker}"
                )

        print()
        print("5M CANDLES AROUND ENTRY")
        print("-" * 110)

        start5 = max(0, entry_i - 8)
        end5 = min(len(execution_rows), entry_i + 13)

        print(
            f"{'IDX':>6} "
            f"{'TIME':>22} "
            f"{'OPEN':>10} "
            f"{'HIGH':>10} "
            f"{'LOW':>10} "
            f"{'CLOSE':>10} "
            f"{'CHG%':>8} "
            f"{'RSI':>8}"
        )

        previous_close = None

        for j in range(start5, end5):

            row = execution_rows[j]

            if previous_close is None:
                change = 0.0
            else:
                change = pct(row["close"], previous_close)

            rsi = rsis[j]

            marker = ""

            if j == entry_i:
                marker = "  <-- ENTRY"

            elif j > entry_i and j <= entry_i + 4:
                marker = "  <-- AFTER ENTRY"

            print(
                f"{j:6d} "
                f"{str(row['timestamp']):>22} "
                f"{row['open']:10.4f} "
                f"{row['high']:10.4f} "
                f"{row['low']:10.4f} "
                f"{row['close']:10.4f} "
                f"{change:+8.3f} "
                f"{rsi if rsi is not None else float('nan'):8.2f}"
                f"{marker}"
            )

            previous_close = row["close"]

        print()
        print("IMMEDIATE POST-ENTRY MOVE")
        print("-" * 110)

        for bars in [1, 2, 3, 4, 6, 12]:

            j = entry_i + bars

            if j < len(execution_rows):

                future_close = execution_rows[j]["close"]
                move = pct(future_close, entry_price)

                print(
                    f"{bars:2d} x 5m bars later: "
                    f"{future_close:.4f}   "
                    f"{move:+.3f}%"
                )

        print()

    print("=" * 110)
    print("END LONG ENTRY DIAGNOSTIC")
    print("NO TRADING LOGIC WAS CHANGED.")
    print("=" * 110)
    print()


if __name__ == "__main__":
    main()
