"""
KISS Transition Diagnostic
==========================

Diagnostic only. Does NOT modify the KISS engine and does NOT write to MySQL.

Uses the CURRENT engine implementation to reproduce its trades, then measures:
- 30m state transitions and previous-state duration
- transition -> actual 5m entry delay
- first adverse moves of 0.25/0.50/1.00/1.50%
- first favorable moves of 0.25/0.50/1.00/1.50/2.00%
- early 5m response of every trade

Run:
    python kiss_transition_diagnostic.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from db import get_db_connection
from engine.kiss_execution_5m import (
    TREND_BAND,
    TREND_WINDOW,
    _entry_confirmed,
    _v_shape,
    get_market_state,
    rsi_wilder,
    run_kiss_30m_5m,
)

SYMBOL = "NVDA"
BROKER_ID = 2
TREND_TF = "30m"
EXEC_TF = "5m"
ADVERSE = [0.25, 0.50, 1.00, 1.50]
FAVORABLE = [0.25, 0.50, 1.00, 1.50, 2.00]


def ts(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    text = str(v).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
    return None


def load(symbol: str, timeframe: str) -> List[Dict[str, Any]]:
    tf = {"1hr": "1h", "6hr": "6h"}.get(timeframe, timeframe)
    conn, cur = get_db_connection()
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, tf, 5000),
        )
        rows = cur.fetchall() or []
        for row in rows:
            row["timestamp"] = ts(row.get("timestamp"))
            for key in ("open", "high", "low", "close", "volume"):
                try:
                    row[key] = float(row[key]) if row[key] is not None else None
                except (TypeError, ValueError):
                    row[key] = None
        return rows
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def move(entry: float, price: float, direction: str) -> float:
    raw = (price / entry - 1.0) * 100.0
    return -raw if direction == "SHORT" else raw


def closest(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    best = None
    best_delta = None
    for i, row in enumerate(rows):
        t = row.get("timestamp")
        if t is None:
            continue
        d = abs((t - target).total_seconds())
        if best_delta is None or d < best_delta:
            best_delta, best = d, i
    return best


def transition_events(trend_rows: Sequence[Dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    closes = [float(r["close"]) for r in trend_rows]
    states = [get_market_state(closes, i) for i in range(len(closes))]
    events = []
    for i in range(TREND_WINDOW + 1, len(states)):
        if states[i] == states[i - 1]:
            continue
        duration = 1
        j = i - 2
        while j >= 0 and states[j] == states[i - 1]:
            duration += 1
            j -= 1
        events.append({
            "index": i,
            "time": trend_rows[i]["timestamp"],
            "from": states[i - 1],
            "to": states[i],
            "shape": _v_shape(closes, i),
            "price": closes[i],
            "duration_bars": duration,
        })
    return states, events


def first_threshold(rows, entry_i, direction, entry_price, threshold, favorable):
    for offset in range(1, min(len(rows) - entry_i, 289)):
        i = entry_i + offset
        m = move(entry_price, rows[i]["close"], direction)
        if (favorable and m >= threshold) or ((not favorable) and m <= -threshold):
            return offset, rows[i]["timestamp"], m
    return None


def analyze_trade(trade: Dict[str, Any], execution_rows, events):
    entry_time = ts(trade["entry_time"])
    event = None
    for e in events:
        if e["to"] != trade["direction"]:
            continue
        if e["time"] is None or entry_time is None:
            continue
        if e["time"] <= entry_time:
            event = e
        else:
            break
    delay = None
    if event and entry_time:
        delay = (entry_time - event["time"]).total_seconds() / 60.0

    entry_i = closest(execution_rows, entry_time) if entry_time else None
    result = dict(trade)
    result["transition_event"] = event
    result["transition_delay_min"] = delay
    result["entry_i"] = entry_i
    if entry_i is not None:
        for x in ADVERSE:
            result[f"adv{x}"] = first_threshold(execution_rows, entry_i, trade["direction"], trade["entry_price"], x, False)
        for x in FAVORABLE:
            result[f"fav{x}"] = first_threshold(execution_rows, entry_i, trade["direction"], trade["entry_price"], x, True)
    return result


def fmt(value):
    return "n/a" if value is None else f"{value:+.3f}%"


def main():
    print("=" * 90)
    print("KISS TRANSITION DIAGNOSTIC — DRY RUN ONLY")
    print("=" * 90)
    print(f"Symbol={SYMBOL} Broker={BROKER_ID} Trend={TREND_TF} Execution={EXEC_TF}")
    print(f"TREND_WINDOW={TREND_WINDOW} TREND_BAND={TREND_BAND * 100:.3f}%")
    print("NO DATABASE WRITES")

    trend_rows = load(SYMBOL, TREND_TF)
    execution_rows = load(SYMBOL, EXEC_TF)
    print(f"30m candles: {len(trend_rows)}")
    print(f"5m candles : {len(execution_rows)}")

    if not trend_rows or not execution_rows:
        print("ERROR: missing candle data")
        return

    states, events = transition_events(trend_rows)
    print(f"30m state transitions: {len(events)}")

    counts = {}
    for e in events:
        key = f"{e['from']}->{e['to']}"
        counts[key] = counts.get(key, 0) + 1
    print("Transition counts:")
    for key in sorted(counts):
        print(f"  {key:<15} {counts[key]}")

    all_trades = []
    for direction in ("LONG", "SHORT"):
        result = run_kiss_30m_5m(trend_rows, execution_rows, SYMBOL, direction)
        trades = [analyze_trade(t, execution_rows, events) for t in result["trades"]]
        all_trades.extend(trades)

        print()
        print("=" * 90)
        print(f"{direction}: {len(trades)} trades | P&L={result['total_pnl_pct']:+.3f}% | Win rate={result['win_rate_pct']:.2f}%")
        print("=" * 90)
        print("TRADE             ENTRY                TRANSITION        DELAY     P&L       MFE       MAE    -0.25  -0.50  -1.00  -1.50")
        print("-" * 125)

        for t in trades:
            e = t["transition_event"]
            transition = t["entry_transition"]
            delay = "n/a" if t["transition_delay_min"] is None else f"{t['transition_delay_min']:.0f}m"
            hits = []
            for x in ADVERSE:
                hit = t.get(f"adv{x}")
                hits.append(str(hit[0]) if hit else "-")
            print(
                f"{t['trade_id']:<17} {str(t['entry_time']):19} {transition:<16} {delay:>7} "
                f"{fmt(t['pnl_pct']):>9} {fmt(t['max_favorable_pct']):>9} {fmt(t['max_adverse_pct']):>9} "
                f"{hits[0]:>6} {hits[1]:>6} {hits[2]:>6} {hits[3]:>6}"
            )
            if t["pnl_pct"] <= 0:
                print(f"  LOSER: entry RSI={t.get('entry_rsi')} exit={t.get('exit_reason')} exit_transition={t.get('exit_transition')}")
                if e:
                    print(f"  Transition at {e['time']} price={e['price']:.4f}; previous {e['from']} lasted {e['duration_bars']} x 30m bars; shape={e['shape']}")
                print("  First 12 x 5m moves:", end=" ")
                if t["entry_i"] is not None:
                    for offset in range(0, min(13, len(execution_rows) - t["entry_i"])):
                        i = t["entry_i"] + offset
                        print(f"{offset}:{move(t['entry_price'], execution_rows[i]['close'], direction):+.3f}%", end=" ")
                print()

    print()
    print("=" * 90)
    print("EARLY FAILURE COMPARISON")
    print("=" * 90)
    for direction in ("LONG", "SHORT"):
        subset = [t for t in all_trades if t["direction"] == direction]
        losers = [t for t in subset if t["pnl_pct"] < 0]
        winners = [t for t in subset if t["pnl_pct"] > 0]
        print(f"{direction}: {len(winners)} winners / {len(losers)} losers")
        for x in (0.25, 0.50, 1.00, 1.50):
            lh = sum(t.get(f"adv{x}") is not None for t in losers)
            wh = sum(t.get(f"adv{x}") is not None for t in winners)
            print(f"  adverse {x:.2f}% within first 24h: losers {lh}/{len(losers)}, winners {wh}/{len(winners)}")

    print()
    print("DIAGNOSTIC COMPLETE — engine unchanged, DB unchanged.")


if __name__ == "__main__":
    main()
