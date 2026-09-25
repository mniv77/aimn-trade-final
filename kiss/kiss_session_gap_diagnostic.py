# [FILE: kiss_session_gap_diagnostic.py] — AATA KISS session-boundary / opening-gap research

"""
AATA KISS SESSION-GAP DIAGNOSTIC

Research only.
No API calls.
No trades.
No engine changes.
No DB writes.

Questions:

1. Does the next-session opening gap tend to follow the major trend?
2. Does relative closing position correlate with gap direction/magnitude?
3. Does the late-day transition pathway contain information about the next gap?
4. Do these relationships generalize across symbols?

IMPORTANT:
The diagnostic only uses information available BEFORE the next session opens
when constructing predictors.

Gap definition:

    gap_pct =
        (next_session_open - previous_session_close)
        / previous_session_close * 100

Sessions are detected from the timestamp gaps in the stored 30m RTH data.
We do not hard-code an exchange timezone.

"Relative close position" is measured several ways:

    session_position:
        previous close relative to that session's high/low

    recent_12_position:
        previous close relative to the preceding 12 30m closes

    recent_24_position:
        previous close relative to the preceding 24 30m closes

The diagnostic also records:

    major trend
    RSI
    late-session state path
    whether the opening gap followed or opposed the major trend

This is hypothesis testing, NOT a trading rule.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, median
from typing import Dict, List, Optional, Sequence, Tuple

from db import get_db_connection


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SYMBOLS = [
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "TSLA",
    "SPY",
    "QQQ",
    "META",
    "AMD",
]

TIMEFRAME = "30m"

TREND_WINDOW = 20
TREND_BAND = 0.002

RECENT_12 = 12
RECENT_24 = 24

# A gap is called "large" using each symbol's own absolute-gap distribution.
# This avoids imposing the same raw percentage threshold on every symbol.
LARGE_GAP_PERCENTILE = 75.0

# Session boundary detection.
# A normal 30m RTH sequence has much smaller gaps than the overnight break.
SESSION_GAP_HOURS = 2.0


# ---------------------------------------------------------------------------
# MARKET STATE
# ---------------------------------------------------------------------------

def get_market_state(
    closes: Sequence[float],
    idx: int,
) -> str:
    """Same basic KISS major-state definition used by the research."""

    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    ma = sum(
        closes[idx - TREND_WINDOW:idx]
    ) / TREND_WINDOW

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def rsi_wilder(
    closes: Sequence[float],
    period: int = 14,
) -> List[Optional[float]]:
    """Wilder RSI."""

    result: List[Optional[float]] = [None] * len(closes)

    if len(closes) <= period:
        return result

    gains: List[float] = []
    losses: List[float] = []

    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]

        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        avg_gain = (
            (avg_gain * (period - 1)) + gain
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) + loss
        ) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (
                100.0 / (1.0 + rs)
            )

    return result


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

def load_candles(
    symbol: str,
) -> List[Dict]:
    conn, cursor = get_db_connection()

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s
              AND timeframe=%s
            ORDER BY timestamp ASC
            LIMIT 10000
            """,
            (symbol, TIMEFRAME),
        )

        rows = cursor.fetchall()

        cleaned: List[Dict] = []

        for row in rows:
            ts = row["timestamp"]

            if not isinstance(ts, datetime):
                continue

            try:
                cleaned.append(
                    {
                        "timestamp": ts,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"] or 0),
                    }
                )
            except (TypeError, ValueError):
                continue

        return cleaned

    finally:
        try:
            cursor.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SESSION DETECTION
# ---------------------------------------------------------------------------

def split_sessions(
    rows: Sequence[Dict],
) -> List[List[Dict]]:
    """
    Split the 30m data into contiguous RTH sessions.

    We use timestamp gaps rather than hard-coded UTC market hours.
    """

    if not rows:
        return []

    sessions: List[List[Dict]] = []
    current: List[Dict] = [rows[0]]

    for row in rows[1:]:
        previous = current[-1]

        delta_hours = (
            row["timestamp"] - previous["timestamp"]
        ).total_seconds() / 3600.0

        if delta_hours > SESSION_GAP_HOURS:
            if current:
                sessions.append(current)

            current = [row]
        else:
            current.append(row)

    if current:
        sessions.append(current)

    return sessions


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def safe_position(
    value: float,
    low: float,
    high: float,
) -> Optional[float]:
    spread = high - low

    if spread <= 0:
        return None

    return (
        (value - low) / spread
    ) * 100.0


