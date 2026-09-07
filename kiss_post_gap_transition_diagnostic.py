"""Research-only diagnostic: detect KISS state transitions after session opens.

Purpose
-------
The post-gap study showed an interesting asymmetry, especially:

    SHORT + relatively LOW -> opening gap often UP

But the main KISS objective is not to trade the gap. It is to recognize
SHORT->FLAT / SHORT->LONG transitions as early as possible.

This script therefore follows each directional session boundary through the
first 120 minutes and records the KISS market state after 30m / 60m / 120m.
It also finds the first state change after the open.

For each event we know only information that would have been available at that
moment. The previous state is calculated at the last completed candle before
the session gap. Future states are calculated only as their candles complete.

Main comparison:
    SHORT + LOW vs SHORT + MIDDLE vs SHORT + HIGH

LONG groups are included for symmetry.

Research only. No orders, no DB writes, no strategy changes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
REL_WINDOW = 12
SESSION_GAP_HOURS = 2.0
MAX_FORWARD_BARS = 4  # 120m on 30m candles
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def market_state(closes: Sequence[float], idx: int) -> str:
    """Same KISS state definition used by the current KISS execution engine."""
    if idx < TREND_WINDOW:
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def relative_position(closes: Sequence[float], idx: int) -> Optional[float]:
    if idx < REL_WINDOW:
        return None
    window = closes[idx - REL_WINDOW:idx]
    lo = min(window)
    hi = max(window)
    if hi <= lo:
        return 50.0
    return 100.0 * (closes[idx] - lo) / (hi - lo)


def rel_bucket(pos: Optional[float]) -> str:
    if pos is None:
        return "UNKNOWN"
    if pos <= 20.0:
        return "LOW"
    if pos >= 80.0:
        return "HIGH"
    return "MIDDLE"


def fetch_rows(symbol: str, limit: int = 10000) -> List[Dict[str, Any]]:
    conn, cursor = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cursor.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC
               LIMIT %s""",
            (symbol, "30m", int(limit)),
        )
        rows = cursor.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            if isinstance(r, dict):
                out.append(r)
            else:
                out.append({
                    "timestamp": r[0], "open": r[1], "high": r[2],
                    "low": r[3], "close": r[4], "volume": r[5],
                })
        return out
    finally:
        conn.close()


def build_events(symbol: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    need = TREND_WINDOW + REL_WINDOW + MAX_FORWARD_BARS + 1
    if len(rows) < need:
        return []

    ts = [_ts(r["timestamp"]) for r in rows]
    opens = [_num(r["open"]) for r in rows]
    highs = [_num(r["high"]) for r in rows]
    lows = [_num(r["low"]) for r in rows]
    closes = [_num(r["close"]) for r in rows]

    events: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + REL_WINDOW, len(rows) - MAX_FORWARD_BARS):
        gap_hours = (ts[i] - ts[i - 1]).total_seconds() / 3600.0
        if gap_hours <= SESSION_GAP_HOURS:
            continue

        prev_close = closes[i - 1]
        next_open = opens[i]
        if prev_close <= 0 or next_open <= 0:
            continue

        prev_state = market_state(closes, i - 1)
        pos = relative_position(closes, i - 1)
        bucket = rel_bucket(pos)
        if prev_state not in {"LONG", "SHORT"} or bucket == "UNKNOWN":
            continue

        gap_pct = (next_open / prev_close - 1.0) * 100.0
        states = [market_state(closes, i + b) for b in range(MAX_FORWARD_BARS)]

        # The first state different from the pre-gap state is the first KISS
        # transition visible after the open. It is deliberately evaluated only
        # at completed 30m candles, never using hindsight inside a candle.
        first_change_bar: Optional[int] = None
        first_change_state: Optional[str] = None
        for b, state in enumerate(states, start=1):
            if state != prev_state:
                first_change_bar = b
                first_change_state = state
                break

        row: Dict[str, Any] = {
            "symbol": symbol,
            "prev_time": ts[i - 1],
            "open_time": ts[i],
            "gap_hours": gap_hours,
            "prev_state": prev_state,
            "relative_position": pos,
            "bucket": bucket,
            "prev_close": prev_close,
            "next_open": next_open,
            "gap_pct": gap_pct,
            "gap_direction": "UP" if gap_pct > 0.05 else "DOWN" if gap_pct < -0.05 else "FLAT",
            "states": states,
            "first_change_bar": first_change_bar,
            "first_change_state": first_change_state,
        }

        for b in range(MAX_FORWARD_BARS):
            end = i + b
            close_ret = (closes[end] / next_open - 1.0) * 100.0
            row[f"ret_{(b + 1) * 30}m"] = close_ret
            row[f"state_{(b + 1) * 30}m"] = states[b]

        # Short/LONG directional excursion over the complete 120m path.
        window_high = max(highs[i:i + MAX_FORWARD_BARS])
        window_low = min(lows[i:i + MAX_FORWARD_BARS])
        if prev_state == "SHORT":
            row["mfe_120m"] = (next_open - window_low) / next_open * 100.0
            row["mae_120m"] = (window_high - next_open) / next_open * 100.0
        else:
            row["mfe_120m"] = (window_high - next_open) / next_open * 100.0
            row["mae_120m"] = (next_open - window_low) / next_open * 100.0

        events.append(row)

    return events


