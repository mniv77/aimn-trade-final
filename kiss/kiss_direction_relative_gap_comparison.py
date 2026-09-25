# [FILE: kiss_direction_relative_gap_comparison.py] — KISS direction × relative-position session-gap comparison research

"""
AATA KISS — Direction × Relative Position × Next Session Gap Comparison

Research only.
NO API.
NO trades.
NO engine changes.
NO DB writes.

Purpose:
    Compare the four combinations:

        SHORT + LOW
        SHORT + HIGH
        LONG  + LOW
        LONG  + HIGH

    against the next session opening gap.

This is the direct follow-up to:
    kiss_short_gap_validation_diagnostic.py
    kiss_long_gap_validation_diagnostic.py

The goal is NOT to create a trading rule.

We want to determine whether the earlier observations are:
    1. direction-specific,
    2. relative-position-specific,
    3. consistent across symbols,
    4. present in later chronological holdout data,
    5. associated with gap magnitude as well as direction.

Relative position:
    0-20   = LOW
    20-80  = MIDDLE
    80-100 = HIGH

Session gap:
    previous RTH/session close -> next session open

Gap %:
    (next_open - previous_close) / previous_close * 100

Discovery / holdout:
    70% chronological discovery
    30% chronological holdout

IMPORTANT:
    This diagnostic does not assume that LONG and SHORT must behave
    symmetrically. That asymmetry is exactly what we are testing.
"""

from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Sequence, Tuple

from db import get_db_connection


# ============================================================
# CONFIG
# ============================================================

TREND_WINDOW = 20
TREND_BAND = 0.002

RECENT_WINDOW = 12

LOW_MAX = 20.0
HIGH_MIN = 80.0

SESSION_GAP_HOURS = 2.0

DISCOVERY_PCT = 0.70

MIN_SYMBOL_GROUP = 4
MIN_COMBINED_GROUP = 4

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


# ============================================================
# DATABASE
# ============================================================

def load_30m_rows(symbol: str) -> List[Dict]:
    conn, cursor = get_db_connection()

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s
              AND timeframe=%s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (symbol, "30m", 5000),
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

    return rows


# ============================================================
# BASIC HELPERS
# ============================================================

def to_float(value) -> float:
    return float(value)


def get_timestamp(row: Dict):
    return row["timestamp"]


def get_close(row: Dict) -> float:
    return to_float(row["close"])


def get_open(row: Dict) -> float:
    return to_float(row["open"])


def get_high(row: Dict) -> float:
    return to_float(row["high"])


def get_low(row: Dict) -> float:
    return to_float(row["low"])


def get_volume(row: Dict) -> float:
    return to_float(row["volume"])


# ============================================================
# KISS STATE
# ============================================================

def get_market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    ma = mean(
        closes[idx - TREND_WINDOW:idx]
    )

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


# ============================================================
# RELATIVE POSITION
# ============================================================

def relative_position(
    closes: Sequence[float],
    idx: int,
    window: int = RECENT_WINDOW,
) -> Optional[float]:
    if idx < window:
        return None

    values = closes[idx - window + 1:idx + 1]

    if not values:
        return None

    low = min(values)
    high = max(values)

    if high <= low:
        return 50.0

    return (
        (closes[idx] - low)
        / (high - low)
        * 100.0
    )


def position_bucket(position: Optional[float]) -> str:
    if position is None:
        return "UNKNOWN"

    if position <= LOW_MAX:
        return "LOW"

    if position >= HIGH_MIN:
        return "HIGH"

    return "MIDDLE"


# ============================================================
# SESSION DETECTION
# ============================================================

def detect_sessions(
    rows: Sequence[Dict],
) -> List[List[Dict]]:
    if not rows:
        return []

    sessions: List[List[Dict]] = []
    current = [rows[0]]

    for row in rows[1:]:
        previous = current[-1]

        delta = (
            get_timestamp(row)
            - get_timestamp(previous)
        ).total_seconds()

        if delta > SESSION_GAP_HOURS * 3600.0:
            sessions.append(current)
            current = [row]
        else:
            current.append(row)

    if current:
        sessions.append(current)

    return sessions


# ============================================================
# SESSION RECORD
# ============================================================

