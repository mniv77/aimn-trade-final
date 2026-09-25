"""
KISS Entry Analysis Loader

Purpose:
    Run the CURRENT KISS 30m-trend / 5m-execution engine for LONG and SHORT
    and prepare rows for kiss_long_entry_analysis.

IMPORTANT:
    - Does NOT modify the KISS engine.
    - Defaults to DRY RUN.
    - Uses the existing db.get_db_connection().
    - Uses the same candles table/data path as /kiss_backtest.
"""

from datetime import datetime
from decimal import Decimal

from db import get_db_connection
from engine.kiss_execution_5m import run_kiss_30m_5m


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "NVDA"
TIMEFRAME = "30m"
BROKER_ID = 2

DRY_RUN = True

LIMIT = 5000


# ============================================================
# DATABASE
# ============================================================

def load_candles(symbol, timeframe, limit=5000):
    """
    Load candles using the same mapping used by kiss_backtest_routes.py.
    """
    tf_map = {
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1hr": "1h",
        "1h": "1h",
        "6hr": "6h",
        "6h": "6h",
    }

    db_tf = tf_map.get(timeframe, timeframe)

    conn, cursor = get_db_connection()

    if not conn:
        raise RuntimeError("Database connection failed")

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
            (symbol, db_tf, int(limit)),
        )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def pct_move(entry_price, exit_price, direction):
    """
    Direction-aware percentage move from entry price.
    Positive = favorable.
    Negative = adverse.
    """
    if entry_price in (None, 0) or exit_price is None:
        return None

    if direction == "LONG":
        return ((exit_price / entry_price) - 1.0) * 100.0

    return ((entry_price / exit_price) - 1.0) * 100.0


def find_index_by_time(rows, target_time):
    """
    Find the candle corresponding to target_time.

    MySQL/Python datetime values can differ slightly in representation
    (for example timezone-awareness), so do not require exact object
    equality. Compare normalized timestamps and choose the nearest
    candle within a small tolerance.
    """
    if target_time is None:
        return None

    def normalize(value):
        if value is None:
            return None

        if isinstance(value, datetime):
            # Remove timezone information for comparison only.
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            return value

        try:
            return datetime.fromisoformat(
                str(value).replace("Z", "")
            )
        except Exception:
            return None

    target = normalize(target_time)

    if target is None:
        return None

    best_index = None
    best_seconds = None

    for i, row in enumerate(rows):
        ts = normalize(row.get("timestamp"))

        if ts is None:
            continue

        difference = abs((ts - target).total_seconds())

        if best_seconds is None or difference < best_seconds:
            best_seconds = difference
            best_index = i

    # A 5m candle should never be matched to something far away.
    # Allow up to 3 minutes of timestamp representation difference.
    if best_seconds is not None and best_seconds <= 180:
        return best_index

    return None


def calculate_ma20(closes, index):
    """
    Same basic MA20 concept used by the current KISS state logic.

    MA is calculated from the previous 20 closes, excluding the current
    close, matching get_market_state() in kiss_execution_5m.py.
    """
    if index is None or index < 20:
        return None

    values = closes[index - 20:index]

    if len(values) != 20:
        return None

    return sum(values) / 20.0


def calculate_entry_distance(entry_price, ma20):
    if entry_price is None or ma20 in (None, 0):
        return None

    return ((entry_price / ma20) - 1.0) * 100.0


def calculate_post_entry_moves(execution_rows, entry_index, entry_price, direction):
    """
    Calculate price movement after entry using 5m candles.

    Positive = favorable to the trade.
    Negative = adverse.
    """
    result = {}

    bars = [1, 2, 3, 4, 6, 12]

    for bar in bars:
        idx = entry_index + bar

        key = f"move_{bar}bar_pct"

        if idx >= len(execution_rows):
            result[key] = None
            continue

        close_price = safe_float(execution_rows[idx].get("close"))

        result[key] = pct_move(
            entry_price,
            close_price,
            direction,
        )

    return result