def percentile(
    values: Sequence[float],
    p: float,
) -> Optional[float]:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    rank = (p / 100.0) * (len(ordered) - 1)

    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)

    fraction = rank - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower])
        * fraction
    )


def direction_from_gap(
    gap_pct: float,
) -> str:
    if gap_pct > 0:
        return "UP"

    if gap_pct < 0:
        return "DOWN"

    return "FLAT"


def follow_or_oppose(
    trend: str,
    gap_direction: str,
) -> str:
    if trend == "LONG":
        if gap_direction == "UP":
            return "FOLLOW"
        if gap_direction == "DOWN":
            return "OPPOSE"

    if trend == "SHORT":
        if gap_direction == "DOWN":
            return "FOLLOW"
        if gap_direction == "UP":
            return "OPPOSE"

    return "NEUTRAL"


def compress_path(
    states: Sequence[str],
) -> str:
    """
    Convert a late-session state sequence into a compact pathway.

    Example:

        SHORT SHORT FLAT LONG LONG
        -> SHORT->FLAT->LONG

    Repeated states are collapsed.
    """

    compressed: List[str] = []

    for state in states:
        if not compressed or state != compressed[-1]:
            compressed.append(state)

    return "->".join(compressed)


# ---------------------------------------------------------------------------
# BUILD SESSION RECORDS
# ---------------------------------------------------------------------------

def build_records(
    symbol: str,
    rows: Sequence[Dict],
) -> List[Dict]:

    sessions = split_sessions(rows)

    if len(sessions) < 2:
        return []

    closes = [
        row["close"]
        for row in rows
    ]

    rsi_values = rsi_wilder(closes)

    # Map timestamp to global row index.
    index_by_timestamp = {
        row["timestamp"]: i
        for i, row in enumerate(rows)
    }

    records: List[Dict] = []

    for session_index in range(len(sessions) - 1):

        previous_session = sessions[session_index]
        next_session = sessions[session_index + 1]

        if not previous_session or not next_session:
            continue

        previous_close_row = previous_session[-1]
        next_open_row = next_session[0]

        previous_close = float(
            previous_close_row["close"]
        )

        next_open = float(
            next_open_row["open"]
        )

        if previous_close <= 0:
            continue

        gap_pct = (
            (next_open - previous_close)
            / previous_close
        ) * 100.0

        gap_direction = direction_from_gap(
            gap_pct
        )

        global_close_index = index_by_timestamp.get(
            previous_close_row["timestamp"]
        )

        if global_close_index is None:
            continue

        trend = get_market_state(
            closes,
            global_close_index,
        )

        rsi = rsi_values[global_close_index]

        # ---------------------------------------------------------------
        # Relative position inside previous session
        # ---------------------------------------------------------------

        session_high = max(
            row["high"]
            for row in previous_session
        )

        session_low = min(
            row["low"]
            for row in previous_session
        )

        session_position = safe_position(
            previous_close,
            session_low,
            session_high,
        )

        # ---------------------------------------------------------------
        # Relative position over recent 12 / 24 closes
        # ---------------------------------------------------------------

        recent_12_values = list(
            closes[
                max(
                    0,
                    global_close_index - RECENT_12 + 1,
                ):
                global_close_index + 1
            ]
        )

        recent_24_values = list(
            closes[
                max(
                    0,
                    global_close_index - RECENT_24 + 1,
                ):
                global_close_index + 1
            ]
        )

        recent_12_position = None
        recent_24_position = None

        if recent_12_values:
            recent_12_position = safe_position(
                previous_close,
                min(recent_12_values),
                max(recent_12_values),
            )

        if recent_24_values:
            recent_24_position = safe_position(
                previous_close,
                min(recent_24_values),
                max(recent_24_values),
            )

        # ---------------------------------------------------------------
        # Late-session state pathway
        # ---------------------------------------------------------------

        late_states: List[str] = []

        late_session_rows = previous_session[-6:]

        for late_row in late_session_rows:
            idx = index_by_timestamp.get(
                late_row["timestamp"]
            )

            if idx is not None:
                late_states.append(
                    get_market_state(
                        closes,
                        idx,
                    )
                )

        pathway = compress_path(
            late_states
        )

        relation = follow_or_oppose(
            trend,
            gap_direction,
        )

        records.append(
            {
                "symbol": symbol,
                "previous_session_date":
                    previous_close_row["timestamp"].date(),
                "previous_close_time":
                    previous_close_row["timestamp"],
                "next_open_time":
                    next_open_row["timestamp"],
                "previous_close":
                    previous_close,
                "next_open":
                    next_open,
                "gap_pct":
                    gap_pct,
                "gap_abs_pct":
                    abs(gap_pct),
                "gap_direction":
                    gap_direction,
                "major_trend":
                    trend,
                "trend_relation":
                    relation,
                "session_position":
                    session_position,
                "recent_12_position":
                    recent_12_position,
                "recent_24_position":
                    recent_24_position,
                "rsi":
                    rsi,
                "late_path":
                    pathway,
                "late_states":
                    " ".join(late_states),
                "previous_session_bars":
                    len(previous_session),
                "next_session_bars":
                    len(next_session),
            }
        )

    return records