def build_session_records(
    symbol: str,
    rows: Sequence[Dict],
) -> List[Dict]:
    if len(rows) < TREND_WINDOW + RECENT_WINDOW + 2:
        return []

    closes = [
        get_close(row)
        for row in rows
    ]

    states = [
        get_market_state(closes, i)
        for i in range(len(rows))
    ]

    sessions = detect_sessions(rows)

    if len(sessions) < 2:
        return []

    row_index = {
        get_timestamp(row): i
        for i, row in enumerate(rows)
    }

    records: List[Dict] = []

    for session_idx in range(len(sessions) - 1):
        previous_session = sessions[session_idx]
        next_session = sessions[session_idx + 1]

        previous_close_row = previous_session[-1]
        next_open_row = next_session[0]

        previous_close_time = get_timestamp(
            previous_close_row
        )

        if previous_close_time not in row_index:
            continue

        idx = row_index[previous_close_time]

        if idx < TREND_WINDOW:
            continue

        major_state = states[idx]

        if major_state not in ("LONG", "SHORT"):
            continue

        position = relative_position(
            closes,
            idx,
            RECENT_WINDOW,
        )

        bucket = position_bucket(position)

        if bucket not in ("LOW", "MIDDLE", "HIGH"):
            continue

        previous_close = get_close(
            previous_close_row
        )

        next_open = get_open(
            next_open_row
        )

        if previous_close == 0:
            continue

        gap_pct = (
            (next_open - previous_close)
            / previous_close
            * 100.0
        )

        records.append(
            {
                "symbol": symbol,
                "previous_close_time":
                    previous_close_time,
                "next_open_time":
                    get_timestamp(next_open_row),
                "major_state":
                    major_state,
                "position":
                    position,
                "bucket":
                    bucket,
                "gap_pct":
                    gap_pct,
                "gap_abs":
                    abs(gap_pct),
            }
        )

    return records


# ============================================================
# STATS
# ============================================================

def stats(
    rows: Sequence[Dict],
) -> Dict[str, float]:
    if not rows:
        return {
            "n": 0,
            "up": 0.0,
            "down": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "abs": 0.0,
        }

    gaps = [
        float(row["gap_pct"])
        for row in rows
    ]

    up = sum(
        1
        for gap in gaps
        if gap > 0
    )

    down = sum(
        1
        for gap in gaps
        if gap < 0
    )

    n = len(gaps)

    return {
        "n": n,
        "up": 100.0 * up / n,
        "down": 100.0 * down / n,
        "mean": mean(gaps),
        "median": median(gaps),
        "abs": mean(abs(gap) for gap in gaps),
    }


def print_group(
    label: str,
    rows: Sequence[Dict],
) -> None:
    s = stats(rows)

    print(
        f"{label:<30}"
        f"N={s['n']:4d} "
        f"UP={s['up']:6.1f}% "
        f"DOWN={s['down']:6.1f}% "
        f"mean={s['mean']:+7.3f}% "
        f"median={s['median']:+7.3f}% "
        f"abs={s['abs']:6.3f}%"
    )


# ============================================================
# FILTERS
# ============================================================

def filter_rows(
    rows: Sequence[Dict],
    direction: Optional[str] = None,
    bucket: Optional[str] = None,
) -> List[Dict]:
    result = []

    for row in rows:
        if direction is not None:
            if row["major_state"] != direction:
                continue

        if bucket is not None:
            if row["bucket"] != bucket:
                continue

        result.append(row)

    return result


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

