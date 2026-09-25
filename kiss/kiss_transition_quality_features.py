"""
KISS transition DNA feature diagnostic.

Purpose:
    Study what information available AT a 30m transition distinguishes
    REAL transitions from WEAK/FALSE transitions.

RESEARCH ONLY:
    - no engine changes
    - no database writes
    - no live trading
    - predictor features use no future information

The future is used only to assign the ex-post REAL/WEAK/FALSE label.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from db import get_db_connection
from engine.kiss_execution_5m import get_market_state, _v_shape, rsi_wilder

SYMBOL = "NVDA"
TREND_LIMIT = 5000
EXEC_LIMIT = 5000
LOOKAHEAD_5M = 48  # 4 hours

REAL_MFE = 1.00
REAL_RATIO = 1.50
FALSE_MAE = 1.00
FALSE_MFE = 0.50


def _rows(symbol: str, timeframe: str, limit: int):
    conn, cursor = get_db_connection()
    try:
        cursor.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC
               LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def _dict_rows(rows):
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append(r)
        else:
            out.append({
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5],
            })
    return out


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0 if b else 0.0


def classify_transition(
    entry_price: float,
    future_rows: Sequence[dict],
    direction: str,
) -> Tuple[str, float, float]:
    """Ex-post label only. MFE/MAE are returned as positive magnitudes."""
    favorable = []
    adverse_signed = []

    for r in future_rows[:LOOKAHEAD_5M]:
        hi = float(r["high"])
        lo = float(r["low"])
        if direction == "LONG":
            favorable.append(pct(hi, entry_price))
            adverse_signed.append(pct(lo, entry_price))
        else:
            favorable.append(pct(entry_price, lo))
            adverse_signed.append(pct(entry_price, hi))

    if not favorable:
        return "UNKNOWN", 0.0, 0.0

    mfe = max(0.0, max(favorable))
    # For both LONG and SHORT the adverse series is negative when price moves
    # against the position. Convert its largest negative excursion to +MAE.
    mae = max(0.0, -min(adverse_signed))

    if mfe >= REAL_MFE and mfe >= max(mae, 0.0001) * REAL_RATIO:
        label = "REAL"
    elif mae >= FALSE_MAE and mfe < FALSE_MFE:
        label = "FALSE"
    else:
        label = "WEAK"
    return label, mfe, mae


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def bin_rsi(x: float) -> str:
    if x < 35:
        return "<35"
    if x < 50:
        return "35-50"
    if x < 65:
        return "50-65"
    return ">=65"


def bin_dist(x: float) -> str:
    x = abs(x)
    if x < 0.30:
        return "<0.30%"
    if x < 0.70:
        return "0.30-0.70%"
    return ">=0.70%"


def bin_duration(x: int) -> str:
    if x <= 2:
        return "1-2 bars"
    if x <= 5:
        return "3-5 bars"
    return "6+ bars"


def bin_churn(x: int) -> str:
    if x <= 1:
        return "0-1 flips"
    if x <= 3:
        return "2-3 flips"
    return "4+ flips"


def summarize(rows: List[dict], key: str) -> None:
    groups: Dict[str, List[dict]] = {}
    for r in rows:
        groups.setdefault(str(r[key]), []).append(r)

    print(f"\n=== BY {key.upper()} ===")
    print("GROUP                         N   REAL%  WEAK% FALSE%  AVG_MFE  AVG_MAE")
    for name, items in groups.items():
        n = len(items)
        real = sum(x["label"] == "REAL" for x in items)
        weak = sum(x["label"] == "WEAK" for x in items)
        false = sum(x["label"] == "FALSE" for x in items)
        print(
            f"{name:<29} {n:>3} {100*real/n:>7.1f} {100*weak/n:>7.1f} "
            f"{100*false/n:>7.1f} {mean([x['mfe'] for x in items]):>8.3f} "
            f"{mean([x['mae'] for x in items]):>8.3f}"
        )


def combo_scan(rows: List[dict]) -> None:
    """Simple research scan for small, interpretable feature combinations."""
    specs = [
        ("type+RSI", lambda r: f"{r['transition']} | RSI {bin_rsi(r['rsi'])}"),
        ("type+dist", lambda r: f"{r['transition']} | dist {bin_dist(r['distance'])}"),
        ("type+duration", lambda r: f"{r['transition']} | prev {bin_duration(r['prev_duration'])}"),
        ("type+churn", lambda r: f"{r['transition']} | churn {bin_churn(r['churn'])}"),
        ("type+MA slope", lambda r: f"{r['transition']} | MA slope {'UP' if r['ma_slope'] > 0 else 'DOWN' if r['ma_slope'] < 0 else 'FLAT'}"),
        ("type+shape", lambda r: f"{r['transition']} | {r['shape']}"),
    ]

    print("\n=== SIMPLE DNA COMBINATION SCAN ===")
    print("Only groups with N >= 5 are shown. Exploratory only; not a trading rule.")
    for title, fn in specs:
        groups: Dict[str, List[dict]] = {}
        for r in rows:
            groups.setdefault(fn(r), []).append(r)
        ranked = []
        for name, items in groups.items():
            if len(items) < 5:
                continue
            real = sum(x["label"] == "REAL" for x in items)
            false = sum(x["label"] == "FALSE" for x in items)
            ranked.append((real / len(items), false / len(items), len(items), name))
        ranked.sort(key=lambda x: (-x[0], x[1], -x[2]))
        print(f"\n-- {title} --")
        for rp, fp, n, name in ranked[:10]:
            print(f"{name:<52} N={n:>2} REAL={100*rp:>5.1f}% FALSE={100*fp:>5.1f}%")


def main() -> None:
    trend = _dict_rows(_rows(SYMBOL, "30m", TREND_LIMIT))
    execution = _dict_rows(_rows(SYMBOL, "5m", EXEC_LIMIT))
    closes = [float(r["close"]) for r in trend]
    rsi_values = rsi_wilder(closes, 14)

    states = [get_market_state(closes, i) for i in range(len(closes))]
    transitions = []
    for i in range(1, len(states)):
        if states[i] != states[i - 1]:
            transitions.append({
                "i": i,
                "from": states[i - 1],
                "to": states[i],
                "timestamp": trend[i]["timestamp"],
            })

    # Use binary search on the sorted 5m timestamps. This guarantees that
    # every transition gets its own first execution candle at/after the
    # transition rather than accidentally reusing the same candle.
    exec_times = [r["timestamp"] for r in execution]
    rows: List[dict] = []

    for t in transitions:
        i = t["i"]
        if t["to"] not in ("LONG", "SHORT"):
            continue
        if i >= len(trend) - 1:
            continue

        ex_i = bisect_left(exec_times, t["timestamp"])
        if ex_i >= len(execution):
            continue

        entry_price = float(execution[ex_i]["close"])
        future = execution[ex_i + 1: ex_i + 1 + LOOKAHEAD_5M]
        label, mfe, mae = classify_transition(entry_price, future, t["to"])
        if label == "UNKNOWN":
            continue

        ma20 = mean(closes[i - 20:i]) if i >= 20 else 0.0
        prev_ma = mean(closes[i - 21:i - 1]) if i >= 21 else ma20
        distance = pct(closes[i], ma20) if ma20 else 0.0
        ma_slope = pct(ma20, prev_ma) if prev_ma else 0.0
        shape = _v_shape(closes, i) or "NO_SHAPE"

        # Backward-looking duration of the state immediately before transition.
        prev_duration = 0
        k = i - 1
        while k >= 0 and states[k] == t["from"]:
            prev_duration += 1
            k -= 1

        # Number of state changes in the previous 6 completed 30m bars.
        start = max(1, i - 6)
        churn = sum(states[x] != states[x - 1] for x in range(start, i))

        def prior_change(n: int) -> float:
            if i < n:
                return 0.0
            return pct(closes[i], closes[i - n])

        # Current and previous 12 completed 30m closes are known at transition.
        recent = closes[max(0, i - 12): i + 1]
        recent_high = max(recent) if recent else closes[i]
        recent_low = min(recent) if recent else closes[i]
        from_high = pct(closes[i], recent_high) if recent_high else 0.0
        from_low = pct(closes[i], recent_low) if recent_low else 0.0

        rows.append({
            "timestamp": t["timestamp"],
            "transition": f"{t['from']}->{t['to']}",
            "direction": t["to"],
            "price": closes[i],
            "ma20": ma20,
            "distance": distance,
            "ma_slope": ma_slope,
            "rsi": float(rsi_values[i]) if i < len(rsi_values) else 0.0,
            "shape": shape,
            "prev_duration": prev_duration,
            "churn": churn,
            "chg1": prior_change(1),
            "chg2": prior_change(2),
            "chg3": prior_change(3),
            "chg4": prior_change(4),
            "chg6": prior_change(6),
            "chg12": prior_change(12),
            "recent_high_dist": from_high,
            "recent_low_dist": from_low,
            "label": label,
            "mfe": mfe,
            "mae": mae,
        })

    for r in rows:
        r["rsi_bin"] = bin_rsi(r["rsi"])
        r["distance_bin"] = bin_dist(r["distance"])
        r["duration_bin"] = bin_duration(r["prev_duration"])
        r["churn_bin"] = bin_churn(r["churn"])
        r["ma_slope_bin"] = "UP" if r["ma_slope"] > 0 else "DOWN" if r["ma_slope"] < 0 else "FLAT"

    print("KISS TRANSITION DNA FEATURE DIAGNOSTIC")
    print("=" * 72)
    print(f"Symbol: {SYMBOL}")
    print(f"30m candles: {len(trend)}")
    print(f"5m candles:  {len(execution)}")
    print(f"Transitions analyzed: {len(rows)}")
    print("Features use ONLY information available at/before transition.")
    print("REAL/WEAK/FALSE uses the next 4 hours of 5m price action.")
    print("MAE is reported as a positive adverse-move magnitude.")

    counts = Counter(r["label"] for r in rows)
    print(f"\nLABELS: REAL={counts['REAL']}  WEAK={counts['WEAK']}  FALSE={counts['FALSE']}")

    summarize(rows, "transition")
    summarize(rows, "shape")
    summarize(rows, "rsi_bin")
    summarize(rows, "distance_bin")
    summarize(rows, "duration_bin")
    summarize(rows, "churn_bin")
    summarize(rows, "ma_slope_bin")

    for direction in ("LONG", "SHORT"):
        subset = [r for r in rows if r["direction"] == direction]
        print(f"\n{'=' * 72}\nDIRECTION: {direction} | N={len(subset)}")
        summarize(subset, "transition")
        summarize(subset, "rsi_bin")
        summarize(subset, "distance_bin")
        summarize(subset, "duration_bin")
        summarize(subset, "churn_bin")
        summarize(subset, "ma_slope_bin")

    combo_scan(rows)

    print("\n=== INDIVIDUAL TRANSITION RECORDS ===")
    print("TIME                       TRANSITION    RSI   DIST   MA_SLOPE  PREV  CHURN SHAPE    LABEL  MFE    MAE")
    for r in rows:
        print(
            f"{str(r['timestamp']):<26} {r['transition']:<13} "
            f"{r['rsi']:>5.1f} {r['distance']:>7.3f} {r['ma_slope']:>8.3f} "
            f"{r['prev_duration']:>5} {r['churn']:>5} {r['shape']:<8} "
            f"{r['label']:<6} {r['mfe']:>5.2f} {r['mae']:>5.2f}"
        )

    print("\nDONE. No database rows were written and no trading engine was changed.")


if __name__ == "__main__":
    main()