# ---------------------------------------------------------------------------
# REPORT HELPERS
# ---------------------------------------------------------------------------

def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"

    return f"{value:+.3f}%"


def print_gap_summary(
    records: Sequence[Dict],
) -> None:

    gaps = [
        float(r["gap_pct"])
        for r in records
    ]

    abs_gaps = [
        abs(float(r["gap_pct"]))
        for r in records
    ]

    if not gaps:
        return

    print()
    print("GAP SUMMARY")
    print("-" * 72)

    print(
        f"Sessions measured: {len(records)}"
    )

    print(
        f"Mean gap:   {mean(gaps):+.3f}%"
    )

    print(
        f"Median gap: {median(gaps):+.3f}%"
    )

    print(
        f"Mean abs gap:   {mean(abs_gaps):.3f}%"
    )

    print(
        f"Median abs gap: {median(abs_gaps):.3f}%"
    )

    up = sum(
        1 for r in records
        if r["gap_direction"] == "UP"
    )

    down = sum(
        1 for r in records
        if r["gap_direction"] == "DOWN"
    )

    flat = sum(
        1 for r in records
        if r["gap_direction"] == "FLAT"
    )

    total = len(records)

    print()
    print(
        f"UP:   {up:4d} "
        f"({100.0 * up / total:.1f}%)"
    )

    print(
        f"DOWN: {down:4d} "
        f"({100.0 * down / total:.1f}%)"
    )

    print(
        f"FLAT: {flat:4d} "
        f"({100.0 * flat / total:.1f}%)"
    )


def print_trend_analysis(
    records: Sequence[Dict],
) -> None:

    print()
    print("1. DOES THE OPENING GAP FOLLOW THE MAJOR TREND?")
    print("-" * 72)

    for trend in ["LONG", "SHORT", "FLAT"]:

        subset = [
            r for r in records
            if r["major_trend"] == trend
        ]

        if not subset:
            continue

        follow = sum(
            1 for r in subset
            if r["trend_relation"] == "FOLLOW"
        )

        oppose = sum(
            1 for r in subset
            if r["trend_relation"] == "OPPOSE"
        )

        neutral = len(subset) - follow - oppose

        print(
            f"{trend:5s} "
            f"N={len(subset):3d} | "
            f"FOLLOW={follow:3d} "
            f"({100.0 * follow / len(subset):5.1f}%) | "
            f"OPPOSE={oppose:3d} "
            f"({100.0 * oppose / len(subset):5.1f}%) | "
            f"NEUTRAL={neutral:3d}"
        )

        follow_gaps = [
            abs(float(r["gap_pct"]))
            for r in subset
            if r["trend_relation"] == "FOLLOW"
        ]

        oppose_gaps = [
            abs(float(r["gap_pct"]))
            for r in subset
            if r["trend_relation"] == "OPPOSE"
        ]

        if follow_gaps:
            print(
                f"      follow mean abs gap: "
                f"{mean(follow_gaps):.3f}%"
            )

        if oppose_gaps:
            print(
                f"      oppose mean abs gap: "
                f"{mean(oppose_gaps):.3f}%"
            )


