"""
KISS Exact Transition / Pending-Entry Diagnostic
=================================================

Diagnostic only. Does NOT modify the KISS engine and does NOT write to MySQL.

Purpose:
- Reproduce the CURRENT KISS transition-event and pending-entry lifecycle.
- Record exactly which 30m transition creates each pending entry.
- Show whether a later transition replaces that pending entry before execution.
- Measure the true transition -> entry delay for the transition that actually
  created the trade, rather than guessing from the latest matching transition.
- Show the first 12 x 5m price moves after entry.
- Highlight losing trades and the transition that eventually closed them.

This intentionally mirrors the current engine's transition/pending-entry rules;
it does not change them.

Run:
    python kiss_exact_transition_diagnostic.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from db import get_db_connection
from engine.kiss_execution_5m import (
    CONFIRM_BARS,
    MIN_CONFIRM,
    TREND_BAND,
    TREND_WINDOW,
    _entry_confirmed,
    _v_shape,
    get_market_state,
    run_kiss_30m_5m,
)

SYMBOL = "NVDA"
BROKER_ID = 2
TREND_TF = "30m"
EXEC_TF = "5m"


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


def build_events(trend_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [float(r["close"]) for r in trend_rows]
    states = [get_market_state(closes, i) for i in range(len(closes))]
    events: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(trend_rows)):
        if states[i] == states[i - 1]:
            continue
        events.append(
            {
                "index": i,
                "time": trend_rows[i]["timestamp"],
                "from": states[i - 1],
                "to": states[i],
                "shape": _v_shape(closes, i),
                "price": closes[i],
            }
        )
    return events


def event_desc(e: Optional[Dict[str, Any]]) -> str:
    if not e:
        return "NONE"
    shape = e.get("shape") or "-"
    return f"{e['from']}->{e['to']} @ {e['time']} price={e['price']:.4f} shape={shape}"


def simulate_pending_lifecycle(
    trend_rows: Sequence[Dict[str, Any]],
    execution_rows: Sequence[Dict[str, Any]],
    direction: str,
    actual_trades: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Mirror the current engine's transition/pending-entry logic.

    We intentionally do NOT reproduce exit/trailing logic here. The actual
    current-engine trades are supplied by run_kiss_30m_5m. This simulation only
    determines which transition event generated each entry and what happened
    to the pending entry while waiting for confirmation.
    """
    events = build_events(trend_rows)
    event_index = 0
    pending: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, Any]] = None
    lifecycle: List[Dict[str, Any]] = []

    # Match generated trades in engine order. This avoids guessing the event
    # from timestamps after the fact.
    trade_index = 0
    entry_records: List[Dict[str, Any]] = []

    for i, row in enumerate(execution_rows):
        cur_time = row.get("timestamp")

        while event_index < len(events) and events[event_index]["time"] <= cur_time:
            event = events[event_index]
            event_index += 1
            target = event["to"]

            if position is None:
                if target == direction:
                    if pending is not None:
                        lifecycle.append(
                            {
                                "kind": "REPLACED_PENDING",
                                "time": event["time"],
                                "old": dict(pending),
                                "new": dict(event),
                            }
                        )
                    pending = {
                        "start": i,
                        "event": event,
                    }
                elif target in {"LONG", "SHORT"} and pending is not None:
                    # This mirrors the current engine's behavior: when flat,
                    # an opposite-direction transition does NOT explicitly
                    # cancel pending_entry; it simply does not replace it.
                    lifecycle.append(
                        {
                            "kind": "OPPOSITE_WHILE_PENDING",
                            "time": event["time"],
                            "event": event,
                            "pending": dict(pending),
                        }
                    )
            else:
                opposite = "SHORT" if position["direction"] == "LONG" else "LONG"
                if target == opposite:
                    lifecycle.append(
                        {
                            "kind": "TRADE_EXIT_TRANSITION",
                            "time": event["time"],
                            "event": event,
                            "position": dict(position),
                        }
                    )
                    position = None
                    if target == direction:
                        pending = {"start": i, "event": event}
                    else:
                        pending = None

        if position is None and pending is not None:
            start = pending["start"]
            if i >= start + CONFIRM_BARS and _entry_confirmed(
                [float(r["close"]) for r in execution_rows], start, direction
            ):
                entry_i = start + CONFIRM_BARS
                entry_time = execution_rows[entry_i]["timestamp"]
                event = pending["event"]
                record = {
                    "trade_index": trade_index,
                    "entry_i": entry_i,
                    "entry_time": entry_time,
                    "entry_price": float(execution_rows[entry_i]["close"]),
                    "event": event,
                    "delay_min": (
                        (entry_time - event["time"]).total_seconds() / 60.0
                        if entry_time and event.get("time")
                        else None
                    ),
                    "pending_start_i": start,
                    "pending_start_time": execution_rows[start]["timestamp"],
                    "pending_confirm_bars": i - start,
                    "lifecycle": [],
                }
                entry_records.append(record)
                position = {
                    "direction": direction,
                    "entry_i": entry_i,
                    "entry": float(execution_rows[entry_i]["close"]),
                    "event": event,
                }
                pending = None
                trade_index += 1

    # Attach lifecycle events to the closest relevant entry record. This is
    # mainly useful for replacements/opposite transitions occurring while flat.
    for item in lifecycle:
        t = item["time"]
        candidates = [r for r in entry_records if r["entry_time"] and r["entry_time"] >= t]
        if candidates:
            candidates[0]["lifecycle"].append(item)

    # If the simulation produces a different number of entries from the
    # current engine, report it rather than silently pretending they match.
    if len(entry_records) != len(actual_trades):
        print(
            f"WARNING: lifecycle simulation found {len(entry_records)} entries, "
            f"but current engine returned {len(actual_trades)} trades for {direction}."
        )

    return entry_records


