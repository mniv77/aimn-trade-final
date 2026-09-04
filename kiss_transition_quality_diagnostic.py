"""
KISS TRANSITION QUALITY DIAGNOSTIC
==================================

Diagnostic only. DOES NOT modify the trading engine and DOES NOT write to DB.

Purpose:
    Evaluate every 30m state transition as REAL / WEAK / FALSE using only
    FUTURE price behavior as an EX-POST label. These labels are for research;
    they must never be fed into live trading as if they were known at the
    transition time.

Current KISS state logic is reused exactly from engine.kiss_execution_5m:
    TREND_WINDOW, TREND_BAND, and _v_shape().

Classification (configurable below):
    REAL:
        favorable move reaches REAL_MOVE_PCT within FORWARD_5M_BARS and
        favorable movement is at least REAL_EDGE_MULT times adverse movement.

    FALSE:
        adverse move reaches FALSE_MOVE_PCT before favorable movement reaches
        FALSE_ESCAPE_PCT.

    WEAK:
        everything between the two cases above.

The diagnostic also prints transition context available AT THE TRANSITION:
    price, state change, V-shape, RSI, MA20 distance, and next 5m reaction.

It then reports the ex-post label and forward MFE/MAE so we can discover
which transition characteristics distinguish real transitions from noise.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection
from engine.kiss_execution_5m import (
    TREND_BAND,
    TREND_WINDOW,
    _v_shape,
    rsi_wilder,
)

SYMBOL = "NVDA"
BROKER_ID = 2
TREND_TIMEFRAME = "30m"
EXECUTION_TIMEFRAME = "5m"
LIMIT = 5000

# Research thresholds only. These are NOT trading rules.
FORWARD_5M_BARS = 48          # 4 hours
REAL_MOVE_PCT = 1.00
REAL_EDGE_MULT = 1.50
FALSE_MOVE_PCT = 1.00
FALSE_ESCAPE_PCT = 0.50

RSI_PERIOD = 14


def _rows(symbol: str, timeframe: str, limit: int = LIMIT) -> List[Dict[str, Any]]:
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
        raw = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    out: List[Dict[str, Any]] = []
    for r in raw:
        out.append(
            {
                "timestamp": r["timestamp"],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume") or 0),
            }
        )
    return out


def _state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def _pct(a: float, b: float) -> float:
    return (b / a - 1.0) * 100.0 if a else 0.0


def _forward_metrics(
    rows: Sequence[Dict[str, Any]],
    idx: int,
    direction: str,
) -> Dict[str, Any]:
    entry = float(rows[idx]["close"])
    end = min(len(rows), idx + FORWARD_5M_BARS + 1)

    mfe = 0.0
    mae = 0.0
    first_favorable_i: Optional[int] = None
    first_adverse_i: Optional[int] = None
    first_real_i: Optional[int] = None
    first_false_i: Optional[int] = None

    for j in range(idx + 1, end):
        hi = float(rows[j]["high"])
        lo = float(rows[j]["low"])

        if direction == "LONG":
            fav = _pct(entry, hi)
            adv = _pct(entry, lo)
            favorable = fav
            adverse = max(0.0, -adv)
        else:
            fav = _pct(entry, lo)
            adv = _pct(entry, hi)
            favorable = fav
            adverse = max(0.0, -adv)

        mfe = max(mfe, favorable)
        mae = max(mae, adverse)

        if favorable >= FALSE_ESCAPE_PCT and first_favorable_i is None:
            first_favorable_i = j
        if adverse >= FALSE_MOVE_PCT and first_adverse_i is None:
            first_adverse_i = j

        if first_real_i is None and favorable >= REAL_MOVE_PCT:
            first_real_i = j
        if first_false_i is None and adverse >= FALSE_MOVE_PCT:
            first_false_i = j

    # Event ordering matters for the FALSE label: if the adverse threshold is
    # reached before the escape threshold, the transition is considered false.
    false_before_escape = (
        first_adverse_i is not None
        and (first_favorable_i is None or first_adverse_i < first_favorable_i)
    )

    if mfe >= REAL_MOVE_PCT and mfe >= max(mae, 0.01) * REAL_EDGE_MULT:
        label = "REAL"
    elif false_before_escape:
        label = "FALSE"
    else:
        label = "WEAK"

    return {
        "label": label,
        "mfe": mfe,
        "mae": mae,
        "first_favorable_i": first_favorable_i,
        "first_adverse_i": first_adverse_i,
        "first_real_i": first_real_i,
        "first_false_i": first_false_i,
        "bars": max(0, end - idx - 1),
    }


def _transition_events(trend_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [float(r["close"]) for r in trend_rows]
    events: List[Dict[str, Any]] = []
    previous = _state(closes, TREND_WINDOW)

    for i in range(TREND_WINDOW + 1, len(trend_rows)):
        current = _state(closes, i)
        if current != previous:
            price = closes[i]
            ma = sum(closes[i - TREND_WINDOW:i]) / TREND_WINDOW
            dist = (price / ma - 1.0) * 100.0 if ma else 0.0
            events.append(
                {
                    "idx": i,
                    "timestamp": trend_rows[i]["timestamp"],
                    "from": previous,
                    "to": current,
                    "price": price,
                    "ma20": ma,
                    "distance_pct": dist,
                    "shape": _v_shape(closes, i),
                }
            )
        previous = current

    return events


def _nearest_5m(rows: Sequence[Dict[str, Any]], ts: datetime) -> Optional[int]:
    best: Optional[int] = None
    for i, r in enumerate(rows):
        rts = r["timestamp"]
        if rts >= ts:
            return i
        best = i
    return best


def _rsi_context(ex_rows: Sequence[Dict[str, Any]], idx: int) -> Optional[float]:
    closes = [float(r["close"]) for r in ex_rows]
    if idx >= len(closes):
        return None
    values = rsi_wilder(closes[: idx + 1], RSI_PERIOD)
    if not values:
        return None
    return values[-1]


def main() -> None:
    trend_rows = _rows(SYMBOL, TREND_TIMEFRAME)
    ex_rows = _rows(SYMBOL, EXECUTION_TIMEFRAME)

    events = _transition_events(trend_rows)

    print("=" * 118)
    print("KISS TRANSITION QUALITY DIAGNOSTIC — REAL / WEAK / FALSE")
    print("=" * 118)
    print(f"Symbol={SYMBOL} Broker={BROKER_ID} Trend={TREND_TIMEFRAME} Execution={EXECUTION_TIMEFRAME}")
    print(
        f"TREND_WINDOW={TREND_WINDOW} TREND_BAND={TREND_BAND * 100:.3f}% "
        f"Forward={FORWARD_5M_BARS}x5m ({FORWARD_5M_BARS * 5 / 60:.1f}h)"
    )
    print(
        f"REAL: MFE>={REAL_MOVE_PCT:.2f}% and MFE>=MAE*{REAL_EDGE_MULT:.2f} | "
        f"FALSE: adverse>={FALSE_MOVE_PCT:.2f}% before favorable>={FALSE_ESCAPE_PCT:.2f}%"
    )
    print("IMPORTANT: REAL/WEAK/FALSE are EX-POST research labels, never live signals.")
    print(f"30m candles={len(trend_rows)} 5m candles={len(ex_rows)} transitions={len(events)}")
    print("=" * 118)

    detail: List[Dict[str, Any]] = []

    for n, e in enumerate(events, 1):
        ex_i = _nearest_5m(ex_rows, e["timestamp"])
        if ex_i is None:
            continue

        metrics = _forward_metrics(ex_rows, ex_i, e["to"] if e["to"] in ("LONG", "SHORT") else "LONG")
        rsi = _rsi_context(ex_rows, ex_i)

        e2 = dict(e)
        e2.update(metrics)
        e2["rsi"] = rsi
        e2["ex_i"] = ex_i
        detail.append(e2)

        print(
            f"{n:03d} {e['timestamp']} | {e['from']:5s}->{e['to']:5s} | "
            f"price={e['price']:.4f} | MA20={e['ma20']:.4f} | dist={e['distance_pct']:+.3f}% | "
            f"shape={str(e['shape']):7s} | RSI={rsi if rsi is not None else float('nan'):.2f} | "
            f"LABEL={metrics['label']:5s} | MFE={metrics['mfe']:+.3f}% | MAE={metrics['mae']:+.3f}%"
        )

    print("\n" + "=" * 118)
    print("SUMMARY BY LABEL")
    print("=" * 118)

    for label in ("REAL", "WEAK", "FALSE"):
        group = [x for x in detail if x["label"] == label]
        if not group:
            print(f"{label:5s}: 0")
            continue
        avg_mfe = sum(x["mfe"] for x in group) / len(group)
        avg_mae = sum(x["mae"] for x in group) / len(group)
        print(
            f"{label:5s}: count={len(group):3d} "
            f"avg_MFE={avg_mfe:+.3f}% avg_MAE={avg_mae:+.3f}%"
        )

    print("\n" + "=" * 118)
    print("SUMMARY BY TRANSITION")
    print("=" * 118)
    for transition in ("SHORT->LONG", "FLAT->LONG", "LONG->SHORT", "FLAT->SHORT", "LONG->FLAT", "SHORT->FLAT", "FLAT->FLAT"):
        group = [x for x in detail if f"{x['from']}->{x['to']}" == transition]
        if not group:
            continue
        counts = {label: sum(1 for x in group if x["label"] == label) for label in ("REAL", "WEAK", "FALSE")}
        avg_mfe = sum(x["mfe"] for x in group) / len(group)
        avg_mae = sum(x["mae"] for x in group) / len(group)
        print(
            f"{transition:12s} count={len(group):3d} "
            f"REAL={counts['REAL']:2d} WEAK={counts['WEAK']:2d} FALSE={counts['FALSE']:2d} "
            f"avg_MFE={avg_mfe:+.3f}% avg_MAE={avg_mae:+.3f}%"
        )

    print("\n" + "=" * 118)
    print("SUMMARY BY V-SHAPE")
    print("=" * 118)
    for shape in ("V-LONG", "V-SHORT", None):
        group = [x for x in detail if x["shape"] == shape]
        if not group:
            continue
        counts = {label: sum(1 for x in group if x["label"] == label) for label in ("REAL", "WEAK", "FALSE")}
        name = shape or "NO_SHAPE"
        print(
            f"{name:8s} count={len(group):3d} "
            f"REAL={counts['REAL']:2d} WEAK={counts['WEAK']:2d} FALSE={counts['FALSE']:2d}"
        )

    print("\n" + "=" * 118)
    print("RESEARCH NOTE")
    print("=" * 118)
    print("This diagnostic intentionally uses future price action to LABEL transitions after the fact.")
    print("The next step is to compare these labels against information known AT the transition")
    print("and discover whether a simple, non-lookahead transition-quality filter can separate")
    print("REAL transitions from FALSE ones without eliminating too many REAL moves.")
    print("NO ENGINE CHANGES. NO DATABASE WRITES.")
    print("=" * 118)


if __name__ == "__main__":
    main()