def position_bucket(
    value: Optional[float],
) -> str:

    if value is None:
        return "UNKNOWN"

    if value < 20:
        return "0-20"
    if value < 40:
        return "20-40"
    if value < 60:
        return "40-60"
    if value < 80:
        return "60-80"

    return "80-100"


def print_relative_position_analysis(
    records: Sequence[Dict],
) -> None:

    print()
    print(
        "2. DOES RELATIVE CLOSE POSITION "
        "CORRELATE WITH THE NEXT GAP?"
    )
    print("-" * 72)

    for field, label in [
        ("session_position", "Previous session position"),
        ("recent_12_position", "Recent 12-bar position"),
        ("recent_24_position", "Recent 24-bar position"),
    ]:

        print()
        print(label)

        buckets = defaultdict(list)

        for record in records:
            bucket = position_bucket(
                record[field]
            )

            if bucket != "UNKNOWN":
                buckets[bucket].append(record)

        for bucket in [
            "0-20",
            "20-40",
            "40-60",
            "60-80",
            "80-100",
        ]:

            subset = buckets.get(bucket, [])

            if not subset:
                continue

            up = sum(
                1 for r in subset
                if r["gap_direction"] == "UP"
            )

            down = sum(
                1 for r in subset
                if r["gap_direction"] == "DOWN"
            )

            avg_gap = mean(
                float(r["gap_pct"])
                for r in subset
            )

            avg_abs = mean(
                abs(float(r["gap_pct"]))
                for r in subset
            )

            print(
                f"  {bucket:>5s} | "
                f"N={len(subset):3d} | "
                f"UP={100.0 * up / len(subset):5.1f}% | "
                f"DOWN={100.0 * down / len(subset):5.1f}% | "
                f"mean gap={avg_gap:+.3f}% | "
                f"mean abs={avg_abs:.3f}%"
            )


def print_pathway_analysis(
    records: Sequence[Dict],
) -> None:

    print()
    print(
        "3. DOES THE LATE-DAY TRANSITION PATHWAY "
        "CONTAIN INFORMATION?"
    )
    print("-" * 72)

    grouped = defaultdict(list)

    for record in records:
        grouped[record["late_path"]].append(
            record
        )

    ranked = sorted(
        grouped.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )

    for pathway, subset in ranked[:20]:

        if len(subset) < 2:
            continue

        up = sum(
            1 for r in subset
            if r["gap_direction"] == "UP"
        )

        down = sum(
            1 for r in subset
            if r["gap_direction"] == "DOWN"
        )

        avg_gap = mean(
            float(r["gap_pct"])
            for r in subset
        )

        avg_abs = mean(
            abs(float(r["gap_pct"]))
            for r in subset
        )

        print(
            f"{pathway:35s} | "
            f"N={len(subset):3d} | "
            f"UP={100.0 * up / len(subset):5.1f}% | "
            f"DOWN={100.0 * down / len(subset):5.1f}% | "
            f"mean={avg_gap:+.3f}% | "
            f"abs={avg_abs:.3f}%"
        )


def print_large_gap_analysis(
    records: Sequence[Dict],
) -> None:

    print()
    print(
        "4. LARGE-JUMP ANALYSIS"
    )
    print("-" * 72)

    abs_gaps = [
        abs(float(r["gap_pct"]))
        for r in records
    ]

    threshold = percentile(
        abs_gaps,
        LARGE_GAP_PERCENTILE,
    )

    if threshold is None:
        return

    large = [
        r for r in records
        if abs(float(r["gap_pct"])) >= threshold
    ]

    print(
        f"Large-gap threshold "
        f"(top {100.0 - LARGE_GAP_PERCENTILE:.0f}%): "
        f"{threshold:.3f}%"
    )

    print(
        f"Large-gap sessions: "
        f"{len(large)} / {len(records)}"
    )

    print()

    if not large:
        return

    follow = sum(
        1 for r in large
        if r["trend_relation"] == "FOLLOW"
    )

    oppose = sum(
        1 for r in large
        if r["trend_relation"] == "OPPOSE"
    )

    directional = follow + oppose

    if directional:
        print(
            f"Among large gaps with a directional trend: "
            f"FOLLOW={100.0 * follow / directional:.1f}% | "
            f"OPPOSE={100.0 * oppose / directional:.1f}%"
        )

    print()

    # Relative position of large gaps.
    positions = [
        r["session_position"]
        for r in large
        if r["session_position"] is not None
    ]

    if positions:
        print(
            f"Large-gap average session position: "
            f"{mean(positions):.1f}/100"
        )

        print(
            f"Large-gap median session position: "
            f"{median(positions):.1f}/100"
        )