def calculate_mfe_mae(execution_rows, entry_index, exit_index, entry_price, direction):
    """
    Calculate maximum favorable and adverse excursion between entry and exit.

    Uses 5m highs/lows.
    """
    if entry_index is None or exit_index is None:
        return None, None

    if entry_price in (None, 0):
        return None, None

    end = min(exit_index, len(execution_rows) - 1)

    max_favorable = None
    max_adverse = None

    for i in range(entry_index, end + 1):
        row = execution_rows[i]

        high = safe_float(row.get("high"))
        low = safe_float(row.get("low"))

        if high is None or low is None:
            continue

        if direction == "LONG":
            favorable = ((high / entry_price) - 1.0) * 100.0
            adverse = ((low / entry_price) - 1.0) * 100.0

        else:
            favorable = ((entry_price / low) - 1.0) * 100.0
            adverse = ((entry_price / high) - 1.0) * 100.0

        if max_favorable is None or favorable > max_favorable:
            max_favorable = favorable

        if max_adverse is None or adverse < max_adverse:
            max_adverse = adverse

    return max_favorable, max_adverse


def get_result_trades(result):
    """
    Handle the current engine's returned structure without assuming too much.
    """
    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        for key in ("trades", "results", "trade_list"):
            value = result.get(key)

            if isinstance(value, list):
                return value

    raise RuntimeError(
        f"Could not find trade list in KISS result. "
        f"Returned type={type(result)}"
    )


# ============================================================
# BUILD ANALYSIS ROW
# ============================================================

def build_analysis_row(
    trade,
    direction,
    execution_rows,
    trend_rows,
):
    """
    Convert one current KISS trade into one analysis-table row.
    """

    entry_time = trade.get("entry_time")
    exit_time = trade.get("exit_time")

    entry_price = safe_float(
        trade.get("entry_price")
        or trade.get("entry")
    )

    exit_price = safe_float(
        trade.get("exit_price")
        or trade.get("exit")
    )

    trade_id_raw = (
        trade.get("trade_id")
        or trade.get("id")
        or trade.get("label")
        or ""
    )

    trade_id = f"{direction}-{trade_id_raw}"

    entry_index = find_index_by_time(
        execution_rows,
        entry_time,
    )

    exit_index = find_index_by_time(
        execution_rows,
        exit_time,
    )

    if entry_index is None:
        raise RuntimeError(
            f"Could not locate entry candle for {trade_id}: "
            f"{entry_time}"
        )

    closes = [
        safe_float(row.get("close"))
        for row in trend_rows
    ]

    ma20 = None

    # Find the 30m candle at or immediately before the entry time.
    # Normalize both values because the KISS engine may return the
    # trade timestamp as a string while MySQL returns datetime.
    trend_index = None

    def normalize_timestamp(value):
        if value is None:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            return value

        try:
            return datetime.fromisoformat(
                str(value).replace("Z", "")
            )
        except Exception:
            return None

    normalized_entry_time = normalize_timestamp(entry_time)

    for i, row in enumerate(trend_rows):
        ts = normalize_timestamp(row.get("timestamp"))

        if ts is None or normalized_entry_time is None:
            continue

        if ts <= normalized_entry_time:
            trend_index = i
        else:
            break

    if trend_index is not None:
        ma20 = calculate_ma20(
            closes,
            trend_index,
        )

    distance_pct = calculate_entry_distance(
        entry_price,
        ma20,
    )

    # Current KISS trade field names.
    entry_transition = (
        trade.get("entry_transition")
        or trade.get("transition")
        or ""
    )

    transition_from = trade.get("transition_from")
    transition_to = trade.get("transition_to")

    if not transition_from and "->" in entry_transition:
        transition_from, transition_to = (
            entry_transition.split("->", 1)
        )

    transition_shape = (
        trade.get("transition_shape")
        or trade.get("shape")
    )

    entry_rsi = safe_float(
        trade.get("entry_rsi")
    )

    if entry_rsi is None:
        entry_rsi = safe_float(
            trade.get("rsi_entry")
        )

    exit_rsi = safe_float(
        trade.get("exit_rsi")
    )

    moves = calculate_post_entry_moves(
        execution_rows,
        entry_index,
        entry_price,
        direction,
    )

    max_favorable, max_adverse = calculate_mfe_mae(
        execution_rows,
        entry_index,
        exit_index,
        entry_price,
        direction,
    )

    pnl_pct = safe_float(
        trade.get("pnl_pct")
    )

    if pnl_pct is None and entry_price and exit_price:
        pnl_pct = pct_move(
            entry_price,
            exit_price,
            direction,
        )

    exit_reason = (
        trade.get("exit_reason")
        or trade.get("reason")
    )

    entry_state = (
        trade.get("entry_state")
        or transition_to
    )

    # Simple offline assessment.
    if pnl_pct is None:
        entry_assessment = "UNKNOWN"
    elif pnl_pct > 0:
        entry_assessment = "GOOD"
    elif pnl_pct <= -2.0:
        entry_assessment = "BAD"
    else:
        entry_assessment = "WEAK"

    notes_parts = []

    if exit_rsi is not None:
        notes_parts.append(
            f"exit_rsi={exit_rsi:.4f}"
        )

    if max_favorable is not None:
        notes_parts.append(
            f"calc_mfe={max_favorable:.4f}%"
        )

    if max_adverse is not None:
        notes_parts.append(
            f"calc_mae={max_adverse:.4f}%"
        )

    notes_parts.append(
        "source=current_run_kiss_30m_5m"
    )

    notes = "; ".join(notes_parts)

    return {
        "trade_id": trade_id,
        "broker_id": BROKER_ID,
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "direction": direction,
        "entry_time": entry_time,
        "entry_price": entry_price,
        "entry_transition": entry_transition,
        "transition_from": transition_from,
        "transition_to": transition_to,
        "transition_shape": transition_shape,
        "entry_rsi": entry_rsi,
        "entry_ma20": ma20,
        "entry_distance_pct": distance_pct,
        "entry_state": entry_state,

        "move_1bar_pct": moves["move_1bar_pct"],
        "move_2bar_pct": moves["move_2bar_pct"],
        "move_3bar_pct": moves["move_3bar_pct"],
        "move_4bar_pct": moves["move_4bar_pct"],
        "move_6bar_pct": moves["move_6bar_pct"],
        "move_12bar_pct": moves["move_12bar_pct"],

        "max_favorable_pct": max_favorable,
        "max_adverse_pct": max_adverse,

        "exit_time": exit_time,
        "exit_price": exit_price,
        "pnl_pct": pnl_pct,
        "exit_reason": exit_reason,

        "entry_assessment": entry_assessment,
        "notes": notes,
    }


