"""
KISS pending-entry expiration experiment.

Diagnostic only. Does NOT modify engine/kiss_execution_5m.py and does NOT write
anything to MySQL.

Compares the current pending-entry behavior with hypothetical expiration
windows of 30, 60, 90 and 120 minutes. The experiment changes ONLY the lifetime
of a pending transition signal; all existing entry confirmation, exit, RSI and
trailing rules remain unchanged.

Run on PythonAnywhere:
    python kiss_pending_expiration_test.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
WINDOWS_MIN = [30, 60, 90, 120]


def parse_ts(v: Any) -> Optional[datetime]:
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
            row["timestamp"] = parse_ts(row.get("timestamp"))
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


def build_events(trend_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [float(r["close"]) for r in trend_rows]
    states = [get_market_state(closes, i) for i in range(len(closes))]
    events: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(trend_rows)):
        if states[i] != states[i - 1]:
            events.append({
                "index": i,
                "time": trend_rows[i]["timestamp"],
                "from": states[i - 1],
                "to": states[i],
                "shape": _v_shape(closes, i),
                "price": closes[i],
            })
    return events


def entry_candidates(
    trend_rows: Sequence[Dict[str, Any]],
    execution_rows: Sequence[Dict[str, Any]],
    direction: str,
    expiry_min: Optional[int],
) -> List[Dict[str, Any]]:
    """Simulate only pending-entry creation/expiry/confirmation.

    Exit behavior is deliberately excluded. This is a clean comparison of the
    entry-signal lifetime against the CURRENT engine entry rules.
    """
    events = build_events(trend_rows)
    closes = [float(r["close"]) for r in execution_rows]
    event_index = 0
    pending: Optional[Dict[str, Any]] = None
    candidates: List[Dict[str, Any]] = []

    for i, row in enumerate(execution_rows):
        now = row["timestamp"]

        while event_index < len(events) and events[event_index]["time"] <= now:
            event = events[event_index]
            event_index += 1
            target = event["to"]

            if target == direction:
                # The current engine replaces a pending signal with a newer
                # same-direction transition. Preserve that behavior.
                pending = {"start_i": i, "event": event}
            elif target in {"LONG", "SHORT"} and pending is not None:
                # Preserve current behavior: an opposite transition while flat
                # does not explicitly cancel pending_entry.
                pass

        if pending is None:
            continue

        event_time = pending["event"]["time"]
        age_min = (now - event_time).total_seconds() / 60.0

        if expiry_min is not None and age_min > expiry_min:
            candidates.append({
                "kind": "EXPIRED",
                "event": pending["event"],
                "expired_at": now,
                "age_min": age_min,
            })
            pending = None
            continue

        start = pending["start_i"]
        if i >= start + CONFIRM_BARS and _entry_confirmed(closes, start, direction):
            entry_i = start + CONFIRM_BARS
            entry_time = execution_rows[entry_i]["timestamp"]
            candidates.append({
                "kind": "ENTRY",
                "event": pending["event"],
                "entry_i": entry_i,
                "entry_time": entry_time,
                "entry_price": closes[entry_i],
                "delay_min": (entry_time - event_time).total_seconds() / 60.0,
            })
            pending = None

    return candidates


def fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return "n/a"
    return f"{float(v):.{digits}f}"


def summarize_window(
    direction: str,
    expiry_min: Optional[int],
    current_trades: Sequence[Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    entries = [x for x in candidates if x["kind"] == "ENTRY"]
    expired = [x for x in candidates if x["kind"] == "EXPIRED"]

    # Map expiration test entries to actual current-engine trades by entry time.
    current_by_time = {str(t.get("entry_time")): t for t in current_trades}
    matched = []
    for e in entries:
        trade = current_by_time.get(str(e["entry_time"]))
        if trade is not None:
            matched.append(trade)

    pnl = sum(float(t["pnl_pct"]) for t in matched)
    wins = sum(float(t["pnl_pct"]) > 0 for t in matched)
    losers = sum(float(t["pnl_pct"]) <= 0 for t in matched)
    delays = [float(e["delay_min"]) for e in entries]
    adverse = [float(t["max_adverse_pct"]) for t in matched]

    return {
        "direction": direction,
        "expiry": expiry_min,
        "entries": len(entries),
        "expired": len(expired),
        "matched_trades": len(matched),
        "pnl": pnl,
        "wins": wins,
        "losers": losers,
        "win_rate": (wins / len(matched) * 100.0) if matched else 0.0,
        "avg_delay": sum(delays) / len(delays) if delays else 0.0,
        "max_delay": max(delays) if delays else 0.0,
        "avg_adverse": sum(adverse) / len(adverse) if adverse else 0.0,
        "max_adverse": min(adverse) if adverse else 0.0,
        "current_trade_count": len(current_trades),
    }


def main() -> None:
    print("=" * 110)
    print("KISS PENDING-ENTRY EXPIRATION EXPERIMENT — DIAGNOSTIC ONLY")
    print("=" * 110)
    print(f"Symbol={SYMBOL} Broker={BROKER_ID} Trend={TREND_TF} Execution={EXEC_TF}")
    print(
        f"TREND_WINDOW={TREND_WINDOW} TREND_BAND={TREND_BAND * 100:.3f}% "
        f"CONFIRM_BARS={CONFIRM_BARS} MIN_CONFIRM={MIN_CONFIRM}"
    )
    print("Existing engine, RSI, trailing and exits are NOT modified.")
    print("NO DATABASE WRITES")

    trend_rows = load(SYMBOL, TREND_TF)
    execution_rows = load(SYMBOL, EXEC_TF)
    print(f"30m candles: {len(trend_rows)}")
    print(f"5m candles : {len(execution_rows)}")

    if not trend_rows or not execution_rows:
        print("ERROR: missing candle data")
        return

    all_results = []

    for direction in ("LONG", "SHORT"):
        current = run_kiss_30m_5m(trend_rows, execution_rows, SYMBOL, direction)
        current_trades = current["trades"]

        print()
        print("=" * 110)
        print(f"{direction} — CURRENT BASELINE")
        print("=" * 110)
        print(
            f"Trades={len(current_trades)}  P&L={current['total_pnl_pct']:+.3f}%  "
            f"WinRate={current['win_rate_pct']:.2f}%  "
            f"Losers={sum(float(t['pnl_pct']) <= 0 for t in current_trades)}"
        )

        # None = current behavior (no expiration), then controlled windows.
        for expiry in [None] + WINDOWS_MIN:
            candidates = entry_candidates(trend_rows, execution_rows, direction, expiry)
            summary = summarize_window(direction, expiry, current_trades, candidates)
            all_results.append(summary)

            label = "NO EXPIRATION" if expiry is None else f"{expiry} MIN"
            print(
                f"{label:>15} | entries={summary['entries']:>3} "
                f"expired={summary['expired']:>3} "
                f"avg_delay={summary['avg_delay']:>7.1f}m "
                f"max_delay={summary['max_delay']:>7.1f}m"
            )

            if expiry is not None:
                # Show exactly which current trades disappear under this window.
                baseline_times = {str(t.get("entry_time")): t for t in current_trades}
                test_times = {str(e["entry_time"]) for e in candidates if e["kind"] == "ENTRY"}
                removed = [t for tm, t in baseline_times.items() if tm not in test_times]
                removed_pnl = sum(float(t["pnl_pct"]) for t in removed)
                removed_winners = sum(float(t["pnl_pct"]) > 0 for t in removed)
                removed_losers = sum(float(t["pnl_pct"]) <= 0 for t in removed)
                matched = [t for tm, t in baseline_times.items() if tm in test_times]
                test_pnl = sum(float(t["pnl_pct"]) for t in matched)
                test_wins = sum(float(t["pnl_pct"]) > 0 for t in matched)
                test_win_rate = test_wins / len(matched) * 100.0 if matched else 0.0
                print(
                    f"                 RESULT: trades={len(matched):>3} "
                    f"P&L={test_pnl:+8.3f}% WinRate={test_win_rate:6.2f}% "
                    f"removed={len(removed):>3} "
                    f"(losers={removed_losers}, winners={removed_winners}, "
                    f"removed P&L={removed_pnl:+.3f}%)"
                )
                if removed:
                    print("                 removed trades:")
                    for t in removed:
                        print(
                            f"                   {t['trade_id']} "
                            f"entry={t['entry_time']} pnl={float(t['pnl_pct']):+.3f}%"
                        )

        print()
        print("DELAY DISTRIBUTION OF CURRENT ENGINE ENTRIES")
        baseline_candidates = entry_candidates(trend_rows, execution_rows, direction, None)
        for e in [x for x in baseline_candidates if x["kind"] == "ENTRY"]:
            print(
                f"  {e['entry_time']} | {e['event']['from']}->{e['event']['to']} | "
                f"delay={e['delay_min']:.0f}m | entry={e['entry_price']:.4f}"
            )

    print()
    print("=" * 110)
    print("FINAL COMPARISON")
    print("=" * 110)
    print("This is an ENTRY-LIFETIME experiment only. It does not change the engine.")
    print()
    print("Direction  Window       Entries  Expired  AvgDelay  MaxDelay")
    print("-" * 70)
    for r in all_results:
        label = "NONE" if r["expiry"] is None else f"{r['expiry']}m"
        print(
            f"{r['direction']:>8}  {label:>6}       {r['entries']:>3}      "
            f"{r['expired']:>3}      {r['avg_delay']:>7.1f}m  {r['max_delay']:>7.1f}m"
        )

    print()
    print("IMPORTANT: no expiration window is being recommended automatically.")
    print("We will choose only after reviewing which window removes stale losers")
    print("without throwing away too many good trades.")


if __name__ == "__main__":
    main()
