from engine.kiss_execution_5m import (
    TREND_WINDOW,
    TREND_BAND,
    get_market_state,
)

from db import get_db_connection


SYMBOL = "NVDA"
TIMEFRAME = "30m"
LIMIT = 5000


def load_candles():
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
            (SYMBOL, TIMEFRAME, LIMIT),
        )

        rows = cursor.fetchall()

        normalized = []

        for r in rows:
            if isinstance(r, dict):
                normalized.append({
                    "timestamp": r.get("timestamp"),
                    "open": float(r.get("open")),
                    "high": float(r.get("high")),
                    "low": float(r.get("low")),
                    "close": float(r.get("close")),
                })
            else:
                normalized.append({
                    "timestamp": r[0],
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                })

        return normalized

    finally:
        conn.close()


def main():
    rows = load_candles()

    if len(rows) <= TREND_WINDOW:
        print("Not enough candles.")
        return

    closes = [r["close"] for r in rows]

    states = [
        get_market_state(closes, i)
        for i in range(len(closes))
    ]

    print()
    print("=" * 100)
    print("KISS TRANSITION DIAGNOSTIC")
    print("=" * 100)
    print(f"Symbol       : {SYMBOL}")
    print(f"Timeframe    : {TIMEFRAME}")
    print(f"Candles      : {len(rows)}")
    print(f"TREND_WINDOW : {TREND_WINDOW}")
    print(f"TREND_BAND   : {TREND_BAND * 100:.3f}%")
    print("=" * 100)
    print()

    transitions = []

    for i in range(TREND_WINDOW + 1, len(rows)):

        previous = states[i - 1]
        current = states[i]

        if previous != current:

            ma = sum(
                closes[i - TREND_WINDOW:i]
            ) / TREND_WINDOW

            distance_pct = (
                (closes[i] - ma) / ma
            ) * 100.0

            transitions.append({
                "index": i,
                "timestamp": rows[i]["timestamp"],
                "close": closes[i],
                "ma": ma,
                "distance_pct": distance_pct,
                "from": previous,
                "to": current,
            })

    print(f"TOTAL STATE TRANSITIONS: {len(transitions)}")
    print()

    for n, event in enumerate(transitions, 1):

        i = event["index"]

        print("=" * 100)
        print(
            f"TRANSITION #{n}: "
            f"{event['from']} -> {event['to']}"
        )
        print(
            f"Time: {event['timestamp']}   "
            f"Close: {event['close']:.4f}   "
            f"MA20: {event['ma']:.4f}   "
            f"Distance: {event['distance_pct']:+.3f}%"
        )
        print("-" * 100)

        start = max(TREND_WINDOW, i - 6)
        end = min(len(rows), i + 1)

        print(
            f"{'INDEX':>7} "
            f"{'TIME':>22} "
            f"{'CLOSE':>12} "
            f"{'MA20':>12} "
            f"{'DIST%':>9} "
            f"{'STATE':>8}"
        )

        for j in range(start, end):

            ma = sum(
                closes[j - TREND_WINDOW:j]
            ) / TREND_WINDOW

            distance_pct = (
                (closes[j] - ma) / ma
            ) * 100.0

            marker = "  <--- TRANSITION" if j == i else ""

            print(
                f"{j:7d} "
                f"{str(rows[j]['timestamp']):>22} "
                f"{closes[j]:12.4f} "
                f"{ma:12.4f} "
                f"{distance_pct:+9.3f} "
                f"{states[j]:>8}"
                f"{marker}"
            )

        print()

    print("=" * 100)
    print("END DIAGNOSTIC")
    print("=" * 100)
    print("No trading logic was changed.")
    print()


if __name__ == "__main__":
    main()