# ============================================================
# PRINT
# ============================================================

def print_trade_summary(row):
    print()
    print("=" * 78)
    print(row["trade_id"])
    print("=" * 78)

    print(
        f"Direction       : {row['direction']}"
    )
    print(
        f"Entry           : {row['entry_time']} @ {row['entry_price']}"
    )
    print(
        f"Transition      : {row['entry_transition']}"
    )
    print(
        f"RSI             : {row['entry_rsi']}"
    )
    print(
        f"MA20            : {row['entry_ma20']}"
    )
    print(
        f"Distance        : {row['entry_distance_pct']}"
    )
    print(
        f"Shape            : {row['transition_shape']}"
    )

    print()
    print("POST ENTRY:")
    print(
        f"  1 bar         : {row['move_1bar_pct']}"
    )
    print(
        f"  2 bars        : {row['move_2bar_pct']}"
    )
    print(
        f"  3 bars        : {row['move_3bar_pct']}"
    )
    print(
        f"  4 bars        : {row['move_4bar_pct']}"
    )
    print(
        f"  6 bars        : {row['move_6bar_pct']}"
    )
    print(
        f"  12 bars       : {row['move_12bar_pct']}"
    )

    print()
    print("TRADE:")
    print(
        f"  MFE           : {row['max_favorable_pct']}"
    )
    print(
        f"  MAE           : {row['max_adverse_pct']}"
    )
    print(
        f"  Exit          : {row['exit_time']} @ {row['exit_price']}"
    )
    print(
        f"  P&L           : {row['pnl_pct']}"
    )
    print(
        f"  Exit reason   : {row['exit_reason']}"
    )
    print(
        f"  Assessment    : {row['entry_assessment']}"
    )


# ============================================================
# DATABASE INSERT
# ============================================================