def print_symbol_summary(
    all_records: Dict[str, List[Dict]],
) -> None:

    print()
    print(
        "5. CROSS-SYMBOL SUMMARY"
    )
    print("-" * 72)

    print(
        f"{'SYMBOL':<8} "
        f"{'N':>5} "
        f"{'AVG GAP':>10} "
        f"{'AVG ABS':>10} "
        f"{'FOLLOW':>9}"
    )

    print("-" * 72)

    for symbol in SYMBOLS:

        records = all_records.get(
            symbol,
            [],
        )

        if not records:
            continue

        avg_gap = mean(
            float(r["gap_pct"])
            for r in records
        )

        avg_abs = mean(
            abs(float(r["gap_pct"]))
            for r in records
        )

        directional = [
            r for r in records
            if r["trend_relation"]
            in ("FOLLOW", "OPPOSE")
        ]

        if directional:
            follow = sum(
                1 for r in directional
                if r["trend_relation"] == "FOLLOW"
            )

            follow_pct = (
                100.0 * follow / len(directional)
            )
        else:
            follow_pct = None

        follow_text = (
            f"{follow_pct:.1f}%"
            if follow_pct is not None
            else "n/a"
        )

        print(
            f"{symbol:<8} "
            f"{len(records):5d} "
            f"{avg_gap:+9.3f}% "
            f"{avg_abs:9.3f}% "
            f"{follow_text:>9}"
        )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:

    print()
    print("=" * 72)
    print(
        "AATA KISS SESSION-GAP DIAGNOSTIC"
    )
    print(
        "Research only — no API, no trades, "
        "no engine changes, no DB writes"
    )
    print("=" * 72)

    print()
    print(
        "Questions:"
    )
    print(
        "  1. Does the next opening gap follow the major trend?"
    )
    print(
        "  2. Does relative close position matter?"
    )
    print(
        "  3. Does the late-day pathway matter?"
    )
    print(
        "  4. Does it generalize across symbols?"
    )

    all_records: Dict[str, List[Dict]] = {}

    combined: List[Dict] = []

    for symbol in SYMBOLS:

        print()
        print(
            f"--- {symbol} ---"
        )

        rows = load_candles(symbol)

        if not rows:
            print(
                "No 30m data."
            )
            continue

        sessions = split_sessions(rows)

        records = build_records(
            symbol,
            rows,
        )

        all_records[symbol] = records

        combined.extend(records)

        print(
            f"30m candles: {len(rows)}"
        )

        print(
            f"Detected sessions: {len(sessions)}"
        )

        print(
            f"Overnight gaps measured: {len(records)}"
        )

        if records:
            print_gap_summary(records)
            print_trend_analysis(records)
            print_relative_position_analysis(records)
            print_pathway_analysis(records)
            print_large_gap_analysis(records)

    print()
    print("=" * 72)
    print(
        "COMBINED CROSS-SYMBOL RESULTS"
    )
    print("=" * 72)

    if not combined:
        print(
            "No usable session pairs found."
        )
        return

    print(
        f"Symbols tested: "
        f"{len(all_records)}"
    )

    print(
        f"Total session pairs: "
        f"{len(combined)}"
    )

    print_gap_summary(combined)
    print_trend_analysis(combined)
    print_relative_position_analysis(combined)
    print_pathway_analysis(combined)
    print_large_gap_analysis(combined)
    print_symbol_summary(all_records)

    print()
    print("=" * 72)
    print(
        "RESEARCH CONCLUSION"
    )
    print("=" * 72)

    print(
        "These results are hypotheses/evidence only."
    )

    print(
        "No trading rule has been changed."
    )

    print(
        "A relationship is interesting only if it survives "
        "cross-symbol testing and later out-of-sample testing."
    )


if __name__ == "__main__":
    main()