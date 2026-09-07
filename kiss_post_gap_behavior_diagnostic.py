"""Research-only diagnostic: what happens after the next session opens?

Purpose
-------
The previous KISS research found a direction-specific session-gap asymmetry:

    SHORT + relatively LOW  -> next opening gap was often UP
    SHORT + relatively HIGH -> next opening gap was more DOWN-biased

This script deliberately does NOT change KISS/V5 or trading logic. It asks the
next question only:

    Is the effect just an opening-gap effect, or does price behavior after the
    open continue in a useful direction?

For every session boundary (> 2 hours between 30m candles), the script records:
    previous close -> next open gap
    next-open -> close after 30m / 60m / 120m
    favorable and adverse excursion over those windows

The main comparison is:
    SHORT+LOW vs SHORT+HIGH
and the LONG groups are also shown for symmetry.

Relative position uses the previous 12 completed 30m closes:
    LOW    <= 20th percentile of recent range
    HIGH   >= 80th percentile of recent range
    MIDDLE otherwise

Major state uses the same KISS 20-bar / 0.2% band definition as the engine.

Research only. No orders, no DB writes, no strategy changes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
REL_WINDOW = 12
SESSION_GAP_HOURS = 2.0
FORWARD_BARS = (1, 2, 4)  # 30m, 60m, 120m
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
    if idx < TREND_WINDOW:
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def relative_position(closes: Sequence[float], idx: int) -> Optional[float]:
    """0..100 position of closes[idx] inside the prior REL_WINDOW range."""
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
    finally:
        conn.close()


def build_events(symbol: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(rows) < TREND_WINDOW + REL_WINDOW + max(FORWARD_BARS) + 1:
        return []

    ts = [_ts(r["timestamp"]) for r in rows]
    opens = [_num(r["open"]) for r in rows]
    highs = [_num(r["high"]) for r in rows]
    lows = [_num(r["low"]) for r in rows]
    closes = [_num(r["close"]) for r in rows]

    events: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + REL_WINDOW, len(rows) - max(FORWARD_BARS)):
        # A session boundary is the gap from the previous completed 30m candle
        # to the next candle's open. The current candle i is the first candle
        # of the new session; i-1 is the final candle of the prior session.
        gap_hours = (ts[i] - ts[i - 1]).total_seconds() / 3600.0
        if gap_hours <= SESSION_GAP_HOURS:
            continue

        prev_close = closes[i - 1]
        next_open = opens[i]
        if prev_close <= 0 or next_open <= 0:
            continue

        # State is evaluated at the previous completed close, using only data
        # available before the gap.
        state = market_state(closes, i - 1)
        pos = relative_position(closes, i - 1)
        bucket = rel_bucket(pos)
        if state not in {"LONG", "SHORT"} or bucket == "UNKNOWN":
            continue

        gap_pct = (next_open / prev_close - 1.0) * 100.0
        row: Dict[str, Any] = {
            "symbol": symbol,
            "prev_time": ts[i - 1],
            "open_time": ts[i],
            "gap_hours": gap_hours,
            "state": state,
            "relative_position": pos,
            "bucket": bucket,
            "prev_close": prev_close,
            "next_open": next_open,
            "gap_pct": gap_pct,
        }

        for bars in FORWARD_BARS:
            end = i + bars  # include candles i .. i+bars-1
            window_high = max(highs[i:end])
            window_low = min(lows[i:end])
            end_close = closes[end - 1]
            close_ret = (end_close / next_open - 1.0) * 100.0
            if state == "SHORT":
                mfe = (next_open - window_low) / next_open * 100.0
                mae = (window_high - next_open) / next_open * 100.0
            else:
                mfe = (window_high - next_open) / next_open * 100.0
                mae = (next_open - window_low) / next_open * 100.0

            row[f"close_{bars}m_pct"] = close_ret
            row[f"mfe_{bars}m_pct"] = mfe
            row[f"mae_{bars}m_pct"] = mae

        row["gap_direction"] = "UP" if gap_pct > 0.05 else "DOWN" if gap_pct < -0.05 else "FLAT"
        events.append(row)

    return events


def pct(xs: List[float]) -> float:
    return 100.0 * sum(1 for x in xs if x > 0) / len(xs) if xs else 0.0


def summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not events:
        return {"n": 0}
    out: Dict[str, Any] = {"n": len(events)}
    gaps = [e["gap_pct"] for e in events]
    out["gap_up_pct"] = pct(gaps)
    out["gap_mean"] = mean(gaps)
    out["gap_median"] = median(gaps)
    for bars in FORWARD_BARS:
        cr = [e[f"close_{bars}m_pct"] for e in events]
        mfe = [e[f"mfe_{bars}m_pct"] for e in events]
        mae = [e[f"mae_{bars}m_pct"] for e in events]
        out[f"close_{bars}m_up_pct"] = pct(cr)
        out[f"close_{bars}m_mean"] = mean(cr)
        out[f"close_{bars}m_median"] = median(cr)
        out[f"mfe_{bars}m_mean"] = mean(mfe)
        out[f"mae_{bars}m_mean"] = mean(mae)
    return out


def split_discovery_holdout(events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Chronological 70/30 split within each symbol, matching prior research."""
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


