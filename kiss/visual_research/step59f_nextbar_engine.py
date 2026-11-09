
"""AIMn Step 59F: independent next-bar execution research prototype.

This module models execution timing and protective orders.
It does not yet reproduce every V18 exit decision.
It must not be used as a validated Step 54 replacement.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional


@dataclass
class Position:
    entry_i: int
    entry_price: float
    signal_i: int
    stop_price: float
    trough: float
    trail_active: bool = False
    trail_price: Optional[float] = None


def timestamp(row):
    return str(row["timestamp"])


def price(row, key):
    return float(row[key])


def short_return_pct(entry, exit_price):
    return (entry / exit_price - 1.0) * 100.0


def simulate(
    rows: list[dict[str, Any]],
    entry_signals: set[int],
    exit_signals: set[int],
    entry_cutoff: Optional[str] = None,
    stop_loss_pct: float = 1.5,
    trailing_start_pct: float = 1.5,
    trailing_minus_pct: float = 0.5,
    commission_pct: float = 0.0,
    entry_slippage_pct: float = 0.02,
    exit_slippage_pct: float = 0.02,
):
    """Execute externally supplied causal close-confirmed signals.

    Signal index i is known only after candle i closes.
    Market orders execute at the opening of candle i+1.

    SHORT stop orders use the worse of stop and opening gap.
    Trailing levels are established only after completed bars.
    No same-bar trailing update can trigger retroactively.
    """

    if stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct must be positive")
    if trailing_start_pct < 0 or trailing_minus_pct < 0:
        raise ValueError("Trailing percentages cannot be negative")
    if any(x < 0 for x in (
        commission_pct, entry_slippage_pct, exit_slippage_pct
    )):
        raise ValueError("Costs cannot be negative")

    if entry_cutoff is not None:
        if len(entry_cutoff) != 5 or entry_cutoff[2] != ":":
            raise ValueError("Use HH:MM for entry_cutoff")

    for i, r in enumerate(rows):
        o, h, l, c = (price(r, k) for k in ("open", "high", "low", "close"))
        if min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c):
            raise ValueError(f"Invalid OHLC candle at index {i}")
        if i and timestamp(r) <= timestamp(rows[i - 1]):
            raise ValueError("Candles must be strictly chronological")

    trades = []
    position = None
    pending_entry = None
    pending_exit = None
    skipped_entries = 0

    for i, row in enumerate(rows):
        op = price(row, "open")
        hi = price(row, "high")
        lo = price(row, "low")
        close = price(row, "close")

        # Orders from previous completed candle execute at this open.
        if pending_exit is not None and position is not None:
            fill = op * (1.0 + exit_slippage_pct / 100.0)
            reason = pending_exit
            pending_exit = None
            trades.append({
                "entry_signal_time": timestamp(rows[position.signal_i]),
                "entry_time": timestamp(rows[position.entry_i]),
                "exit_time": timestamp(row),
                "entry_price": position.entry_price,
                "exit_price": fill,
                "exit_reason": reason,
                "pnl_pct": short_return_pct(position.entry_price, fill),
                "net_pnl_pct": (
                    short_return_pct(position.entry_price, fill)
                    - 2 * commission_pct
                ),
            })
            position = None

        if pending_entry is not None and position is None:
            fill = op * (1.0 - entry_slippage_pct / 100.0)
            position = Position(
                entry_i=i,
                entry_price=fill,
                signal_i=pending_entry,
                stop_price=fill * (1.0 + stop_loss_pct / 100.0),
                trough=fill,
            )
            pending_entry = None

        # Active protective orders, evaluated before close signals.
        if position is not None:
            reason = None
            level = None

            if hi >= position.stop_price:
                reason = "STOP_LOSS"
                level = position.stop_price

            elif (
                position.trail_active
                and position.trail_price is not None
                and hi >= position.trail_price
            ):
                reason = "TRAILING_REVERSE"
                level = position.trail_price

            if reason is not None:
                # SHORT buy-to-cover: an adverse opening gap
                # cannot receive a better fill than the open.
                fill = max(op, level)
                fill *= 1.0 + exit_slippage_pct / 100.0

                trades.append({
                    "entry_signal_time": timestamp(rows[position.signal_i]),
                    "entry_time": timestamp(rows[position.entry_i]),
                    "exit_time": timestamp(row),
                    "entry_price": position.entry_price,
                    "exit_price": fill,
                    "exit_reason": reason,
                    "pnl_pct": short_return_pct(position.entry_price, fill),
                    "net_pnl_pct": (
                        short_return_pct(position.entry_price, fill)
                        - 2 * commission_pct
                    ),
                })
                position = None
                pending_exit = None

        # Close-confirmed structural exit signals.
        if position is not None and i in exit_signals:
            if i + 1 < len(rows):
                pending_exit = "SIGNAL_EXIT"

        # Trailing protection is updated AFTER the candle closes.
        # Do not update it from a candle whose exit is already pending.
        if position is not None and pending_exit is None:
            position.trough = min(position.trough, lo)
            favorable_pct = (
                (position.entry_price / position.trough - 1.0) * 100.0
            )
            if favorable_pct >= trailing_start_pct:
                position.trail_active = True
                candidate = position.trough * (
                    1.0 + trailing_minus_pct / 100.0
                )
                position.trail_price = (
                    candidate if position.trail_price is None
                    else min(position.trail_price, candidate)
                )

        # Close-confirmed entry signals, subject to cutoff.
        if position is None and pending_entry is None and i in entry_signals:
            clock = timestamp(row)[11:16]
            if entry_cutoff is not None and clock >= entry_cutoff:
                skipped_entries += 1
            elif i + 1 < len(rows):
                pending_entry = i

    unresolved = None
    if position is not None:
        unresolved = {
            "entry_time": timestamp(rows[position.entry_i]),
            "entry_price": position.entry_price,
            "last_close": price(rows[-1], "close"),
            "pending_exit": pending_exit,
            "status": "OPEN_AT_DATA_END",
        }

    return {
        "trades": trades,
        "trade_count": len(trades),
        "total_net_pnl_pct": round(
            sum(t["net_pnl_pct"] for t in trades), 6
        ),
        "skipped_entry_signals": skipped_entries,
        "unresolved_position": unresolved,
        "pending_entry_at_end": pending_entry,
        "execution_model": "NEXT_BAR_OPEN_WITH_GAP_AWARE_STOPS",
        "signal_model": "EXTERNAL_CAUSAL_SIGNALS",
    }


def self_test():
    # Signal at 09:30; entry at 09:35 open.
    # A later overnight opening gap breaches the stop.
    rows = [
        {"timestamp": "2026-01-05 09:30", "open": 100,
         "high": 101, "low": 99, "close": 100},
        {"timestamp": "2026-01-05 09:35", "open": 100,
         "high": 100.5, "low": 99, "close": 99.5},
        {"timestamp": "2026-01-06 09:30", "open": 105,
         "high": 106, "low": 104, "close": 105},
    ]

    result = simulate(
        rows,
        entry_signals={0},
        exit_signals=set(),
        entry_slippage_pct=0,
        exit_slippage_pct=0,
        trailing_start_pct=10,
    )

    assert result["trade_count"] == 1
    trade = result["trades"][0]
    assert trade["entry_time"] == "2026-01-05 09:35"
    assert trade["entry_price"] == 100
    assert trade["exit_price"] == 105
    assert trade["exit_reason"] == "STOP_LOSS"

    # A signal on the final candle cannot fill without next-bar data.
    result2 = simulate(
        rows,
        entry_signals={2},
        exit_signals=set(),
    )
    assert result2["trade_count"] == 0
    assert result2["pending_entry_at_end"] is None

    return True


if __name__ == "__main__":
    assert self_test()
    print("NEXT-BAR EXECUTION SELF-TEST: PASS")
    print("Overnight stop gap: PASS")
    print("No same-close entry: PASS")
    print("No artificial final close: PASS")
