# [FILE: kiss_session_gap_interaction_diagnostic.py] — AATA KISS session-gap interaction research

"""
AATA KISS SESSION-GAP INTERACTION DIAGNOSTIC

Research only:
    - no API calls
    - no trades
    - no engine changes
    - no DB writes

Question:
    Does the NEXT SESSION OPENING GAP depend on combinations of:

        1. Major KISS trend at the previous session close
        2. Relative price position near the previous session close
        3. Late-session state pathway

The important point is that every predictor uses information available
BEFORE the next session opens.

We deliberately do NOT turn any finding into a trading rule here.

Outputs:
    - trend x recent-12 position
    - trend x recent-24 position
    - trend x late pathway
    - relative-position x late pathway
    - strongest 3-way combinations with sufficient sample size
    - per-symbol and combined summaries

Gap:
    (next_session_open - previous_session_close) / previous_session_close * 100

Relative position:
    0-20   = relatively low
    20-40
    40-60
    60-80
    80-100 = relatively high

All times are taken directly from the database.
No market-hours timezone is hard-coded.
A session boundary is detected by a timestamp gap > 2 hours.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from db import get_db_connection


# ---------------------------------------------------------------------------
# CONFIGURATION
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

RSI_PERIOD = 14

SESSION_GAP_HOURS = 2.0

RECENT_12 = 12
RECENT_24 = 24

MIN_DISPLAY_N = 8


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

def load_candles(symbol: str) -> List[Dict]:
    conn, cursor = get_db_connection()

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s AND timeframe=%s
            ORDER BY timestamp ASC
            """,
            (symbol, TIMEFRAME),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

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
# BASIC HELPERS
# ---------------------------------------------------------------------------

def as_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def get_state(
    closes: Sequence[float],
    idx: int,
) -> str:
    if idx < TREND_WINDOW:
        return "FLAT"

    ma = sum(
        closes[idx - TREND_WINDOW:idx]
    ) / TREND_WINDOW

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def rsi_wilder(
    closes: Sequence[float],
    period: int = RSI_PERIOD,
) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(closes)

    if len(closes) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]

        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

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