def print_summary(title: str, events: List[Dict[str, Any]]) -> None:
    s = summary(events)
    print(f"\n{title}")
    print("-" * len(title))
    if not events:
        print("N=0")
        return
    print(
        f"N={s['n']} | GAP UP {s['gap_up_pct']:.1f}% | "
        f"gap mean {s['gap_mean']:+.3f}% | median {s['gap_median']:+.3f}%"
    )
    for bars in FORWARD_BARS:
        print(
            f"  {bars*30:>3}m after open: "
            f"close-up {s[f'close_{bars}m_up_pct']:.1f}% | "
            f"mean {s[f'close_{bars}m_mean']:+.3f}% | "
            f"median {s[f'close_{bars}m_median']:+.3f}% | "
            f"MFE {s[f'mfe_{bars}m_mean']:.3f}% | "
            f"MAE {s[f'mae_{bars}m_mean']:.3f}%"
        )


def print_group_table(events: List[Dict[str, Any]], title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    groups = [
        ("SHORT", "LOW"),
        ("SHORT", "MIDDLE"),
        ("SHORT", "HIGH"),
        ("LONG", "LOW"),
        ("LONG", "MIDDLE"),
        ("LONG", "HIGH"),
    ]
    for state, bucket in groups:
        group = [e for e in events if e["state"] == state and e["bucket"] == bucket]
        if not group:
            continue
        s = summary(group)
        print(
            f"{state:5} + {bucket:6} N={s['n']:3d} | "
            f"gapUP={s['gap_up_pct']:5.1f}% mean={s['gap_mean']:+6.3f}% | "
            f"30m={s['close_1m_mean']:+6.3f}% | "
            f"60m={s['close_2m_mean']:+6.3f}% | "
            f"120m={s['close_4m_mean']:+6.3f}%"
        )


def print_short_comparison(events: List[Dict[str, Any]], title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    for bucket in ("LOW", "HIGH"):
        group = [e for e in events if e["state"] == "SHORT" and e["bucket"] == bucket]
        if not group:
            print(f"SHORT + {bucket}: N=0")
            continue
        s = summary(group)
        print(
            f"SHORT + {bucket}: N={s['n']} | gapUP {s['gap_up_pct']:.1f}% "
            f"gap {s['gap_mean']:+.3f}% | "
            f"30m {s['close_1m_mean']:+.3f}% "
            f"60m {s['close_2m_mean']:+.3f}% "
            f"120m {s['close_4m_mean']:+.3f}%"
        )
        for bars in FORWARD_BARS:
            print(
                f"    {bars*30:>3}m: MFE {s[f'mfe_{bars}m_mean']:.3f}% "
                f"MAE {s[f'mae_{bars}m_mean']:.3f}%"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()

    all_events: List[Dict[str, Any]] = []
    print("KISS POST-GAP BEHAVIOR DIAGNOSTIC")
    print("Research only — no strategy/engine changes")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Session boundary: > {SESSION_GAP_HOURS:.1f}h")
    print("Forward windows: 30m / 60m / 120m")

    for symbol in args.symbols:
        try:
            rows = fetch_rows(symbol, args.limit)
            events = build_events(symbol, rows)
            all_events.extend(events)
            print(f"{symbol}: candles={len(rows)} session_events={len(events)}")
        except Exception as exc:
            print(f"{symbol}: ERROR: {exc}")

    print_summary("ALL DIRECTIONAL SESSION EVENTS", all_events)
    print_group_table(all_events, "ALL GROUPS")
    print_short_comparison(all_events, "SHORT LOW vs SHORT HIGH — FULL SAMPLE")

    discovery, holdout = split_discovery_holdout(all_events)
    print_group_table(discovery, "DISCOVERY — CHRONOLOGICAL 70% PER SYMBOL")
    print_short_comparison(discovery, "SHORT LOW vs SHORT HIGH — DISCOVERY")

    print_group_table(holdout, "HOLDOUT — CHRONOLOGICAL 30% PER SYMBOL")
    print_short_comparison(holdout, "SHORT LOW vs SHORT HIGH — HOLDOUT")

    print("\nINTERPRETATION CHECK")
    print("===================")
    print("The key test is whether SHORT+LOW remains meaningfully different from SHORT+HIGH")
    print("at 30m/60m/120m after the open, not merely at the opening gap.")
    print("Do not convert any result here into a trading rule without separate validation.")


if __name__ == "__main__":
    main()
