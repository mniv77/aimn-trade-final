
"""AIMn Step 59F-4C: causal V18 SHORT execution research.

Independent research only. No production changes.
Uses V18 signal helpers, with next-open execution.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kiss.visual_research import exp58_v4_causal_trailing as v18
from kiss.kiss_exp53_supertrend import calculate_supertrend



def _aimn_atr_35c(rows, period=10):
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    closes = [float(r["close"]) for r in rows]

    tr = []
    for i in range(len(rows)):
        if i == 0:
            value = highs[i] - lows[i]
        else:
            value = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1]),
            )
        tr.append(value)

    atr = [None] * len(rows)
    if len(rows) < period:
        return atr

    atr[period-1] = sum(tr[:period]) / period

    for i in range(period, len(rows)):
        atr[i] = (
            atr[i-1] * (period-1) + tr[i]
        ) / period

    return atr


def run(
    rows,
    entry_cutoff=None,
    commission_pct=0.0,
    entry_slippage_pct=0.02,
    exit_slippage_pct=0.02,
    trailing_minus_pct=0.5,
    rsi_rescue_short=80.0,
    atr_exhaustion_filter=False,
    structural_exit_mode='OFF',
):
    if structural_exit_mode not in ('OFF', 'HH_HL', 'ENTRY_HIGH', 'EITHER'):
        raise ValueError('Unknown structural exit mode')

    rows = sorted([dict(r) for r in rows], key=lambda r: str(r["timestamp"]))
    if not rows:
        raise ValueError("Empty dataset")

    if entry_cutoff is not None:
        from datetime import datetime
        datetime.strptime(entry_cutoff, "%H:%M")

    if min(commission_pct, entry_slippage_pct,
           exit_slippage_pct, trailing_minus_pct) < 0:
        raise ValueError("Negative cost or trailing parameter")

    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    opens = [float(r["open"]) for r in rows]
    times = [str(r["timestamp"]) for r in rows]
    atr_exhaustion_values = _aimn_atr_35c(rows)
    atr_exhaustion_blocked = 0

    if any(x <= 0 for series in (closes, highs, lows, opens)
           for x in series):
        raise ValueError("Nonpositive OHLC price")
    if any(times[i] <= times[i-1] for i in range(1, len(times))):
        raise ValueError("Timestamps must increase strictly")

    states = [v18.get_market_state(closes, i)
              for i in range(len(rows))]
    rsis = v18.rsi_wilder(closes)

    st = calculate_supertrend(rows, atr_period=10, multiplier=3.0)
    short_signals = set(
        st.index[st["st_transition"] == "LONG->SHORT"].tolist()
    )

    trades = []
    position = None
    pending_entry = None
    pending_exit = None
    skipped = 0
    suppressed_same_bar = 0

    def finish(i, fill, reason):
        nonlocal position
        p = position
        gross = (p["entry"] / fill - 1.0) * 100.0
        trade = {
            "entry_signal_time": times[p["signal_i"]],
            "entry_time": times[p["entry_i"]],
            "exit_time": times[i],
            "entry_price": round(p["entry"], 8),
            "exit_price": round(fill, 8),
            "exit_reason": reason,
            "pnl_pct": round(gross, 6),
            "net_pnl_pct": round(gross - 2 * commission_pct, 6),
        }
        trades.append(trade)
        position = None

    for i in range(v18.TREND_WINDOW + 1, len(rows)):
        opened_or_closed = False

        # 1. Fill market exit requested at previous candle close.
        if pending_exit is not None and position is not None:
            fill = opens[i] * (1 + exit_slippage_pct / 100)
            finish(i, fill, pending_exit)
            pending_exit = None
            opened_or_closed = True

        # 2. Fill entry requested at previous candle close.
        if pending_entry is not None and position is None:
            fill = opens[i] * (1 - entry_slippage_pct / 100)
            position = {
                "signal_i": pending_entry,
                "entry_i": i,
                "entry_candle_high": highs[i],
                "entry": fill,
                "stop": fill * (1 + v18.STOP_LOSS_PCT),
                "trough": fill,
                "trail": None,
                "short_reversal_pending": False,
            }
            pending_entry = None
            opened_or_closed = True

        # 3. Active protective orders execute intrabar.
        if position is not None:
            p = position
            reason = None
            level = None

            if highs[i] >= p["stop"]:
                reason = "STOP_LOSS"
                level = p["stop"]
            elif p["trail"] is not None and highs[i] >= p["trail"]:
                reason = "TRAILING_REVERSE"
                level = p["trail"]

            if reason:
                fill = max(opens[i], level)
                fill *= 1 + exit_slippage_pct / 100
                finish(i, fill, reason)
                pending_exit = None
                opened_or_closed = True

        # 4. At candle close, evaluate original V18 exit signals.
        if position is not None:
            p = position
            state = states[i]
            prev = states[i-1]

            short_to_flat = prev == "SHORT" and state == "FLAT"
            flat_to_long = prev == "FLAT" and state == "LONG"
            direct_long = prev == "SHORT" and state == "LONG"

            if short_to_flat:
                p["short_reversal_pending"] = True

            trend_exit = (
                direct_long or
                (p["short_reversal_pending"] and flat_to_long)
            )

            current_profit = (p["entry"] / closes[i] - 1) * 100
            profitable_v = (
                v18.is_v_long(closes, i)
                and current_profit > 2 * commission_pct
            )

            emergency = (
                rsis[i] is not None
                and rsis[i] > rsi_rescue_short
            )

            if profitable_v:
                pending_exit = "V_PROFIT"
            elif trend_exit:
                pending_exit = "TREND_CHANGE"
            elif emergency:
                pending_exit = "RSI_EMERGENCY"

            if pending_exit is None and i > p["entry_i"]:
                higher_high_low = (
                    highs[i] > highs[i - 1]
                    and lows[i] > lows[i - 1]
                )
                entry_high_recovery = (
                    closes[i] > p["entry_candle_high"]
                )

                if structural_exit_mode == "HH_HL":
                    structural_signal = higher_high_low
                elif structural_exit_mode == "ENTRY_HIGH":
                    structural_signal = entry_high_recovery
                elif structural_exit_mode == "EITHER":
                    structural_signal = (
                        higher_high_low or entry_high_recovery
                    )
                else:
                    structural_signal = False

                if structural_signal and i + 1 < len(rows):
                    pending_exit = "STRUCTURAL_EXIT"

            # Trailing protection for the next candle only.
            # Do not retroactively apply today's low to today's high.
            if pending_exit is None:
                p["trough"] = min(p["trough"], lows[i])
                candidate = p["trough"] * (
                    1 + trailing_minus_pct / 100
                )
                p["trail"] = (
                    candidate if p["trail"] is None
                    else min(p["trail"], candidate)
                )

        # 5. V18 entry signal is known only at candle close.
        if position is None and pending_entry is None and i in short_signals:
            if opened_or_closed:
                suppressed_same_bar += 1
                continue

            clock = times[i][11:16]
            if entry_cutoff is not None and clock >= entry_cutoff:
                skipped += 1
                continue

            # Preserve original V18 exhausted 09:30 filter.
            if clock == "09:30":
                opening_move = (closes[i] / opens[i] - 1) * 100
                if opening_move < -0.60:
                    skipped += 1
                    continue

            if atr_exhaustion_filter and i >= 5:
                same_session = (
                    times[i-5][:10] == times[i][:10]
                )
                current_atr = atr_exhaustion_values[i]
                if same_session and current_atr is not None and current_atr > 0:
                    decline_atr = (
                        closes[i-5] - closes[i]
                    ) / current_atr
                    if decline_atr >= 2.0:
                        atr_exhaustion_blocked += 1
                        continue

            if i + 1 < len(rows):
                pending_entry = i

    unresolved = None
    if position is not None:
        unresolved = {
            "entry_time": times[position["entry_i"]],
            "entry_price": position["entry"],
            "last_close": closes[-1],
            "pending_exit": pending_exit,
        }

    return {
        "trades": trades,
        "trade_count": len(trades),
        "net_pnl_pct": round(
            sum(t["net_pnl_pct"] for t in trades), 6
        ),
        "skipped_entries": skipped,
        "suppressed_same_bar_entries": suppressed_same_bar,
        "unresolved_position": unresolved,
        "pending_entry_at_end": pending_entry,
        "atr_exhaustion_blocked": atr_exhaustion_blocked,
        "model": "INTEGRATED_V18_NEXT_BAR_RESEARCH",
    }
