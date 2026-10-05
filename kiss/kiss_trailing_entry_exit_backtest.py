#!/usr/bin/env python3
"""
AIMn KISS - Trailing Entry + Trailing Exit Research Backtest

RESEARCH ONLY.

- 5m candles are the single source of truth.
- Six completed 5m candles are reconstructed into each 30m advisor candle.
- 30m advisor uses the existing KISS 20-bar MA +/- 0.20% band.
- After a 30m direction transition, a 5m trailing ENTRY waits for price
  to recover from the adverse extreme.
- Once entered, a 5m trailing EXIT follows the favorable extreme.
- No live orders, no broker calls, no production strategy changes.

Default first experiment:
    entry trail: 0.50%
    exit trail: 1.50%

Usage:
    python kiss/kiss_trailing_entry_exit_backtest.py
    python kiss/kiss_trailing_entry_exit_backtest.py --entry-trail 0.25 --exit-trail 1.50

Outputs:
    kiss/results/kiss_trailing_entry_exit_trades.csv
    kiss/results/kiss_trailing_entry_exit_summary.json

Important research behavior:

ENTRY
------
LONG:
    After a LONG advisor transition, track the lowest 5m low.
    Ignore higher lows.
    Enter when price recovers upward by entry_trail_pct.

SHORT:
    After a SHORT advisor transition, track the highest 5m high.
    Ignore lower highs.
    Enter when price recovers downward by entry_trail_pct.

EXIT
----
LONG:
    After entry, track only the highest favorable price.
    Exit when price falls by exit_trail_pct from that top.

SHORT:
    After entry, track only the lowest favorable price.
    Exit when price rises by exit_trail_pct from that bottom.

CONSERVATIVE INTRABAR RULE
---------------------------
If a candle establishes a new adverse/favorable extreme, that same
candle cannot also trigger the corresponding entry/exit. Intrabar order
is unknown, so the new extreme is recorded first and confirmation must
occur on a later candle.

30M REVERSAL
------------
If a new opposite 30m advisor transition occurs while a position is open:

    1. Close the existing position at the current 5m candle open.
    2. Immediately start a new trailing-entry process for the NEW
       advisor direction.

This is the intended continuous state-machine behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_db_connection


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SYMBOLS = [
    "SPY",
    "QQQ",
    "NVDA",
    "AAPL",
    "TSLA",
    "MSFT",
    "AMZN",
    "GOOGL",
]

TREND_WINDOW = 20
TREND_BAND = 0.002

DEFAULT_ENTRY_TRAIL_PCT = 0.005
DEFAULT_EXIT_TRAIL_PCT = 0.015

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


# ---------------------------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------------------------

def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def utc_from_db_5m(ts: Any) -> datetime:
    """
    DB 5m timestamps are naive New York session timestamps.
    Convert them to UTC for all research timing.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            return ts.astimezone(UTC)

        return ts.replace(tzinfo=ET).astimezone(UTC)

    dt = datetime.fromisoformat(str(ts))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)

    return dt.astimezone(UTC)


def pct(a: float, b: float) -> float:
    """
    Percentage change from b to a.
    """
    return (a / b - 1.0) * 100.0


# ---------------------------------------------------------------------------
# LOAD 5M DATA
# ---------------------------------------------------------------------------