def nearest_record(records: Sequence[Dict[str, Any]], entry_time: datetime) -> Optional[Dict[str, Any]]:
    best = None
    best_delta = None
    for record in records:
        t = record.get("entry_time")
        if t is None:
            continue
        d = abs((t - entry_time).total_seconds())
        if best_delta is None or d < best_delta:
            best_delta = d
            best = record
    return best


def main() -> None:
    print("=" * 100)
    print("KISS EXACT TRANSITION / PENDING-ENTRY DIAGNOSTIC — DRY RUN ONLY")
    print("=" * 100)
    print(f"Symbol={SYMBOL} Broker={BROKER_ID} Trend={TREND_TF} Execution={EXEC_TF}")
    print(
        f"TREND_WINDOW={TREND_WINDOW} TREND_BAND={TREND_BAND * 100:.3f}% "
        f"CONFIRM_BARS={CONFIRM_BARS} MIN_CONFIRM={MIN_CONFIRM}"
    )
    print("NO DATABASE WRITES")

    trend_rows = load(SYMBOL, TREND_TF)
    execution_rows = load(SYMBOL, EXEC_TF)
    print(f"30m candles: {len(trend_rows)}")
    print(f"5m candles : {len(execution_rows)}")

    if not trend_rows or not execution_rows:
        print("ERROR: missing candle data")
        return

    events = build_events(trend_rows)
    print(f"30m state transitions: {len(events)}")
    print()
    print("FIRST / ALL TRANSITIONS")
    print("-" * 100)
    for e in events:
        print(
            f"{e['time']}  {e['from']:>5} -> {e['to']:<5} "
            f"price={e['price']:.4f} shape={e['shape'] or '-'}"
        )

    for direction in ("LONG", "SHORT"):
        result = run_kiss_30m_5m(trend_rows, execution_rows, SYMBOL, direction)
        trades = result["trades"]
        records = simulate_pending_lifecycle(trend_rows, execution_rows, direction, trades)

        print()
        print("=" * 100)
        print(
            f"{direction}: {len(trades)} CURRENT-ENGINE TRADES | "
            f"P&L={result['total_pnl_pct']:+.3f}% | Win rate={result['win_rate_pct']:.2f}%"
        )
        print("=" * 100)
        print(
            "TRADE             ENGINE ENTRY         EXACT TRANSITION             "
            "DELAY     P&L       PENDING WAIT"
        )
        print("-" * 100)

        for idx, trade in enumerate(trades):
            entry_time = ts(trade.get("entry_time"))
            record = nearest_record(records, entry_time) if entry_time else None
            exact_event = record.get("event") if record else None
            delay = record.get("delay_min") if record else None
            wait = record.get("pending_confirm_bars") if record else None
            transition = trade.get("entry_transition") or "?"
            exact = (
                f"{exact_event['from']}->{exact_event['to']} "
                f"@ {exact_event['time']}"
                if exact_event
                else "NOT FOUND"
            )
            delay_text = "n/a" if delay is None else f"{delay:.0f}m"
            wait_text = "n/a" if wait is None else f"{wait} bars"
            print(
                f"{trade['trade_id']:<17} {str(entry_time):19} {exact:<30} "
                f"{delay_text:>7} {trade['pnl_pct']:>+8.3f}% {wait_text:>10}"
            )

            if trade["pnl_pct"] <= 0:
                print("  LOSER")
                print(f"  Engine transition label : {transition}")
                print(f"  Exact creating event    : {event_desc(exact_event)}")
                if record:
                    print(
                        f"  Pending started         : {record['pending_start_time']} "
                        f"(5m index {record['pending_start_i']})"
                    )
                    print(
                        f"  Actual confirmed entry  : {record['entry_time']} "
                        f"@ {record['entry_price']:.4f}"
                    )
                    print(f"  True transition delay   : {delay_text}")
                    if record["lifecycle"]:
                        print("  Lifecycle events before this entry:")
                        for item in record["lifecycle"]:
                            if item["kind"] == "REPLACED_PENDING":
                                old = item["old"]["event"]
                                new = item["new"]
                                print(
                                    f"    REPLACED: {old['from']}->{old['to']} @ {old['time']} "
                                    f"by {new['from']}->{new['to']} @ {new['time']}"
                                )
                            elif item["kind"] == "OPPOSITE_WHILE_PENDING":
                                e = item["event"]
                                p = item["pending"]["event"]
                                print(
                                    f"    OPPOSITE WHILE PENDING: pending {p['from']}->{p['to']} "
                                    f"then {e['from']}->{e['to']} @ {e['time']}"
                                )
                            elif item["kind"] == "TRADE_EXIT_TRANSITION":
                                e = item["event"]
                                print(f"    EXIT TRANSITION: {e['from']}->{e['to']} @ {e['time']}")
                print(f"  Engine exit reason     : {trade.get('exit_reason')}")
                print(f"  Engine exit transition : {trade.get('exit_transition')}")
                print("  First 12 x 5m moves    : ", end="")
                if entry_time:
                    entry_i = next(
                        (
                            i
                            for i, r in enumerate(execution_rows)
                            if r.get("timestamp") == entry_time
                        ),
                        None,
                    )
                    if entry_i is not None:
                        entry_price = float(execution_rows[entry_i]["close"])
                        for off in range(0, min(13, len(execution_rows) - entry_i)):
                            px = float(execution_rows[entry_i + off]["close"])
                            print(f"{off}:{move(entry_price, px, direction):+.3f}%", end=" ")
                print()

    print()
    print("=" * 100)
    print("CRITICAL CHECK")
    print("=" * 100)
    print("The DELAY above is calculated from the exact transition event that created")
    print("the engine's pending_entry, not from a guessed/latest matching transition.")
    print("If any delay is still many hours, that is now real engine behavior and")
    print("not a diagnostic association artifact.")
    print("No engine changes. No database writes.")


if __name__ == "__main__":
    main()
