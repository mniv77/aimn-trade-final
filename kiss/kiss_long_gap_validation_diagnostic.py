# [FILE: kiss_long_gap_validation_diagnostic.py] — LONG relative-position session-gap validation research

"""
AATA KISS — LONG Relative-Position Gap Validation Diagnostic

PURPOSE
-------
Validate one specific hypothesis discovered during the earlier
session-gap research:

    MAJOR TREND = SHORT
    +
    RELATIVE PRICE POSITION = LOW or HIGH
    ->
    NEXT SESSION OPENING GAP

This is a research-only experiment.

IMPORTANT
---------
NO API
NO TRADES
NO ENGINE CHANGES
NO DB WRITES

The database is READ ONLY.

The diagnostic deliberately focuses on LONG only so that we do not
mix several hypotheses together.

PRIMARY TESTS
-------------
1. ALL LONG sessions
2. SHORT + recent-12 position 0-20%  = LOW
3. SHORT + recent-12 position 80-100% = HIGH

For each group we measure:
- sample size
- UP/DOWN count
- UP percentage
- mean gap
- median gap
- mean absolute gap
- median absolute gap

VALIDATION
----------
For every symbol:
- chronological discovery period
- chronological holdout period

The pooled discovery period is used to describe the relationship.
The holdout period is NOT used to choose the hypothesis.

The purpose is to see whether the relationship survives on later data.

RELATIVE POSITION
-----------------
recent-12 position is:

    (close - recent_12_low) /
    (recent_12_high - recent_12_low)

expressed as 0-100%.

SHORT TREND
-----------
Uses the same KISS major-state definition:

    TREND_WINDOW = 20
    TREND_BAND   = 0.2%

SESSION GAP
-----------
Previous regular session close -> next regular session open.

A session boundary is detected when the timestamp gap is greater
than two hours.

This diagnostic does not hard-code a timezone.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from db import get_db_connection


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

TREND_WINDOW = 20
TREND_BAND = 0.002

RECENT_WINDOW = 12

# Relative-position buckets.
LOW_MAX = 20.0
HIGH_MIN = 80.0

# Session boundary.
SESSION_GAP_HOURS = 2.0

# Chronological validation split.
#
# 70% of each symbol's usable session pairs:
# discovery
#
# 30%:
# holdout
#
# We do NOT tune the hypothesis using the holdout.
DISCOVERY_FRACTION = 0.70

# Minimum sample size for displaying a per-symbol bucket.
MIN_SYMBOL_N = 4

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


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SessionPair:
    symbol: str
    previous_close_time: datetime
    next_open_time: datetime

    previous_close: float
    next_open: float

    gap_pct: float

    major_state: str

    session_position_pct: Optional[float]
    recent12_position_pct: Optional[float]

    previous_pathway: str


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

def load_30m_candles(symbol: str) -> List[Candle]:
    """
    Load 30m candles from the existing candles table.

    READ ONLY.
    """

    conn, cursor = get_db_connection()

    try:
        cursor.execute(
            """
            SELECT
                timestamp,
                open,
                high,
                low,
                close,
                volume
            FROM candles
            WHERE symbol=%s
              AND timeframe=%s
            ORDER BY timestamp ASC
            """,
            (symbol, "30m"),
        )

        rows = cursor.fetchall()

    finally:
        try:
            cursor.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass

    candles: List[Candle] = []

    for row in rows:
        try:
            candles.append(
                Candle(
                    timestamp=row["timestamp"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"] or 0.0),
                )
            )
        except Exception:
            continue

    return candles


# ---------------------------------------------------------------------------
# KISS STATE
# ---------------------------------------------------------------------------

def get_market_state(
    closes: Sequence[float],
    idx: int,
) -> str:
    """
    Same basic KISS major-state classifier used by the research.

    IMPORTANT:
    The moving average uses candles BEFORE idx.
    """

    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    window = closes[idx - TREND_WINDOW:idx]

    if not window:
        return "FLAT"

    ma = sum(window) / len(window)

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def build_states(
    candles: Sequence[Candle],
) -> List[str]:
    closes = [c.close for c in candles]

    return [
        get_market_state(closes, i)
        for i in range(len(candles))
    ]


# ---------------------------------------------------------------------------
# RELATIVE POSITION
# ---------------------------------------------------------------------------

def relative_position(
    closes: Sequence[float],
    idx: int,
    window: int,
) -> Optional[float]:
    """
    Return current close's relative position within the previous
    `window` candles.

    0   = at recent low
    100 = at recent high

    The current candle is included in the range.

    This is intentionally a relative measure, not an absolute price.
    """

    if idx < window - 1:
        return None

    values = closes[idx - window + 1:idx + 1]

    if not values:
        return None

    lo = min(values)
    hi = max(values)

    if hi <= lo:
        return 50.0

    value = (closes[idx] - lo) / (hi - lo)

    return value * 100.0


def session_position(
    candles: Sequence[Candle],
    start_idx: int,
    end_idx: int,
) -> Optional[float]:
    """
    Position of the previous session's closing price within that
    session's high/low range.

    0   = session low
    100 = session high
    """

    if start_idx < 0 or end_idx >= len(candles):
        return None

    session = candles[start_idx:end_idx + 1]

    if not session:
        return None

    lo = min(c.low for c in session)
    hi = max(c.high for c in session)

    close = candles[end_idx].close

    if hi <= lo:
        return 50.0

    return ((close - lo) / (hi - lo)) * 100.0


# ---------------------------------------------------------------------------
# PATHWAY
# ---------------------------------------------------------------------------

def build_pathway(
    states: Sequence[str],
    end_idx: int,
    bars: int = 6,
) -> str:
    """
    Compact description of the last few KISS states before the
    session ended.

    Repeated states are compressed.

    Example:

        SHORT -> FLAT -> LONG
    """

    start = max(0, end_idx - bars + 1)

    raw = list(states[start:end_idx + 1])

    if not raw:
        return "UNKNOWN"

    compressed: List[str] = []

    for state in raw:
        if not compressed or compressed[-1] != state:
            compressed.append(state)

    return "->".join(compressed)


# ---------------------------------------------------------------------------
# SESSION DETECTION
# ---------------------------------------------------------------------------

def detect_sessions(
    candles: Sequence[Candle],
) -> List[Tuple[int, int]]:
    """
    Detect contiguous regular-market sessions.

    A gap > SESSION_GAP_HOURS starts a new session.

    Returns:
        [(start_idx, end_idx), ...]
    """

    if not candles:
        return []

    sessions: List[Tuple[int, int]] = []

    start_idx = 0

    for i in range(1, len(candles)):
        previous = candles[i - 1].timestamp
        current = candles[i].timestamp

        try:
            gap_hours = (
                current - previous
            ).total_seconds() / 3600.0
        except Exception:
            continue

        if gap_hours > SESSION_GAP_HOURS:
            sessions.append((start_idx, i - 1))
            start_idx = i

    sessions.append((start_idx, len(candles) - 1))

    return sessions


# ---------------------------------------------------------------------------
# SESSION PAIRS
# ---------------------------------------------------------------------------

def build_session_pairs(
    symbol: str,
    candles: Sequence[Candle],
) -> List[SessionPair]:
    """
    Build:

        previous session close
        ->
        next session open
    """

    if len(candles) < TREND_WINDOW + RECENT_WINDOW:
        return []

    states = build_states(candles)
    closes = [c.close for c in candles]

    sessions = detect_sessions(candles)

    pairs: List[SessionPair] = []

    for session_i in range(len(sessions) - 1):
        prev_start, prev_end = sessions[session_i]
        next_start, next_end = sessions[session_i + 1]

        if prev_end < TREND_WINDOW:
            continue

        previous_close = candles[prev_end].close
        next_open = candles[next_start].open

        if previous_close <= 0:
            continue

        gap_pct = (
            (next_open - previous_close)
            / previous_close
            * 100.0
        )

        major_state = states[prev_end]

        if major_state != "LONG":
            continue

        recent12 = relative_position(
            closes,
            prev_end,
            RECENT_WINDOW,
        )

        if recent12 is None:
            continue

        sess_pos = session_position(
            candles,
            prev_start,
            prev_end,
        )

        pathway = build_pathway(
            states,
            prev_end,
            bars=6,
        )

        pairs.append(
            SessionPair(
                symbol=symbol,
                previous_close_time=candles[prev_end].timestamp,
                next_open_time=candles[next_start].timestamp,
                previous_close=previous_close,
                next_open=next_open,
                gap_pct=gap_pct,
                major_state=major_state,
                session_position_pct=sess_pos,
                recent12_position_pct=recent12,
                previous_pathway=pathway,
            )
        )

    return pairs


# ---------------------------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------------------------

def mean_or_zero(values: Sequence[float]) -> float:
    if not values:
        return 0.0

    return statistics.mean(values)


def median_or_zero(values: Sequence[float]) -> float:
    if not values:
        return 0.0

    return statistics.median(values)


def pct(value: float) -> str:
    return f"{value:.1f}%"


def classify_relative_position(
    value: Optional[float],
) -> str:
    if value is None:
        return "UNKNOWN"

    if value <= LOW_MAX:
        return "LOW"

    if value >= HIGH_MIN:
        return "HIGH"

    return "MIDDLE"


def group_statistics(
    rows: Sequence[SessionPair],
) -> Dict[str, float]:
    gaps = [r.gap_pct for r in rows]

    up = sum(1 for x in gaps if x > 0)
    down = sum(1 for x in gaps if x < 0)
    flat = sum(1 for x in gaps if x == 0)

    n = len(gaps)

    up_pct = (
        (up / n) * 100.0
        if n
        else 0.0
    )

    down_pct = (
        (down / n) * 100.0
        if n
        else 0.0
    )

    abs_gaps = [abs(x) for x in gaps]

    return {
        "n": float(n),
        "up": float(up),
        "down": float(down),
        "flat": float(flat),
        "up_pct": up_pct,
        "down_pct": down_pct,
        "mean_gap": mean_or_zero(gaps),
        "median_gap": median_or_zero(gaps),
        "mean_abs": mean_or_zero(abs_gaps),
        "median_abs": median_or_zero(abs_gaps),
    }


def print_group(
    label: str,
    rows: Sequence[SessionPair],
    indent: str = "",
) -> None:
    stats = group_statistics(rows)

    print(
        f"{indent}{label:<28}"
        f"N={int(stats['n']):>4} "
        f"UP={pct(stats['up_pct']):>7} "
        f"DOWN={pct(stats['down_pct']):>7} "
        f"mean={stats['mean_gap']:+.3f}% "
        f"median={stats['median_gap']:+.3f}% "
        f"abs={stats['mean_abs']:.3f}%"
    )


# ---------------------------------------------------------------------------
# DISCOVERY / HOLDOUT SPLIT
# ---------------------------------------------------------------------------

def chronological_split(
    rows: Sequence[SessionPair],
) -> Tuple[List[SessionPair], List[SessionPair]]:
    ordered = sorted(
        rows,
        key=lambda r: r.next_open_time,
    )

    n = len(ordered)

    if n < 2:
        return list(ordered), []

    split_idx = int(
        math.floor(n * DISCOVERY_FRACTION)
    )

    split_idx = max(1, split_idx)
    split_idx = min(n - 1, split_idx)

    return (
        ordered[:split_idx],
        ordered[split_idx:],
    )


# ---------------------------------------------------------------------------
# DISCOVERY ANALYSIS
# ---------------------------------------------------------------------------

def analyze_discovery(
    rows: Sequence[SessionPair],
) -> None:
    print()
    print("=" * 110)
    print("LONG RELATIVE-POSITION — DISCOVERY DATA")
    print("=" * 110)

    print()
    print("HYPOTHESIS:")
    print(
        "When the major KISS trend is LONG, relative price position "
        "may contain information about the next session opening gap."
    )

    print()
    print("GROUPS:")
    print_group("ALL LONG", rows)

    low_rows = [
        r
        for r in rows
        if r.recent12_position_pct is not None
        and r.recent12_position_pct <= LOW_MAX
    ]

    high_rows = [
        r
        for r in rows
        if r.recent12_position_pct is not None
        and r.recent12_position_pct >= HIGH_MIN
    ]

    middle_rows = [
        r
        for r in rows
        if r.recent12_position_pct is not None
        and LOW_MAX < r.recent12_position_pct < HIGH_MIN
    ]

    print_group(
        "LONG + LOW 0-20",
        low_rows,
    )

    print_group(
        "LONG + MIDDLE 20-80",
        middle_rows,
    )

    print_group(
        "LONG + HIGH 80-100",
        high_rows,
    )

    print()
    print("LOW vs HIGH:")
    print_group(
        "LOW",
        low_rows,
        indent="  ",
    )
    print_group(
        "HIGH",
        high_rows,
        indent="  ",
    )


# ---------------------------------------------------------------------------
# SYMBOL ANALYSIS
# ---------------------------------------------------------------------------

def analyze_per_symbol(
    symbol_rows: Dict[str, List[SessionPair]],
) -> None:
    print()
    print("=" * 110)
    print("LONG RELATIVE-POSITION — PER SYMBOL")
    print("=" * 110)

    print()
    print(
        f"{'SYMBOL':<8}"
        f"{'ALL':>8}"
        f"{'LOW':>8}"
        f"{'LOW UP':>10}"
        f"{'HIGH':>8}"
        f"{'HIGH UP':>10}"
        f"{'LOW AVG':>11}"
        f"{'HIGH AVG':>11}"
    )

    print("-" * 110)

    for symbol in SYMBOLS:
        rows = symbol_rows.get(symbol, [])

        if not rows:
            continue

        low_rows = [
            r
            for r in rows
            if r.recent12_position_pct is not None
            and r.recent12_position_pct <= LOW_MAX
        ]

        high_rows = [
            r
            for r in rows
            if r.recent12_position_pct is not None
            and r.recent12_position_pct >= HIGH_MIN
        ]

        if len(low_rows) < MIN_SYMBOL_N and len(high_rows) < MIN_SYMBOL_N:
            continue

        all_stats = group_statistics(rows)
        low_stats = group_statistics(low_rows)
        high_stats = group_statistics(high_rows)

        print(
            f"{symbol:<8}"
            f"{int(all_stats['n']):>8}"
            f"{int(low_stats['n']):>8}"
            f"{low_stats['up_pct']:>9.1f}%"
            f"{int(high_stats['n']):>8}"
            f"{high_stats['up_pct']:>9.1f}%"
            f"{low_stats['mean_gap']:>+10.3f}%"
            f"{high_stats['mean_gap']:>+10.3f}%"
        )


# ---------------------------------------------------------------------------
# HOLDOUT ANALYSIS
# ---------------------------------------------------------------------------

def analyze_holdout(
    symbol_splits: Dict[
        str,
        Tuple[List[SessionPair], List[SessionPair]],
    ],
) -> None:
    print()
    print("=" * 110)
    print("LONG RELATIVE-POSITION — OUT-OF-SAMPLE HOLDOUT")
    print("=" * 110)

    print()
    print(
        "The holdout is the later 30% of each symbol's chronological "
        "session pairs."
    )

    print(
        "The LOW/HIGH hypothesis was defined before looking at this "
        "holdout."
    )

    print()

    combined_holdout: List[SessionPair] = []

    for symbol in SYMBOLS:
        split = symbol_splits.get(symbol)

        if not split:
            continue

        _, holdout = split

        if not holdout:
            continue

        combined_holdout.extend(holdout)

        low_rows = [
            r
            for r in holdout
            if r.recent12_position_pct is not None
            and r.recent12_position_pct <= LOW_MAX
        ]

        high_rows = [
            r
            for r in holdout
            if r.recent12_position_pct is not None
            and r.recent12_position_pct >= HIGH_MIN
        ]

        print(
            f"{symbol}: holdout N={len(holdout)}"
        )

        print_group(
            "ALL LONG",
            holdout,
            indent="  ",
        )

        print_group(
            "LONG + LOW",
            low_rows,
            indent="  ",
        )

        print_group(
            "LONG + HIGH",
            high_rows,
            indent="  ",
        )

        print()

    print("-" * 110)
    print("COMBINED HOLDOUT")
    print()

    print_group(
        "ALL LONG",
        combined_holdout,
    )

    low_combined = [
        r
        for r in combined_holdout
        if r.recent12_position_pct is not None
        and r.recent12_position_pct <= LOW_MAX
    ]

    high_combined = [
        r
        for r in combined_holdout
        if r.recent12_position_pct is not None
        and r.recent12_position_pct >= HIGH_MIN
    ]

    print_group(
        "LONG + LOW",
        low_combined,
    )

    print_group(
        "LONG + HIGH",
        high_combined,
    )


# ---------------------------------------------------------------------------
# EXTREME GAP ANALYSIS
# ---------------------------------------------------------------------------

def analyze_gap_magnitude(
    rows: Sequence[SessionPair],
) -> None:
    print()
    print("=" * 110)
    print("LONG RELATIVE-POSITION — GAP MAGNITUDE")
    print("=" * 110)

    low_rows = [
        r
        for r in rows
        if r.recent12_position_pct is not None
        and r.recent12_position_pct <= LOW_MAX
    ]

    high_rows = [
        r
        for r in rows
        if r.recent12_position_pct is not None
        and r.recent12_position_pct >= HIGH_MIN
    ]

    def magnitude_stats(
        label: str,
        group: Sequence[SessionPair],
    ) -> None:
        magnitudes = sorted(
            [abs(r.gap_pct) for r in group]
        )

        if not magnitudes:
            print(
                f"{label:<25} N=0"
            )
            return

        p50 = statistics.median(magnitudes)

        p75 = magnitudes[
            min(
                len(magnitudes) - 1,
                int(len(magnitudes) * 0.75),
            )
        ]

        p90 = magnitudes[
            min(
                len(magnitudes) - 1,
                int(len(magnitudes) * 0.90),
            )
        ]

        print(
            f"{label:<25}"
            f"N={len(group):>4} "
            f"mean_abs={statistics.mean(magnitudes):.3f}% "
            f"median_abs={p50:.3f}% "
            f"p75={p75:.3f}% "
            f"p90={p90:.3f}%"
        )

    magnitude_stats(
        "ALL LONG",
        rows,
    )

    magnitude_stats(
        "LONG + LOW",
        low_rows,
    )

    magnitude_stats(
        "LONG + HIGH",
        high_rows,
    )


# ---------------------------------------------------------------------------
# DIRECTIONAL CONSISTENCY
# ---------------------------------------------------------------------------

def analyze_symbol_consistency(
    symbol_rows: Dict[str, List[SessionPair]],
) -> None:
    print()
    print("=" * 110)
    print("LONG RELATIVE-POSITION — SYMBOL CONSISTENCY")
    print("=" * 110)

    print()
    print(
        "This asks whether LOW tends UP and/or HIGH tends DOWN "
        "inside individual symbols."
    )

    print()

    low_up_symbols = 0
    high_down_symbols = 0

    eligible_low = 0
    eligible_high = 0

    for symbol in SYMBOLS:
        rows = symbol_rows.get(symbol, [])

        low_rows = [
            r
            for r in rows
            if r.recent12_position_pct is not None
            and r.recent12_position_pct <= LOW_MAX
        ]

        high_rows = [
            r
            for r in rows
            if r.recent12_position_pct is not None
            and r.recent12_position_pct >= HIGH_MIN
        ]

        if len(low_rows) >= MIN_SYMBOL_N:
            eligible_low += 1

            low_stats = group_statistics(low_rows)

            if low_stats["up_pct"] > 50.0:
                low_up_symbols += 1

        if len(high_rows) >= MIN_SYMBOL_N:
            eligible_high += 1

            high_stats = group_statistics(high_rows)

            if high_stats["down_pct"] > 50.0:
                high_down_symbols += 1

    print(
        f"LOW groups with N>={MIN_SYMBOL_N}: "
        f"{eligible_low}"
    )

    print(
        f"LOW groups where UP > 50%: "
        f"{low_up_symbols}"
    )

    print()

    print(
        f"HIGH groups with N>={MIN_SYMBOL_N}: "
        f"{eligible_high}"
    )

    print(
        f"HIGH groups where DOWN > 50%: "
        f"{high_down_symbols}"
    )


# ---------------------------------------------------------------------------
# REPORT DATA RANGE
# ---------------------------------------------------------------------------

def print_data_range(
    symbol_rows: Dict[str, List[SessionPair]],
) -> None:
    all_rows = [
        row
        for rows in symbol_rows.values()
        for row in rows
    ]

    if not all_rows:
        return

    all_rows.sort(
        key=lambda r: r.next_open_time
    )

    print()
    print(
        f"Data range: "
        f"{all_rows[0].next_open_time} "
        f"-> "
        f"{all_rows[-1].next_open_time}"
    )

    print(
        f"LONG session pairs: {len(all_rows)}"
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=" * 110)
    print("AATA KISS — LONG RELATIVE-POSITION GAP VALIDATION")
    print("=" * 110)
    print()
    print(
        "Research only: no API, no trades, no engine changes, no DB writes"
    )
    print()
    print(
        "FOCUS:"
    )
    print(
        "Major trend LONG -> relative price position -> next session opening gap"
    )
    print()
    print(
        f"Trend window: {TREND_WINDOW} x 30m"
    )
    print(
        f"Trend band: {TREND_BAND * 100:.2f}%"
    )
    print(
        f"Relative-position window: {RECENT_WINDOW} bars"
    )
    print(
        f"LOW: 0-{LOW_MAX:.0f}"
    )
    print(
        f"HIGH: {HIGH_MIN:.0f}-100"
    )
    print(
        f"Discovery / holdout: "
        f"{DISCOVERY_FRACTION * 100:.0f}% / "
        f"{(1.0 - DISCOVERY_FRACTION) * 100:.0f}%"
    )

    symbol_rows: Dict[str, List[SessionPair]] = {}

    print()
    print("=" * 110)
    print("LOADING DATA")
    print("=" * 110)

    for symbol in SYMBOLS:
        candles = load_30m_candles(symbol)

        if not candles:
            print(
                f"{symbol}: no 30m data"
            )
            continue

        pairs = build_session_pairs(
            symbol,
            candles,
        )

        symbol_rows[symbol] = pairs

        print(
            f"{symbol}: "
            f"{len(candles)} candles -> "
            f"{len(pairs)} LONG session pairs"
        )

    all_rows = [
        row
        for rows in symbol_rows.values()
        for row in rows
    ]

    if not all_rows:
        print()
        print("NO SHORT SESSION PAIRS FOUND.")
        return

    print_data_range(
        symbol_rows
    )

    # ------------------------------------------------------------------
    # Chronological splits.
    # ------------------------------------------------------------------

    symbol_splits: Dict[
        str,
        Tuple[List[SessionPair], List[SessionPair]],
    ] = {}

    discovery_combined: List[SessionPair] = []

    for symbol, rows in symbol_rows.items():
        discovery, holdout = chronological_split(rows)

        symbol_splits[symbol] = (
            discovery,
            holdout,
        )

        discovery_combined.extend(discovery)

    discovery_combined.sort(
        key=lambda r: r.next_open_time
    )

    # ------------------------------------------------------------------
    # Discovery.
    # ------------------------------------------------------------------

    analyze_discovery(
        discovery_combined
    )

    # ------------------------------------------------------------------
    # Per-symbol discovery.
    # ------------------------------------------------------------------

    discovery_symbol_rows: Dict[
        str,
        List[SessionPair],
    ] = {
        symbol: split[0]
        for symbol, split in symbol_splits.items()
    }

    analyze_per_symbol(
        discovery_symbol_rows
    )

    # ------------------------------------------------------------------
    # Magnitude.
    # ------------------------------------------------------------------

    analyze_gap_magnitude(
        discovery_combined
    )

    # ------------------------------------------------------------------
    # Consistency.
    # ------------------------------------------------------------------

    analyze_symbol_consistency(
        discovery_symbol_rows
    )

    # ------------------------------------------------------------------
    # Holdout.
    # ------------------------------------------------------------------

    analyze_holdout(
        symbol_splits
    )

    # ------------------------------------------------------------------
    # Final interpretation guardrails.
    # ------------------------------------------------------------------

    print()
    print("=" * 110)
    print("INTERPRETATION GUARDRAILS")
    print("=" * 110)
    print()
    print(
        "1. This is NOT a trading rule."
    )
    print(
        "2. LOW/HIGH were selected from the earlier research hypothesis."
    )
    print(
        "3. Holdout data is later chronological data and should be treated "
        "as the important validation."
    )
    print(
        "4. Small per-symbol samples are evidence only, not conclusions."
    )
    print(
        "5. A pooled edge that disappears inside most symbols is suspicious."
    )
    print(
        "6. A relationship that survives later holdout data is much more "
        "interesting."
    )
    print(
        "7. Even a strong gap-direction relationship does not automatically "
        "mean a profitable trading strategy."
    )
    print()
    print(
        "END OF RESEARCH-ONLY DIAGNOSTIC"
    )
    print()


if __name__ == "__main__":
    main()