def load_5m(symbol: str) -> List[Dict[str, Any]]:
    conn, cursor = get_db_connection()

    if not conn:
        raise RuntimeError("Database connection failed")

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s AND timeframe='5m'
            ORDER BY timestamp ASC
            """,
            (symbol,),
        )

        rows = cursor.fetchall()

    finally:
        conn.close()

    out: List[Dict[str, Any]] = []

    for r in rows:
        out.append(
            {
                "timestamp": r["timestamp"],
                "utc": utc_from_db_5m(r["timestamp"]),
                "open": num(r["open"]),
                "high": num(r["high"]),
                "low": num(r["low"]),
                "close": num(r["close"]),
                "volume": num(r["volume"]),
            }
        )

    return out


# ---------------------------------------------------------------------------
# RECONSTRUCT 30M FROM 5M
# ---------------------------------------------------------------------------

def reconstruct_30m(
    rows5: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build 30m candles from six consecutive completed 5m session candles.

    The 30m candle timestamp is the UTC timestamp of its first 5m candle.

    known_utc is when the sixth 5m candle has completed.

    No decision may use the 30m candle before known_utc.
    """

    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    for row in rows5:
        local = row["utc"].astimezone(ET)

        # Only regular US session candles.
        if local.hour < 9 or (
            local.hour == 9 and local.minute < 30
        ):
            continue

        if local.hour > 16 or (
            local.hour == 16 and local.minute > 0
        ):
            continue

        if not current:
            current = [row]
            continue

        prev = current[-1]

        same_day = (
            prev["utc"].astimezone(ET).date()
            == local.date()
        )

        five_minutes = row["utc"] - prev["utc"]

        if (
            same_day
            and five_minutes == timedelta(minutes=5)
        ):
            current.append(row)

        else:
            if len(current) == 6:
                groups.append(current)

            current = [row]

        if len(current) == 6:
            groups.append(current)
            current = []

    if len(current) == 6:
        groups.append(current)

    out: List[Dict[str, Any]] = []

    for g in groups:
        out.append(
            {
                "timestamp": g[0]["utc"],
                "known_utc": (
                    g[-1]["utc"]
                    + timedelta(minutes=5)
                ),
                "open": g[0]["open"],
                "high": max(x["high"] for x in g),
                "low": min(x["low"] for x in g),
                "close": g[-1]["close"],
                "volume": sum(x["volume"] for x in g),
            }
        )

    return out


# ---------------------------------------------------------------------------
# 30M MARKET STATE
# ---------------------------------------------------------------------------

def market_state(
    closes: List[float],
    i: int,
) -> str:

    if i < TREND_WINDOW:
        return "FLAT"

    ma = sum(
        closes[i - TREND_WINDOW:i]
    ) / TREND_WINDOW

    if closes[i] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[i] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


# ---------------------------------------------------------------------------
# TRADE RECORD
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    trade_id: str
    symbol: str
    direction: str

    transition_time_utc: str
    transition_known_utc: str

    entry_extreme_time_utc: str
    entry_trigger_time_utc: str
    entry_time_utc: str

    exit_extreme_time_utc: str
    exit_time_utc: str

    transition_from: str
    transition_to: str

    entry_extreme: float
    entry_trigger: float
    entry_price: float

    exit_extreme: float
    exit_trigger: float
    exit_price: float

    pnl_pct: float

    max_favorable_pct: float
    max_adverse_pct: float

    exit_reason: str

    entry_wait_minutes: float
    trade_minutes: float


# ---------------------------------------------------------------------------
# RUN ONE SYMBOL
# ---------------------------------------------------------------------------