def relative_position(
    closes: Sequence[float],
    idx: int,
    window: int,
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

    value = closes[idx]

    position = (
        (value - low) /
        (high - low)
    ) * 100.0

    return max(0.0, min(100.0, position))


def position_bucket(position: Optional[float]) -> str:
    if position is None:
        return "NA"

    if position < 20:
        return "0-20"

    if position < 40:
        return "20-40"

    if position < 60:
        return "40-60"

    if position < 80:
        return "60-80"

    return "80-100"


def state_path(
    states: Sequence[str],
    idx: int,
    bars: int = 6,
) -> str:
    start = max(0, idx - bars + 1)

    values = [
        states[i]
        for i in range(start, idx + 1)
    ]

    if not values:
        return "NA"

    compressed = [values[0]]

    for value in values[1:]:
        if value != compressed[-1]:
            compressed.append(value)

    return "->".join(compressed)


def trend_label(state: str) -> str:
    if state == "LONG":
        return "LONG"

    if state == "SHORT":
        return "SHORT"

    return "FLAT"


# ---------------------------------------------------------------------------
# SESSION DETECTION
# ---------------------------------------------------------------------------

def split_sessions(
    rows: Sequence[Dict],
) -> List[List[Dict]]:
    if not rows:
        return []

    sessions: List[List[Dict]] = []
    current: List[Dict] = [rows[0]]

    for row in rows[1:]:
        previous_time = current[-1]["timestamp"]
        current_time = row["timestamp"]

        try:
            gap_hours = (
                current_time - previous_time
            ).total_seconds() / 3600.0
        except Exception:
            gap_hours = 0.0

        if gap_hours > SESSION_GAP_HOURS:
            sessions.append(current)
            current = [row]
        else:
            current.append(row)

    if current:
        sessions.append(current)

    return sessions


# ---------------------------------------------------------------------------
# SESSION RECORD
# ---------------------------------------------------------------------------

def build_session_records(
    rows: Sequence[Dict],
) -> List[Dict]:
    if len(rows) < TREND_WINDOW + RECENT_24:
        return []

    closes = [
        as_float(row["close"])
        for row in rows
    ]

    valid_closes = [
        value if value is not None else 0.0
        for value in closes
    ]

    states = [
        get_state(valid_closes, i)
        for i in range(len(rows))
    ]

    rsi_values = rsi_wilder(valid_closes)

    sessions = split_sessions(rows)

    if len(sessions) < 2:
        return []

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

        previous_timestamp = (
            previous_close_row["timestamp"]
        )

        next_timestamp = (
            next_open_row["timestamp"]
        )

        idx = index_by_timestamp.get(
            previous_timestamp
        )

        if idx is None:
            continue

        previous_close = as_float(
            previous_close_row["close"]
        )

        next_open = as_float(
            next_open_row["open"]
        )

        if previous_close is None:
            continue

        if next_open is None:
            continue

        if previous_close == 0:
            continue

        gap_pct = (
            (next_open - previous_close)
            / previous_close
        ) * 100.0

        position_12 = relative_position(
            valid_closes,
            idx,
            RECENT_12,
        )

        position_24 = relative_position(
            valid_closes,
            idx,
            RECENT_24,
        )

        rsi = (
            rsi_values[idx]
            if idx < len(rsi_values)
            else None
        )

        state = states[idx]

        path = state_path(
            states,
            idx,
            bars=6,
        )

        session_high = max(
            (
                as_float(row["high"])
                for row in previous_session
                if as_float(row["high"]) is not None
            ),
            default=None,
        )

        session_low = min(
            (
                as_float(row["low"])
                for row in previous_session
                if as_float(row["low"]) is not None
            ),
            default=None,
        )

        session_position = None

        if (
            session_high is not None
            and session_low is not None
            and session_high > session_low
        ):
            session_position = (
                (previous_close - session_low)
                / (session_high - session_low)
            ) * 100.0

        records.append(
            {
                "symbol": None,
                "previous_close_time": previous_timestamp,
                "next_open_time": next_timestamp,
                "previous_close": previous_close,
                "next_open": next_open,
                "gap_pct": gap_pct,
                "direction": (
                    "UP"
                    if gap_pct > 0
                    else "DOWN"
                    if gap_pct < 0
                    else "FLAT"
                ),
                "trend": trend_label(state),
                "position_12": position_12,
                "position_12_bucket": position_bucket(
                    position_12
                ),
                "position_24": position_24,
                "position_24_bucket": position_bucket(
                    position_24
                ),
                "session_position": session_position,
                "session_position_bucket": position_bucket(
                    session_position
                ),
                "path": path,
                "rsi": rsi,
            }
        )

    return records


# ---------------------------------------------------------------------------
# GROUPING / STATISTICS
# ---------------------------------------------------------------------------

def group_records(
    records: Sequence[Dict],
    keys: Sequence[str],
) -> Dict[Tuple, List[Dict]]:
    groups: Dict[Tuple, List[Dict]] = defaultdict(list)

    for record in records:
        key = tuple(
            record.get(key_name)
            for key_name in keys
        )

        groups[key].append(record)

    return groups


def summarize(
    records: Sequence[Dict],
) -> Dict[str, float]:
    gaps = [
        float(record["gap_pct"])
        for record in records
    ]

    if not gaps:
        return {
            "n": 0,
            "up_pct": 0.0,
            "down_pct": 0.0,
            "flat_pct": 0.0,
            "mean_gap": 0.0,
            "mean_abs": 0.0,
        }

    up = sum(
        1
        for value in gaps
        if value > 0
    )

    down = sum(
        1
        for value in gaps
        if value < 0
    )

    flat = len(gaps) - up - down

    return {
        "n": len(gaps),
        "up_pct": 100.0 * up / len(gaps),
        "down_pct": 100.0 * down / len(gaps),
        "flat_pct": 100.0 * flat / len(gaps),
        "mean_gap": sum(gaps) / len(gaps),
        "mean_abs": (
            sum(abs(value) for value in gaps)
            / len(gaps)
        ),
    }


def print_group_table(
    title: str,
    records: Sequence[Dict],
    keys: Sequence[str],
    min_n: int = MIN_DISPLAY_N,
) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    groups = group_records(records, keys)

    rows = []

    for key, group in groups.items():
        stats = summarize(group)

        if stats["n"] < min_n:
            continue

        rows.append(
            (
                key,
                stats,
            )
        )

    rows.sort(
        key=lambda item: (
            -item[1]["n"],
            item[0],
        )
    )

    if not rows:
        print(
            f"No groups with N >= {min_n}"
        )
        return

    header = (
        " | ".join(
            f"{key:<24}"
            for key in keys
        )
        + " | N    | UP%   | DOWN% | "
          "MEAN GAP | MEAN ABS"
    )

    print(header)
    print("-" * len(header))

    for key, stats in rows:
        key_text = " | ".join(
            f"{str(value):<24}"
            for value in key
        )

        print(
            f"{key_text} | "
            f"{stats['n']:>4} | "
            f"{stats['up_pct']:>5.1f} | "
            f"{stats['down_pct']:>5.1f} | "
            f"{stats['mean_gap']:>+8.3f}% | "
            f"{stats['mean_abs']:>8.3f}%"
        )


# ---------------------------------------------------------------------------
# EDGE RANKING
# ---------------------------------------------------------------------------

def print_directional_edges(
    title: str,
    records: Sequence[Dict],
    keys: Sequence[str],
    min_n: int = MIN_DISPLAY_N,
) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    groups = group_records(records, keys)

    ranked = []

    for key, group in groups.items():
        stats = summarize(group)

        if stats["n"] < min_n:
            continue

        edge = abs(
            stats["up_pct"] - 50.0
        )

        ranked.append(
            (
                edge,
                key,
                stats,
            )
        )

    ranked.sort(
        key=lambda item: (
            -item[0],
            -item[2]["n"],
        )
    )

    if not ranked:
        print(
            f"No groups with N >= {min_n}"
        )
        return

    for edge, key, stats in ranked[:20]:
        print(
            f"{key} | "
            f"N={stats['n']:>3} | "
            f"UP={stats['up_pct']:>5.1f}% | "
            f"DOWN={stats['down_pct']:>5.1f}% | "
            f"edge={edge:>5.1f} pts | "
            f"mean={stats['mean_gap']:+.3f}% | "
            f"abs={stats['mean_abs']:.3f}%"
        )


# ---------------------------------------------------------------------------
# SYMBOL REPORT
# ---------------------------------------------------------------------------

def print_symbol_summary(
    symbol: str,
    records: Sequence[Dict],
) -> None:
    stats = summarize(records)

    print()
    print("-" * 100)
    print(f"{symbol}")
    print("-" * 100)

    print(
        f"Session pairs: {stats['n']} | "
        f"UP: {stats['up_pct']:.1f}% | "
        f"DOWN: {stats['down_pct']:.1f}% | "
        f"Mean gap: {stats['mean_gap']:+.3f}% | "
        f"Mean abs gap: {stats['mean_abs']:.3f}%"
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=" * 100)
    print("AATA KISS SESSION-GAP INTERACTION DIAGNOSTIC")
    print("=" * 100)
    print(
        "Research only: no API, no trades, no engine changes, no DB writes"
    )
    print()
    print(
        "Question: does the NEXT opening gap depend on combinations of"
    )
    print(
        "trend + relative position + late-session pathway?"
    )
    print()
    print(
        f"Session boundary: timestamp gap > {SESSION_GAP_HOURS:.1f} hours"
    )
    print(
        f"Minimum displayed group size: N >= {MIN_DISPLAY_N}"
    )

    all_records: List[Dict] = []
    records_by_symbol: Dict[str, List[Dict]] = {}

    for symbol in SYMBOLS:
        try:
            rows = load_candles(symbol)

            if not rows:
                print(
                    f"\n{symbol}: NO {TIMEFRAME} DATA"
                )
                continue

            records = build_session_records(rows)

            for record in records:
                record["symbol"] = symbol

            records_by_symbol[symbol] = records
            all_records.extend(records)

            print(
                f"\n{symbol}: "
                f"{len(rows)} candles -> "
                f"{len(records)} session pairs"
            )

        except Exception as exc:
            print(
                f"\n{symbol}: ERROR: {exc}"
            )

    if not all_records:
        print()
        print("NO SESSION DATA FOUND.")
        return

    # ------------------------------------------------------------------
    # OVERALL
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("COMBINED SESSION-GAP SUMMARY")
    print("=" * 100)

    stats = summarize(all_records)

    print(
        f"Symbols tested: {len(records_by_symbol)}"
    )
    print(
        f"Session pairs: {stats['n']}"
    )
    print(
        f"UP: {stats['up_pct']:.1f}%"
    )
    print(
        f"DOWN: {stats['down_pct']:.1f}%"
    )
    print(
        f"Mean gap: {stats['mean_gap']:+.3f}%"
    )
    print(
        f"Mean absolute gap: {stats['mean_abs']:.3f}%"
    )

    # ------------------------------------------------------------------
    # SYMBOLS
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("PER-SYMBOL SUMMARIES")
    print("=" * 100)

    for symbol, records in records_by_symbol.items():
        print_symbol_summary(
            symbol,
            records,
        )

    # ------------------------------------------------------------------
    # 1. TREND x RELATIVE POSITION
    # ------------------------------------------------------------------

    print_group_table(
        "TREND x RECENT 12-BAR RELATIVE POSITION",
        all_records,
        [
            "trend",
            "position_12_bucket",
        ],
    )

    print_directional_edges(
        "STRONGEST TREND x RECENT-12 DIRECTIONAL EDGES",
        all_records,
        [
            "trend",
            "position_12_bucket",
        ],
    )

    print_group_table(
        "TREND x RECENT 24-BAR RELATIVE POSITION",
        all_records,
        [
            "trend",
            "position_24_bucket",
        ],
    )

    print_directional_edges(
        "STRONGEST TREND x RECENT-24 DIRECTIONAL EDGES",
        all_records,
        [
            "trend",
            "position_24_bucket",
        ],
    )

    # ------------------------------------------------------------------
    # 2. TREND x SESSION POSITION
    # ------------------------------------------------------------------

    print_group_table(
        "TREND x PREVIOUS SESSION RELATIVE CLOSE POSITION",
        all_records,
        [
            "trend",
            "session_position_bucket",
        ],
    )

    print_directional_edges(
        "STRONGEST TREND x SESSION-POSITION EDGES",
        all_records,
        [
            "trend",
            "session_position_bucket",
        ],
    )

    # ------------------------------------------------------------------
    # 3. TREND x PATHWAY
    # ------------------------------------------------------------------

    print_group_table(
        "TREND x LATE-SESSION PATHWAY",
        all_records,
        [
            "trend",
            "path",
        ],
    )

    print_directional_edges(
        "STRONGEST TREND x PATHWAY EDGES",
        all_records,
        [
            "trend",
            "path",
        ],
    )

    # ------------------------------------------------------------------
    # 4. RELATIVE POSITION x PATHWAY
    # ------------------------------------------------------------------

    print_group_table(
        "RECENT-12 RELATIVE POSITION x LATE-SESSION PATHWAY",
        all_records,
        [
            "position_12_bucket",
            "path",
        ],
    )

    print_directional_edges(
        "STRONGEST RELATIVE-POSITION x PATHWAY EDGES",
        all_records,
        [
            "position_12_bucket",
            "path",
        ],
    )

    # ------------------------------------------------------------------
    # 5. THREE-WAY INTERACTION
    # ------------------------------------------------------------------

    print_group_table(
        "THREE-WAY: TREND x RECENT-12 POSITION x PATHWAY",
        all_records,
        [
            "trend",
            "position_12_bucket",
            "path",
        ],
    )

    print_directional_edges(
        "STRONGEST THREE-WAY INTERACTION EDGES",
        all_records,
        [
            "trend",
            "position_12_bucket",
            "path",
        ],
    )

    # ------------------------------------------------------------------
    # 6. IMPORTANT LOW-vs-HIGH COMPARISON
    # ------------------------------------------------------------------

    extreme_records = [
        record
        for record in all_records
        if record["position_12_bucket"]
        in ("0-20", "80-100")
    ]

    print_group_table(
        "EXTREME RELATIVE POSITION: LOW vs HIGH, CONDITIONAL ON TREND",
        extreme_records,
        [
            "trend",
            "position_12_bucket",
        ],
        min_n=5,
    )

    # ------------------------------------------------------------------
    # 7. PATHWAY FOCUS
    # ------------------------------------------------------------------

    pathway_records = [
        record
        for record in all_records
        if "->" in record["path"]
    ]

    print_group_table(
        "MULTI-STATE LATE PATHWAYS ONLY",
        pathway_records,
        [
            "trend",
            "path",
        ],
        min_n=5,
    )

    # ------------------------------------------------------------------
    # FINAL
    # ------------------------------------------------------------------

    print()
    print("=" * 100)
    print("RESEARCH INTERPRETATION GUIDE")
    print("=" * 100)

    print(
        "1. Look for groups with meaningful N, not just high UP%."
    )
    print(
        "2. A 100% result with N=3 is not a rule."
    )
    print(
        "3. We care about repeatable directional separation."
    )
    print(
        "4. Mean absolute gap tells us whether the condition occurs"
    )
    print(
        "   during meaningful opening moves."
    )
    print(
        "5. The three-way table is exploratory only."
    )
    print(
        "6. Any promising pattern must later be tested out-of-sample."
    )
    print(
        "7. Nothing in this diagnostic changes KISS or the trading engine."
    )

    print()
    print("DONE.")


if __name__ == "__main__":
    main()