def chronological_split(
    rows: Sequence[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    ordered = sorted(
        rows,
        key=lambda row: row["previous_close_time"],
    )

    if not ordered:
        return [], []

    split_idx = int(
        len(ordered) * DISCOVERY_PCT
    )

    split_idx = max(
        1,
        min(split_idx, len(ordered) - 1),
    )

    return (
        ordered[:split_idx],
        ordered[split_idx:],
    )


# ============================================================
# DISCOVERY
# ============================================================

def print_discovery(
    rows: Sequence[Dict],
) -> None:
    print()
    print("=" * 110)
    print(
        "DIRECTION × RELATIVE POSITION — "
        "DISCOVERY DATA"
    )
    print("=" * 110)

    print()
    print("FOUR CORE GROUPS")

    print_group(
        "SHORT + LOW",
        filter_rows(rows, "SHORT", "LOW"),
    )

    print_group(
        "SHORT + MIDDLE",
        filter_rows(rows, "SHORT", "MIDDLE"),
    )

    print_group(
        "SHORT + HIGH",
        filter_rows(rows, "SHORT", "HIGH"),
    )

    print_group(
        "LONG + LOW",
        filter_rows(rows, "LONG", "LOW"),
    )

    print_group(
        "LONG + MIDDLE",
        filter_rows(rows, "LONG", "MIDDLE"),
    )

    print_group(
        "LONG + HIGH",
        filter_rows(rows, "LONG", "HIGH"),
    )

    print()
    print("DIRECT LOW vs HIGH COMPARISON")

    for direction in ("SHORT", "LONG"):
        print()
        print(f"{direction}")

        print_group(
            "  LOW",
            filter_rows(rows, direction, "LOW"),
        )

        print_group(
            "  HIGH",
            filter_rows(rows, direction, "HIGH"),
        )


# ============================================================
# PER SYMBOL
# ============================================================

def print_symbol_consistency(
    rows_by_symbol: Dict[str, List[Dict]],
) -> None:
    print()
    print("=" * 110)
    print(
        "DIRECTION × RELATIVE POSITION — "
        "PER SYMBOL"
    )
    print("=" * 110)

    print()
    print(
        f"{'SYMBOL':<8}"
        f"{'S+L':>7}"
        f"{'S+L UP':>10}"
        f"{'S+H':>7}"
        f"{'S+H UP':>10}"
        f"{'L+L':>7}"
        f"{'L+L UP':>10}"
        f"{'L+H':>7}"
        f"{'L+H UP':>10}"
    )

    print("-" * 90)

    for symbol, rows in rows_by_symbol.items():

        sl = filter_rows(rows, "SHORT", "LOW")
        sh = filter_rows(rows, "SHORT", "HIGH")
        ll = filter_rows(rows, "LONG", "LOW")
        lh = filter_rows(rows, "LONG", "HIGH")

        sls = stats(sl)
        shs = stats(sh)
        lls = stats(ll)
        lhs = stats(lh)

        print(
            f"{symbol:<8}"
            f"{sls['n']:7d}"
            f"{sls['up']:9.1f}%"
            f"{shs['n']:7d}"
            f"{shs['up']:9.1f}%"
            f"{lls['n']:7d}"
            f"{lls['up']:9.1f}%"
            f"{lhs['n']:7d}"
            f"{lhs['up']:9.1f}%"
        )

    print()
    print(
        "Only groups with meaningful sample size should "
        "be considered evidence."
    )


# ============================================================
# GAP MAGNITUDE
# ============================================================

def print_gap_magnitude(
    rows: Sequence[Dict],
) -> None:
    print()
    print("=" * 110)
    print(
        "DIRECTION × RELATIVE POSITION — "
        "GAP MAGNITUDE"
    )
    print("=" * 110)

    groups = [
        ("SHORT + LOW", "SHORT", "LOW"),
        ("SHORT + HIGH", "SHORT", "HIGH"),
        ("LONG + LOW", "LONG", "LOW"),
        ("LONG + HIGH", "LONG", "HIGH"),
    ]

    for label, direction, bucket in groups:
        group = filter_rows(
            rows,
            direction,
            bucket,
        )

        gaps = [
            abs(float(row["gap_pct"]))
            for row in group
        ]

        if not gaps:
            print(
                f"{label:<30}"
                "N=   0"
            )
            continue

        ordered = sorted(gaps)

        p75_index = min(
            len(ordered) - 1,
            int(len(ordered) * 0.75),
        )

        p90_index = min(
            len(ordered) - 1,
            int(len(ordered) * 0.90),
        )

        print(
            f"{label:<30}"
            f"N={len(gaps):4d} "
            f"mean_abs={mean(gaps):6.3f}% "
            f"median_abs={median(gaps):6.3f}% "
            f"p75={ordered[p75_index]:6.3f}% "
            f"p90={ordered[p90_index]:6.3f}%"
        )


# ============================================================
# HOLDOUT
# ============================================================

def print_holdout(
    rows_by_symbol: Dict[str, List[Dict]],
) -> None:
    print()
    print("=" * 110)
    print(
        "DIRECTION × RELATIVE POSITION — "
        "OUT-OF-SAMPLE HOLDOUT"
    )
    print("=" * 110)

    print()
    print(
        "Each symbol is split chronologically:"
    )
    print(
        "70% discovery / 30% later holdout."
    )

    all_holdout: List[Dict] = []

    for symbol, rows in rows_by_symbol.items():
        _, holdout = chronological_split(rows)

        all_holdout.extend(holdout)

        print()
        print(
            f"{symbol}: holdout N={len(holdout)}"
        )

        print_group(
            "  SHORT + LOW",
            filter_rows(
                holdout,
                "SHORT",
                "LOW",
            ),
        )

        print_group(
            "  SHORT + HIGH",
            filter_rows(
                holdout,
                "SHORT",
                "HIGH",
            ),
        )

        print_group(
            "  LONG + LOW",
            filter_rows(
                holdout,
                "LONG",
                "LOW",
            ),
        )

        print_group(
            "  LONG + HIGH",
            filter_rows(
                holdout,
                "LONG",
                "HIGH",
            ),
        )

    print()
    print("-" * 110)
    print("COMBINED HOLDOUT")

    print_group(
        "SHORT + LOW",
        filter_rows(
            all_holdout,
            "SHORT",
            "LOW",
        ),
    )

    print_group(
        "SHORT + HIGH",
        filter_rows(
            all_holdout,
            "SHORT",
            "HIGH",
        ),
    )

    print_group(
        "LONG + LOW",
        filter_rows(
            all_holdout,
            "LONG",
            "LOW",
        ),
    )

    print_group(
        "LONG + HIGH",
        filter_rows(
            all_holdout,
            "LONG",
            "HIGH",
        ),
    )

    return all_holdout


# ============================================================
# DISCOVERY VS HOLDOUT COMPARISON
# ============================================================

def print_discovery_holdout_comparison(
    rows_by_symbol: Dict[str, List[Dict]],
) -> None:
    print()
    print("=" * 110)
    print(
        "DISCOVERY vs HOLDOUT — CORE FOUR"
    )
    print("=" * 110)

    discovery_all: List[Dict] = []
    holdout_all: List[Dict] = []

    for rows in rows_by_symbol.values():
        discovery, holdout = chronological_split(rows)
        discovery_all.extend(discovery)
        holdout_all.extend(holdout)

    groups = [
        ("SHORT + LOW", "SHORT", "LOW"),
        ("SHORT + HIGH", "SHORT", "HIGH"),
        ("LONG + LOW", "LONG", "LOW"),
        ("LONG + HIGH", "LONG", "HIGH"),
    ]

    for label, direction, bucket in groups:
        print()
        print(label)

        print_group(
            "  discovery",
            filter_rows(
                discovery_all,
                direction,
                bucket,
            ),
        )

        print_group(
            "  holdout",
            filter_rows(
                holdout_all,
                direction,
                bucket,
            ),
        )


# ============================================================
# SIMPLE DIFFERENCE MEASURES
# ============================================================

def print_directional_differences(
    rows: Sequence[Dict],
) -> None:
    print()
    print("=" * 110)
    print(
        "LOW vs HIGH — DIRECTIONAL DIFFERENCES"
    )
    print("=" * 110)

    for direction in ("SHORT", "LONG"):

        low = filter_rows(
            rows,
            direction,
            "LOW",
        )

        high = filter_rows(
            rows,
            direction,
            "HIGH",
        )

        lows = stats(low)
        highs = stats(high)

        print()
        print(direction)

        if lows["n"] and highs["n"]:
            print(
                f"  UP-rate difference "
                f"(LOW - HIGH): "
                f"{lows['up'] - highs['up']:+.1f} percentage points"
            )

            print(
                f"  Mean-gap difference "
                f"(LOW - HIGH): "
                f"{lows['mean'] - highs['mean']:+.3f}%"
            )

            print(
                f"  Mean-absolute-gap difference "
                f"(LOW - HIGH): "
                f"{lows['abs'] - highs['abs']:+.3f}%"
            )
        else:
            print(
                "  Not enough data for comparison."
            )


# ============================================================
# GUARDRAILS
# ============================================================

def print_guardrails() -> None:
    print()
    print("=" * 110)
    print("INTERPRETATION GUARDRAILS")
    print("=" * 110)

    print()
    print(
        "1. This is NOT a trading rule."
    )

    print(
        "2. LOW/HIGH are research buckets, "
        "not buy/sell signals."
    )

    print(
        "3. Discovery results are hypotheses; "
        "the later chronological holdout is more important."
    )

    print(
        "4. Small groups can produce impressive-looking "
        "percentages by chance."
    )

    print(
        "5. A pooled effect that disappears inside symbols "
        "is suspicious."
    )

    print(
        "6. A relationship that survives the holdout "
        "is more interesting."
    )

    print(
        "7. Gap direction alone does not establish "
        "trading profitability."
    )

    print(
        "8. LONG and SHORT do not have to behave "
        "symmetrically."
    )

    print(
        "9. No KISS engine or AATA model is changed "
        "by this research."
    )

    print(
        "10. The purpose is to discover structure "
        "before deciding whether it belongs in AATA."
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 110)
    print(
        "AATA KISS — DIRECTION × RELATIVE POSITION "
        "SESSION-GAP COMPARISON"
    )
    print("=" * 110)

    print()
    print(
        "Research only: no API, no trades, "
        "no engine changes, no DB writes"
    )

    print()
    print(
        "FOCUS:"
    )

    print(
        "SHORT + LOW"
    )
    print(
        "SHORT + HIGH"
    )
    print(
        "LONG  + LOW"
    )
    print(
        "LONG  + HIGH"
    )

    print()
    print(
        f"Trend window: {TREND_WINDOW} x 30m"
    )

    print(
        f"Trend band: {TREND_BAND * 100:.2f}%"
    )

    print(
        f"Relative-position window: "
        f"{RECENT_WINDOW} bars"
    )

    print(
        f"LOW: 0-{LOW_MAX:.0f}"
    )

    print(
        f"HIGH: {HIGH_MIN:.0f}-100"
    )

    print(
        f"Discovery / holdout: "
        f"{DISCOVERY_PCT * 100:.0f}% / "
        f"{(1.0 - DISCOVERY_PCT) * 100:.0f}%"
    )

    print()
    print("=" * 110)
    print("LOADING DATA")
    print("=" * 110)

    rows_by_symbol: Dict[str, List[Dict]] = {}
    all_rows: List[Dict] = []

    for symbol in SYMBOLS:
        rows = load_30m_rows(symbol)

        if not rows:
            print(
                f"{symbol}: no 30m data"
            )
            continue

        records = build_session_records(
            symbol,
            rows,
        )

        rows_by_symbol[symbol] = records
        all_rows.extend(records)

        print(
            f"{symbol}: "
            f"{len(rows)} candles -> "
            f"{len(records)} usable LONG/SHORT "
            f"session pairs"
        )

    print()

    print(
        f"Symbols tested: "
        f"{len(rows_by_symbol)}"
    )

    print(
        f"Total usable LONG/SHORT session pairs: "
        f"{len(all_rows)}"
    )

    overall = stats(all_rows)

    print(
        f"UP={overall['up']:.1f}% "
        f"DOWN={overall['down']:.1f}% "
        f"mean={overall['mean']:+.3f}% "
        f"abs={overall['abs']:.3f}%"
    )

    # --------------------------------------------------------
    # Discovery data
    # --------------------------------------------------------

    discovery_all: List[Dict] = []

    discovery_by_symbol: Dict[str, List[Dict]] = {}

    for symbol, rows in rows_by_symbol.items():
        discovery, _ = chronological_split(rows)

        discovery_by_symbol[symbol] = discovery
        discovery_all.extend(discovery)

    print_discovery(
        discovery_all
    )

    # --------------------------------------------------------
    # Per-symbol consistency
    # --------------------------------------------------------

    print_symbol_consistency(
        discovery_by_symbol
    )

    # --------------------------------------------------------
    # Gap magnitude
    # --------------------------------------------------------

    print_gap_magnitude(
        discovery_all
    )

    # --------------------------------------------------------
    # Holdout
    # --------------------------------------------------------

    print_holdout(
        rows_by_symbol
    )

    # --------------------------------------------------------
    # Discovery vs holdout
    # --------------------------------------------------------

    print_discovery_holdout_comparison(
        rows_by_symbol
    )

    # --------------------------------------------------------
    # Directional differences
    # --------------------------------------------------------

    print_directional_differences(
        discovery_all
    )

    # --------------------------------------------------------
    # Guardrails
    # --------------------------------------------------------

    print_guardrails()

    print()
    print("=" * 110)
    print(
        "END OF RESEARCH-ONLY COMPARISON"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()