def run_symbol(
    symbol: str,
    rows5: List[Dict[str, Any]],
    entry_trail_pct: float,
    exit_trail_pct: float,
) -> List[Trade]:

    # ---------------------------------------------------------------
    # Reconstruct 30m advisor candles from 5m source of truth.
    # ---------------------------------------------------------------

    rows30 = reconstruct_30m(rows5)

    if len(rows30) <= TREND_WINDOW:
        return []

    closes30 = [
        x["close"]
        for x in rows30
    ]

    states = [
        market_state(closes30, i)
        for i in range(len(rows30))
    ]

    # ---------------------------------------------------------------
    # Detect 30m advisor transitions.
    # ---------------------------------------------------------------

    events: List[Dict[str, Any]] = []

    for i in range(
        TREND_WINDOW + 1,
        len(rows30),
    ):
        old = states[i - 1]
        new = states[i]

        if (
            new in {"LONG", "SHORT"}
            and new != old
        ):
            events.append(
                {
                    "transition_time": rows30[i]["timestamp"],
                    "known_utc": rows30[i]["known_utc"],
                    "from": old,
                    "to": new,
                }
            )

    # ---------------------------------------------------------------
    # State machine.
    #
    # position = active trade
    # pending  = trailing entry waiting to trigger
    # ---------------------------------------------------------------

    trades: List[Trade] = []

    event_i = 0

    pending: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, Any]] = None

    # ---------------------------------------------------------------
    # Process every 5m candle chronologically.
    # ---------------------------------------------------------------

    for row in rows5:

        ts = row["utc"]

        # ===========================================================
        # PROCESS NEW 30M ADVISOR EVENTS
        # ===========================================================

        while (
            event_i < len(events)
            and events[event_i]["known_utc"] <= ts
        ):
            event = events[event_i]
            event_i += 1

            # -------------------------------------------------------
            # NO ACTIVE POSITION
            #
            # Start trailing entry for the advisor direction.
            # -------------------------------------------------------

            if position is None:

                pending = {
                    **event,
                    "extreme": (
                        row["low"]
                        if event["to"] == "LONG"
                        else row["high"]
                    ),
                    "extreme_time": ts,
                    "triggered": False,
                }

            # -------------------------------------------------------
            # ACTIVE POSITION
            #
            # If advisor changes to the opposite direction:
            #
            #   1. Close current trade.
            #   2. Start trailing entry for NEW direction.
            # -------------------------------------------------------

            else:

                opposite = (
                    "SHORT"
                    if position["direction"] == "LONG"
                    else "LONG"
                )

                if event["to"] == opposite:

                    exit_price = row["open"]

                    direction = position["direction"]

                    pnl = (
                        pct(
                            exit_price,
                            position["entry_price"],
                        )
                        if direction == "LONG"
                        else pct(
                            position["entry_price"],
                            exit_price,
                        )
                    )

                    trades.append(
                        Trade(
                            trade_id=(
                                f"{symbol}-"
                                f"{len(trades)+1:05d}"
                            ),
                            symbol=symbol,
                            direction=direction,

                            transition_time_utc=(
                                position[
                                    "transition_time"
                                ].isoformat()
                            ),

                            transition_known_utc=(
                                position[
                                    "transition_known"
                                ].isoformat()
                            ),

                            entry_extreme_time_utc=(
                                position[
                                    "entry_extreme_time"
                                ].isoformat()
                            ),

                            entry_trigger_time_utc=(
                                position[
                                    "entry_trigger_time"
                                ].isoformat()
                            ),

                            entry_time_utc=(
                                position[
                                    "entry_time"
                                ].isoformat()
                            ),

                            exit_extreme_time_utc=(
                                position[
                                    "exit_extreme_time"
                                ].isoformat()
                            ),

                            exit_time_utc=ts.isoformat(),

                            transition_from=(
                                position[
                                    "transition_from"
                                ]
                            ),

                            transition_to=direction,

                            entry_extreme=round(
                                position[
                                    "entry_extreme"
                                ],
                                8,
                            ),

                            entry_trigger=round(
                                position[
                                    "entry_trigger"
                                ],
                                8,
                            ),

                            entry_price=round(
                                position[
                                    "entry_price"
                                ],
                                8,
                            ),

                            exit_extreme=round(
                                position[
                                    "exit_extreme"
                                ],
                                8,
                            ),

                            exit_trigger=round(
                                position[
                                    "exit_trigger"
                                ],
                                8,
                            ),

                            exit_price=round(
                                exit_price,
                                8,
                            ),

                            pnl_pct=round(
                                pnl,
                                6,
                            ),

                            max_favorable_pct=round(
                                position[
                                    "max_favorable"
                                ],
                                6,
                            ),

                            max_adverse_pct=round(
                                position[
                                    "max_adverse"
                                ],
                                6,
                            ),

                            exit_reason=(
                                "30M_TREND_REVERSAL"
                            ),

                            entry_wait_minutes=(
                                (
                                    position[
                                        "entry_time"
                                    ]
                                    - position[
                                        "transition_known"
                                    ]
                                ).total_seconds()
                                / 60.0
                            ),

                            trade_minutes=(
                                (
                                    ts
                                    - position[
                                        "entry_time"
                                    ]
                                ).total_seconds()
                                / 60.0
                            ),
                        )
                    )

                    # ------------------------------------------------
                    # Close old position.
                    # ------------------------------------------------

                    position = None

                    # ------------------------------------------------
                    # IMPORTANT:
                    #
                    # Start trailing entry for the NEW advisor
                    # direction.
                    #
                    # This is the intentional correction.
                    # ------------------------------------------------

                    pending = {
                        **event,
                        "extreme": (
                            row["low"]
                            if event["to"] == "LONG"
                            else row["high"]
                        ),
                        "extreme_time": ts,
                        "triggered": False,
                    }

        # ===========================================================
        # TRAILING ENTRY
        # ===========================================================

        if (
            position is None
            and pending is not None
        ):

            direction = pending["to"]

            # -------------------------------------------------------
            # LONG ENTRY
            # -------------------------------------------------------

            if direction == "LONG":

                new_extreme = (
                    row["low"]
                    < pending["extreme"]
                )

                if new_extreme:

                    pending["extreme"] = row["low"]
                    pending["extreme_time"] = ts

                trigger = (
                    pending["extreme"]
                    * (1.0 + entry_trail_pct)
                )

                # Conservative intrabar rule:
                # a candle that makes the new low cannot also
                # trigger the recovery entry.
                if (
                    not new_extreme
                    and row["high"] >= trigger
                    and ts > pending["known_utc"]
                ):

                    entry_price = trigger

                    position = {
                        "direction": "LONG",

                        "transition_time": (
                            pending[
                                "transition_time"
                            ]
                        ),

                        "transition_known": (
                            pending[
                                "known_utc"
                            ]
                        ),

                        "transition_from": (
                            pending[
                                "from"
                            ]
                        ),

                        "entry_extreme": (
                            pending[
                                "extreme"
                            ]
                        ),

                        "entry_extreme_time": (
                            pending[
                                "extreme_time"
                            ]
                        ),

                        "entry_trigger": trigger,
                        "entry_trigger_time": ts,
                        "entry_time": ts,
                        "entry_price": entry_price,

                        "exit_extreme": entry_price,
                        "exit_extreme_time": ts,

                        "max_favorable": 0.0,

                        "max_adverse": min(
                            0.0,
                            pct(
                                row["low"],
                                entry_price,
                            ),
                        ),
                    }

                    pending = None

            # -------------------------------------------------------
            # SHORT ENTRY
            # -------------------------------------------------------

            else:

                new_extreme = (
                    row["high"]
                    > pending["extreme"]
                )

                if new_extreme:

                    pending["extreme"] = row["high"]
                    pending["extreme_time"] = ts

                trigger = (
                    pending["extreme"]
                    * (1.0 - entry_trail_pct)
                )

                # Conservative intrabar rule:
                # a candle that makes the new high cannot also
                # trigger the recovery entry.
                if (
                    not new_extreme
                    and row["low"] <= trigger
                    and ts > pending["known_utc"]
                ):

                    entry_price = trigger

                    position = {
                        "direction": "SHORT",

                        "transition_time": (
                            pending[
                                "transition_time"
                            ]
                        ),

                        "transition_known": (
                            pending[
                                "known_utc"
                            ]
                        ),

                        "transition_from": (
                            pending[
                                "from"
                            ]
                        ),

                        "entry_extreme": (
                            pending[
                                "extreme"
                            ]
                        ),

                        "entry_extreme_time": (
                            pending[
                                "extreme_time"
                            ]
                        ),

                        "entry_trigger": trigger,
                        "entry_trigger_time": ts,
                        "entry_time": ts,
                        "entry_price": entry_price,

                        "exit_extreme": entry_price,
                        "exit_extreme_time": ts,

                        "max_favorable": 0.0,

                        "max_adverse": min(
                            0.0,
                            pct(
                                entry_price,
                                row["high"],
                            ),
                        ),
                    }

                    pending = None

        # ===========================================================
        # NO POSITION
        # ===========================================================

        if position is None:
            continue

        direction = position["direction"]

        # ===========================================================
        # TRAILING EXIT — LONG
        # ===========================================================

        if direction == "LONG":

            new_extreme = (
                row["high"]
                > position["exit_extreme"]
            )

            if new_extreme:

                position["exit_extreme"] = row["high"]
                position["exit_extreme_time"] = ts

            position["max_favorable"] = max(
                position["max_favorable"],
                pct(
                    position["exit_extreme"],
                    position["entry_price"],
                ),
            )

            position["max_adverse"] = min(
                position["max_adverse"],
                pct(
                    row["low"],
                    position["entry_price"],
                ),
            )

            exit_trigger = (
                position["exit_extreme"]
                * (1.0 - exit_trail_pct)
            )

            hit = (
                not new_extreme
                and row["low"] <= exit_trigger
            )

        # ===========================================================
        # TRAILING EXIT — SHORT
        # ===========================================================

        else:

            new_extreme = (
                row["low"]
                < position["exit_extreme"]
            )

            if new_extreme:

                position["exit_extreme"] = row["low"]
                position["exit_extreme_time"] = ts

            position["max_favorable"] = max(
                position["max_favorable"],
                pct(
                    position["entry_price"],
                    position["exit_extreme"],
                ),
            )

            position["max_adverse"] = min(
                position["max_adverse"],
                pct(
                    position["entry_price"],
                    row["high"],
                ),
            )

            exit_trigger = (
                position["exit_extreme"]
                * (1.0 + exit_trail_pct)
            )

            hit = (
                not new_extreme
                and row["high"] >= exit_trigger
            )

        position["exit_trigger"] = exit_trigger

        # ===========================================================
        # TRAILING EXIT TRIGGERED
        # ===========================================================

        if (
            hit
            and ts > position["entry_time"]
        ):

            exit_price = exit_trigger

            pnl = (
                pct(
                    exit_price,
                    position["entry_price"],
                )
                if direction == "LONG"
                else pct(
                    position["entry_price"],
                    exit_price,
                )
            )

            trades.append(
                Trade(
                    trade_id=(
                        f"{symbol}-"
                        f"{len(trades)+1:05d}"
                    ),

                    symbol=symbol,
                    direction=direction,

                    transition_time_utc=(
                        position[
                            "transition_time"
                        ].isoformat()
                    ),

                    transition_known_utc=(
                        position[
                            "transition_known"
                        ].isoformat()
                    ),

                    entry_extreme_time_utc=(
                        position[
                            "entry_extreme_time"
                        ].isoformat()
                    ),

                    entry_trigger_time_utc=(
                        position[
                            "entry_trigger_time"
                        ].isoformat()
                    ),

                    entry_time_utc=(
                        position[
                            "entry_time"
                        ].isoformat()
                    ),

                    exit_extreme_time_utc=(
                        position[
                            "exit_extreme_time"
                        ].isoformat()
                    ),

                    exit_time_utc=ts.isoformat(),

                    transition_from=(
                        position[
                            "transition_from"
                        ]
                    ),

                    transition_to=direction,

                    entry_extreme=round(
                        position[
                            "entry_extreme"
                        ],
                        8,
                    ),

                    entry_trigger=round(
                        position[
                            "entry_trigger"
                        ],
                        8,
                    ),

                    entry_price=round(
                        position[
                            "entry_price"
                        ],
                        8,
                    ),

                    exit_extreme=round(
                        position[
                            "exit_extreme"
                        ],
                        8,
                    ),

                    exit_trigger=round(
                        exit_trigger,
                        8,
                    ),

                    exit_price=round(
                        exit_price,
                        8,
                    ),

                    pnl_pct=round(
                        pnl,
                        6,
                    ),

                    max_favorable_pct=round(
                        position[
                            "max_favorable"
                        ],
                        6,
                    ),

                    max_adverse_pct=round(
                        position[
                            "max_adverse"
                        ],
                        6,
                    ),

                    exit_reason="TRAILING_EXIT",

                    entry_wait_minutes=(
                        (
                            position[
                                "entry_time"
                            ]
                            - position[
                                "transition_known"
                            ]
                        ).total_seconds()
                        / 60.0
                    ),

                    trade_minutes=(
                        (
                            ts
                            - position[
                                "entry_time"
                            ]
                        ).total_seconds()
                        / 60.0
                    ),
                )
            )

            position = None

    # ===============================================================
    # END OF DATA
    # ===============================================================

    if position is not None:

        row = rows5[-1]

        exit_price = row["close"]

        direction = position["direction"]

        pnl = (
            pct(
                exit_price,
                position["entry_price"],
            )
            if direction == "LONG"
            else pct(
                position["entry_price"],
                exit_price,
            )
        )

        trades.append(
            Trade(
                trade_id=(
                    f"{symbol}-"
                    f"{len(trades)+1:05d}"
                ),

                symbol=symbol,
                direction=direction,

                transition_time_utc=(
                    position[
                        "transition_time"
                    ].isoformat()
                ),

                transition_known_utc=(
                    position[
                        "transition_known"
                    ].isoformat()
                ),

                entry_extreme_time_utc=(
                    position[
                        "entry_extreme_time"
                    ].isoformat()
                ),

                entry_trigger_time_utc=(
                    position[
                        "entry_trigger_time"
                    ].isoformat()
                ),

                entry_time_utc=(
                    position[
                        "entry_time"
                    ].isoformat()
                ),

                exit_extreme_time_utc=(
                    position[
                        "exit_extreme_time"
                    ].isoformat()
                ),

                exit_time_utc=row[
                    "utc"
                ].isoformat(),

                transition_from=(
                    position[
                        "transition_from"
                    ]
                ),

                transition_to=direction,

                entry_extreme=round(
                    position[
                        "entry_extreme"
                    ],
                    8,
                ),

                entry_trigger=round(
                    position[
                        "entry_trigger"
                    ],
                    8,
                ),

                entry_price=round(
                    position[
                        "entry_price"
                    ],
                    8,
                ),

                exit_extreme=round(
                    position[
                        "exit_extreme"
                    ],
                    8,
                ),

                exit_trigger=round(
                    position.get(
                        "exit_trigger",
                        exit_price,
                    ),
                    8,
                ),

                exit_price=round(
                    exit_price,
                    8,
                ),

                pnl_pct=round(
                    pnl,
                    6,
                ),

                max_favorable_pct=round(
                    position[
                        "max_favorable"
                    ],
                    6,
                ),

                max_adverse_pct=round(
                    position[
                        "max_adverse"
                    ],
                    6,
                ),

                exit_reason="END_OF_DATA",

                entry_wait_minutes=(
                    (
                        position[
                            "entry_time"
                        ]
                        - position[
                            "transition_known"
                        ]
                    ).total_seconds()
                    / 60.0
                ),

                trade_minutes=(
                    (
                        row["utc"]
                        - position[
                            "entry_time"
                        ]
                    ).total_seconds()
                    / 60.0
                ),
            )
        )

    return trades


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--entry-trail",
        type=float,
        default=DEFAULT_ENTRY_TRAIL_PCT * 100.0,
        help="Entry trailing distance in percent.",
    )

    parser.add_argument(
        "--exit-trail",
        type=float,
        default=DEFAULT_EXIT_TRAIL_PCT * 100.0,
        help="Exit trailing distance in percent.",
    )

    args = parser.parse_args()

    entry_trail = args.entry_trail / 100.0
    exit_trail = args.exit_trail / 100.0

    all_trades: List[Trade] = []
    symbol_summary: List[Dict[str, Any]] = []

    for symbol in SYMBOLS:

        print(f"[LOAD] {symbol}")

        rows5 = load_5m(symbol)

        if not rows5:
            print(
                f"[SKIP] {symbol}: no 5m data"
            )
            continue

        trades = run_symbol(
            symbol,
            rows5,
            entry_trail,
            exit_trail,
        )

        all_trades.extend(trades)

        pnl = sum(
            t.pnl_pct
            for t in trades
        )

        winners = sum(
            t.pnl_pct > 0
            for t in trades
        )

        symbol_summary.append(
            {
                "symbol": symbol,
                "candles_5m": len(rows5),
                "trades": len(trades),
                "winners": winners,
                "losers": (
                    len(trades) - winners
                ),
                "win_rate_pct": (
                    round(
                        winners
                        / len(trades)
                        * 100.0,
                        2,
                    )
                    if trades
                    else 0.0
                ),
                "total_pnl_pct": round(
                    pnl,
                    4,
                ),
                "avg_pnl_pct": (
                    round(
                        pnl / len(trades),
                        4,
                    )
                    if trades
                    else 0.0
                ),
            }
        )

    # -----------------------------------------------------------------------
    # RESULTS
    # -----------------------------------------------------------------------

    results_dir = Path("kiss/results")

    results_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = (
        results_dir
        / "kiss_trailing_entry_exit_trades.csv"
    )

    json_path = (
        results_dir
        / "kiss_trailing_entry_exit_summary.json"
    )

    # -----------------------------------------------------------------------
    # TRADE CSV
    # -----------------------------------------------------------------------

    if all_trades:

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=list(
                    asdict(
                        all_trades[0]
                    ).keys()
                ),
            )

            writer.writeheader()

            writer.writerows(
                asdict(t)
                for t in all_trades
            )

    # -----------------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------------

    total_pnl = sum(
        t.pnl_pct
        for t in all_trades
    )

    total_winners = sum(
        t.pnl_pct > 0
        for t in all_trades
    )

    total_losers = (
        len(all_trades)
        - total_winners
    )

    summary = {
        "research_only": True,

        "entry_trail_pct": args.entry_trail,
        "exit_trail_pct": args.exit_trail,

        "trend_window": TREND_WINDOW,
        "trend_band_pct": TREND_BAND * 100.0,

        "source_timeframe": "5m",
        "advisor_timeframe": "30m",

        "symbols": SYMBOLS,

        "total_trades": len(all_trades),

        "winners": total_winners,
        "losers": total_losers,

        "win_rate_pct": (
            round(
                total_winners
                / len(all_trades)
                * 100.0,
                2,
            )
            if all_trades
            else 0.0
        ),

        "total_pnl_pct": round(
            total_pnl,
            4,
        ),

        "average_pnl_pct": (
            round(
                total_pnl
                / len(all_trades),
                4,
            )
            if all_trades
            else 0.0
        ),

        "symbols": symbol_summary,
    }

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
        )

    # -----------------------------------------------------------------------
    # CONSOLE SUMMARY
    # -----------------------------------------------------------------------

    print()
    print("=" * 72)
    print("AIMn KISS TRAILING ENTRY + EXIT RESEARCH")
    print("=" * 72)

    print(
        f"Entry trail : {args.entry_trail:.3f}%"
    )

    print(
        f"Exit trail  : {args.exit_trail:.3f}%"
    )

    print(
        f"Trades      : {len(all_trades)}"
    )

    print(
        f"Winners     : {total_winners}"
    )

    print(
        f"Losers      : {total_losers}"
    )

    print(
        f"Win rate    : {summary['win_rate_pct']:.2f}%"
    )

    print(
        f"Total P&L   : {total_pnl:.4f}%"
    )

    print(
        f"Average P&L : "
        f"{summary['average_pnl_pct']:.4f}%"
    )

    print("=" * 72)

    print()
    print("Per-symbol results:")

    for item in symbol_summary:

        print(
            f"{item['symbol']:>5}  "
            f"trades={item['trades']:4d}  "
            f"win={item['win_rate_pct']:6.2f}%  "
            f"pnl={item['total_pnl_pct']:9.4f}%"
        )

    print()
    print(f"[OUTPUT] {csv_path}")
    print(f"[OUTPUT] {json_path}")


if __name__ == "__main__":
    main()