def split_discovery_holdout(events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_symbol[e["symbol"]].append(e)

    discovery: List[Dict[str, Any]] = []
    holdout: List[Dict[str, Any]] = []
    for symbol, rows in by_symbol.items():
        rows.sort(key=lambda x: x["open_time"])
        cut = int(len(rows) * 0.70)
        discovery.extend(rows[:cut])
        holdout.extend(rows[cut:])
    return discovery, holdout


def group(events: List[Dict[str, Any]], state: str, bucket: str) -> List[Dict[str, Any]]:
    return [e for e in events if e["prev_state"] == state and e["bucket"] == bucket]


def pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def print_transition_summary(title: str, events: List[Dict[str, Any]]) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    if not events:
        print("N=0")
        return

    changes = [e for e in events if e["first_change_bar"] is not None]
    print(f"N={len(events)} | any state change by 120m: {pct(len(changes), len(events)):.1f}%")

    for target in ("FLAT", "LONG", "SHORT"):
        xs = [e for e in events if e["first_change_state"] == target]
        if xs:
            print(
                f"  first change -> {target:5}: N={len(xs):3d} "
                f"({pct(len(xs), len(events)):.1f}%)"
            )

    counts = Counter(e["first_change_bar"] for e in changes)
    if counts:
        timing = []
        for b in sorted(counts):
            timing.append(f"{b * 30}m={counts[b]}")
        print("  first-change timing: " + " | ".join(timing))


def print_group_table(events: List[Dict[str, Any]], title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    for state, bucket in (
        ("SHORT", "LOW"), ("SHORT", "MIDDLE"), ("SHORT", "HIGH"),
        ("LONG", "LOW"), ("LONG", "MIDDLE"), ("LONG", "HIGH"),
    ):
        xs = group(events, state, bucket)
        if not xs:
            continue

        changed = [e for e in xs if e["first_change_bar"] is not None]
        to_flat = [e for e in xs if e["first_change_state"] == "FLAT"]
        to_opposite = [
            e for e in xs
            if (state == "SHORT" and e["first_change_state"] == "LONG")
            or (state == "LONG" and e["first_change_state"] == "SHORT")
        ]
        print(
            f"{state:5} + {bucket:6} N={len(xs):3d} | "
            f"change120={pct(len(changed), len(xs)):5.1f}% | "
            f"toFLAT={pct(len(to_flat), len(xs)):5.1f}% | "
            f"toOPP={pct(len(to_opposite), len(xs)):5.1f}% | "
            f"30m={mean(e['ret_30m'] for e in xs):+6.3f}% | "
            f"60m={mean(e['ret_60m'] for e in xs):+6.3f}% | "
            f"120m={mean(e['ret_120m'] for e in xs):+6.3f}%"
        )


def print_short_detail(events: List[Dict[str, Any]], title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    for bucket in ("LOW", "MIDDLE", "HIGH"):
        xs = group(events, "SHORT", bucket)
        if not xs:
            print(f"SHORT + {bucket}: N=0")
            continue

        print(f"\nSHORT + {bucket}: N={len(xs)}")
        first = [e for e in xs if e["first_change_bar"] is not None]
        for target in ("FLAT", "LONG", "SHORT"):
            ys = [e for e in xs if e["first_change_state"] == target]
            if ys:
                bars = [e["first_change_bar"] for e in ys if e["first_change_bar"] is not None]
                avg_min = mean(bars) * 30.0 if bars else 0.0
                print(
                    f"  first -> {target:5}: N={len(ys):3d} "
                    f"{pct(len(ys), len(xs)):.1f}% | avg timing={avg_min:.1f}m"
                )
        if first:
            print(
                f"  any change by 120m: {pct(len(first), len(xs)):.1f}% | "
                f"120m MFE={mean(e['mfe_120m'] for e in xs):.3f}% | "
                f"120m MAE={mean(e['mae_120m'] for e in xs):.3f}%"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()

    print("KISS POST-GAP TRANSITION DIAGNOSTIC")
    print("Research only — no strategy/engine changes")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Session boundary: > {SESSION_GAP_HOURS:.1f}h")
    print("Transition observation: completed 30m / 60m / 120m states")
    print("State definition: KISS 20-bar MA with 0.2% band")

    all_events: List[Dict[str, Any]] = []
    for symbol in args.symbols:
        try:
            rows = fetch_rows(symbol, args.limit)
            events = build_events(symbol, rows)
            all_events.extend(events)
            print(f"{symbol}: candles={len(rows)} session_events={len(events)}")
        except Exception as exc:
            print(f"{symbol}: ERROR: {exc}")

    print_transition_summary("ALL EVENTS", all_events)
    print_group_table(all_events, "ALL GROUPS")
    print_short_detail(all_events, "SHORT TRANSITION DETAIL — FULL SAMPLE")

    discovery, holdout = split_discovery_holdout(all_events)
    print_transition_summary("DISCOVERY — CHRONOLOGICAL 70% PER SYMBOL", discovery)
    print_group_table(discovery, "DISCOVERY GROUPS")
    print_short_detail(discovery, "SHORT TRANSITION DETAIL — DISCOVERY")

    print_transition_summary("HOLDOUT — CHRONOLOGICAL 30% PER SYMBOL", holdout)
    print_group_table(holdout, "HOLDOUT GROUPS")
    print_short_detail(holdout, "SHORT TRANSITION DETAIL — HOLDOUT")

    print("\nKEY QUESTION")
    print("===========")
    print("Does SHORT+LOW show a measurably different rate/timing of SHORT->FLAT or")
    print("SHORT->LONG transitions after the open, compared with SHORT+MIDDLE/HIGH?")
    print("If yes, the next research step is to test whether those transition signals")
    print("can be recognized early enough to improve KISS exits without changing the")
    print("trading engine yet.")
    print("\nNo trading rule is derived from this diagnostic.")


if __name__ == "__main__":
    main()