def insert_rows(rows):
    conn, cursor = get_db_connection()

    if not conn:
        raise RuntimeError("Database connection failed")

    sql = """
        INSERT INTO kiss_long_entry_analysis (
            trade_id,
            broker_id,
            symbol,
            timeframe,
            direction,
            entry_time,
            entry_price,
            entry_transition,
            transition_from,
            transition_to,
            transition_shape,
            entry_rsi,
            entry_ma20,
            entry_distance_pct,
            entry_state,
            move_1bar_pct,
            move_2bar_pct,
            move_3bar_pct,
            move_4bar_pct,
            move_6bar_pct,
            move_12bar_pct,
            max_favorable_pct,
            max_adverse_pct,
            exit_time,
            exit_price,
            pnl_pct,
            exit_reason,
            entry_assessment,
            notes
        )
        VALUES (
            %(trade_id)s,
            %(broker_id)s,
            %(symbol)s,
            %(timeframe)s,
            %(direction)s,
            %(entry_time)s,
            %(entry_price)s,
            %(entry_transition)s,
            %(transition_from)s,
            %(transition_to)s,
            %(transition_shape)s,
            %(entry_rsi)s,
            %(entry_ma20)s,
            %(entry_distance_pct)s,
            %(entry_state)s,
            %(move_1bar_pct)s,
            %(move_2bar_pct)s,
            %(move_3bar_pct)s,
            %(move_4bar_pct)s,
            %(move_6bar_pct)s,
            %(move_12bar_pct)s,
            %(max_favorable_pct)s,
            %(max_adverse_pct)s,
            %(exit_time)s,
            %(exit_price)s,
            %(pnl_pct)s,
            %(exit_reason)s,
            %(entry_assessment)s,
            %(notes)s
        )
    """

    try:
        for row in rows:
            cursor.execute(sql, row)

        conn.commit()

    finally:
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 78)
    print("KISS ENTRY ANALYSIS LOADER")
    print("=" * 78)
    print(
        f"Symbol={SYMBOL} "
        f"Timeframe={TIMEFRAME} "
        f"Broker={BROKER_ID}"
    )
    print(
        f"DRY_RUN={DRY_RUN}"
    )
    print()

    print("Loading 30m candles...")
    trend_rows = load_candles(
        SYMBOL,
        "30m",
        LIMIT,
    )

    print(
        f"30m candles: {len(trend_rows)}"
    )

    print("Loading 5m candles...")
    execution_rows = load_candles(
        SYMBOL,
        "5m",
        LIMIT,
    )

    print(
        f"5m candles: {len(execution_rows)}"
    )

    if not trend_rows:
        raise RuntimeError("No 30m candles found")

    if not execution_rows:
        raise RuntimeError("No 5m candles found")

    all_rows = []

    for direction in ("LONG", "SHORT"):
        print()
        print("-" * 78)
        print(f"RUNNING CURRENT KISS ENGINE: {direction}")
        print("-" * 78)

        result = run_kiss_30m_5m(
            trend_rows,
            execution_rows,
            SYMBOL,
            direction,
        )

        trades = get_result_trades(result)

        print(
            f"Trades returned: {len(trades)}"
        )

        for trade in trades:
            row = build_analysis_row(
                trade,
                direction,
                execution_rows,
                trend_rows,
            )

            all_rows.append(row)

            print_trade_summary(row)

    print()
    print("=" * 78)
    print("ANALYSIS COMPLETE")
    print("=" * 78)
    print(
        f"Total analysis rows: {len(all_rows)}"
    )

    long_count = sum(
        1 for r in all_rows
        if r["direction"] == "LONG"
    )

    short_count = sum(
        1 for r in all_rows
        if r["direction"] == "SHORT"
    )

    print(
        f"LONG rows : {long_count}"
    )
    print(
        f"SHORT rows: {short_count}"
    )

    if DRY_RUN:
        print()
        print("*** DRY RUN ***")
        print(
            "Nothing was written to kiss_long_entry_analysis."
        )
    else:
        print()
        print(
            "Writing rows to kiss_long_entry_analysis..."
        )

        insert_rows(all_rows)

        print(
            f"Inserted {len(all_rows)} rows."
        )


if __name__ == "__main__":
    main()
