"""Independent AiMn KISS V3 backtest.

This module deliberately does not call the existing tuner or its strategy code.
It implements the strategy specification in doc/strategy/AiMn-KISS-Strategy-V3-full.md
for a clean comparison baseline.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
import math

TRAIL_PCT = 0.015
TREND_WINDOW = 20
TREND_BAND = 0.002

# SHORT tactic V12 entry parameters:
# The entry should react close to the high-side reversal, while the existing
# trailing-minus value remains the EXIT distance. Do not use the exit distance
# as the entry delay.
SHORT_SWING_LOOKBACK = 30
SHORT_ENTRY_PULLBACK_PCT = 0.20
SHORT_ENTRY_MAX_PEAK_AGE = 1
SHORT_ENTRY_RSI_MIN = 70.0
SHORT_ENTRY_PEAK_MAX_AGE = 1
SHORT_MAJOR_HILL_MULTIPLE = 2.0

CONFIRM_BARS = 3
MIN_CONFIRM = 2
RSI_PERIOD = 14
RSI_LONG_EMERGENCY = 20.0
RSI_SHORT_EMERGENCY = 80.0
# Document 2 specifies a stop-loss but does not specify its percentage.
# It is therefore disabled for the clean baseline rather than invented.
STOP_LOSS_PCT = 0.0


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rsi_wilder(closes: Sequence[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    """Wilder RSI used ONLY as the emergency protection circuit."""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out
    gains, losses = [], []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def value(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        return 100.0 - (100.0 / (1.0 + g / l))

    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = ((avg_gain * (period - 1)) + gains[i - 1]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i - 1]) / period
        out[i] = value(avg_gain, avg_loss)
    return out


def get_market_state(closes: Sequence[float], idx: int, window: int = TREND_WINDOW) -> str:
    """Simple LONG/SHORT/FLAT state from price versus its recent mean."""
    if idx < window or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - window:idx]) / window
    price = closes[idx]
    if price > ma * (1.0 + TREND_BAND):
        return "LONG"
    if price < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def is_v_long(closes: Sequence[float], idx: int) -> bool:
    return idx >= 2 and closes[idx - 2] > closes[idx - 1] < closes[idx]


def is_v_short(closes: Sequence[float], idx: int) -> bool:
    return idx >= 2 and closes[idx - 2] < closes[idx - 1] > closes[idx]


def is_short_peak_reversal(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    states: Sequence[str],
    idx: int,
    lookback: int = SHORT_SWING_LOOKBACK,
) -> bool:
    """True on the first down candle after a meaningful local high.

    The candidate peak is idx-1. We only use data through idx, so there is no
    future-looking confirmation. The candidate must:
      1) have been in LONG state,
      2) have the highest high over the preceding lookback bars,
      3) not be exceeded by the current candle,
      4) turn down now (lower close and lower/equal low).

    This is the tactical SHORT entry: HIGH -> FIRST MOVE DOWN -> ENTER.
    """
    if idx < lookback + 1 or idx >= len(highs):
        return False

    peak_i = idx - 1
    prior_highs = highs[peak_i - lookback:peak_i]
    if len(prior_highs) < lookback:
        return False

    if states[peak_i] != "LONG":
        return False

    peak_high = highs[peak_i]
    if peak_high < max(prior_highs):
        return False

    # The current candle confirms that the peak is not being exceeded.
    if highs[idx] > peak_high:
        return False

    # First actual move down from the peak.
    if closes[idx] >= closes[peak_i]:
        return False
    if lows[idx] > lows[peak_i]:
        return False

    return True


def find_transition(closes: Sequence[float], idx: int) -> Optional[Dict[str, Any]]:
    """Return a transition ending at idx; no future candles are inspected."""
    if idx < TREND_WINDOW + 1:
        return None
    new_state = get_market_state(closes, idx)
    previous = get_market_state(closes, idx - 1)
    if new_state == previous:
        return None
    return {
        "from": previous,
        "to": new_state,
        "index": idx,
        "v_shape": "V-LONG" if is_v_long(closes, idx) else ("V-SHORT" if is_v_short(closes, idx) else None),
    }


@dataclass
class KISSTrade:
    trade_id: str
    symbol: str
    direction: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    entry_transition: str
    transition_shape: Optional[str]
    exit_reason: str
    max_favorable_pct: float
    max_adverse_pct: float
    entry_rsi: Optional[float]
    exit_rsi: Optional[float]
    entry_reference_high: Optional[float] = None
    entry_trigger_price: Optional[float] = None
    entry_peak_time: Optional[str] = None
    entry_peak_age_candles: Optional[int] = None
    entry_pullback_from_peak_pct: Optional[float] = None


@dataclass
class KISSResult:
    symbol: str
    direction: str
    timeframe: str
    candle_count: int
    trades: List[Dict[str, Any]]
    total_pnl_pct: float
    win_rate_pct: float
    avg_pnl_pct: float
    loser_count: int
    winner_count: int
    transition_count: int
    rsi_rescue_long: float = RSI_LONG_EMERGENCY
    rsi_rescue_short: float = RSI_SHORT_EMERGENCY
    total_commission_pct: float = 0.0
    total_net_pnl_pct: float = 0.0
    data_warning: Optional[str] = None


def _ts(v: Any) -> str:
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    return str(v)


def _confirmed_reverse(states: Sequence[str], start_i: int, new_state: str) -> bool:
    """Require at least 2 of the next 3 completed candles in the new state."""
    end = min(len(states), start_i + 1 + CONFIRM_BARS)
    checked = states[start_i + 1:end]
    return len(checked) >= CONFIRM_BARS and sum(s == new_state for s in checked) >= MIN_CONFIRM


def run_kiss_backtest(
    rows: Sequence[Dict[str, Any]],
    symbol: str,
    direction: str,
    timeframe: str,
    rsi_rescue_long: float = RSI_LONG_EMERGENCY,
    rsi_rescue_short: float = RSI_SHORT_EMERGENCY,
    trailing_minus_pct: float = TRAIL_PCT * 100.0,
    commission_pct: float = 0.0,
) -> Dict[str, Any]:
    """Run the independent KISS strategy on chronological candle dictionaries."""
    if str(timeframe).lower() not in {"5m", "5min"}:
        raise ValueError("AIMn research baseline uses 5m candles only")
    if not (0.0 <= float(rsi_rescue_long) <= 50.0):
        raise ValueError("LONG RSI rescue threshold must be between 0 and 50")
    if not (50.0 <= float(rsi_rescue_short) <= 100.0):
        raise ValueError("SHORT RSI rescue threshold must be between 50 and 100")
    if float(trailing_minus_pct) <= 0:
        raise ValueError("Trailing minus percentage must be greater than zero")
    if float(commission_pct) < 0:
        raise ValueError("Commission percentage cannot be negative")
    rows = list(rows)
    if not rows:
        raise ValueError("No candles available for this symbol/timeframe")
    rows.sort(key=lambda r: r.get("timestamp"))
    closes = [_num(r.get("close")) for r in rows]
    highs = [_num(r.get("high")) for r in rows]
    lows = [_num(r.get("low")) for r in rows]
    if any(math.isnan(x) for x in closes + highs + lows):
        raise ValueError("Candle data contains invalid OHLC prices")

    states = [get_market_state(closes, i) for i in range(len(rows))]
    rsis = rsi_wilder(closes)
    direction = direction.upper()
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("Direction must be LONG or SHORT")

    trades: List[KISSTrade] = []
    transitions = 0
    position = None
    peak = None
    trough = None
    max_fav = 0.0
    max_adv = 0.0
    pending_entry = None
    pending_exit = None

    # SHORT tactic V12 state:
    # Remember the complete current LONG move (hill): its floor, highest
    # price, peak time, and peak RSI. This prevents a small local bump inside
    # a longer move from becoming the SHORT entry.
    long_run_peak = None
    long_run_peak_i = None
    long_run_floor = None
    long_run_bars = 0
    long_run_peak_rsi = None
    # Entry is based on a recent price high, not on the lagging MA state.
    # We look for a high in the recent 20-candle window and require the
    # current candle to give back the configured trailing-minus amount.
    i = TREND_WINDOW + 1
    while i < len(rows):
        state = states[i]
        prev_state = states[i - 1]
        if state != prev_state:
            transitions += 1

        # ---------------- Entry ----------------
        # SHORT tactic V12:
        #   1) Build the CURRENT LONG "hill".
        #   2) Keep its highest peak and lowest point.
        #   3) Require the hill to be materially larger than normal noise.
        #   4) When price first turns down from the major peak, enter SHORT.
        #
        # The entry is deliberately fast. We do not wait for a delayed
        # 3-candle state confirmation.
        if direction == "SHORT":
            pending_entry = None

            if state == "LONG":
                if prev_state != "LONG" or long_run_peak is None:
                    long_run_peak = highs[i]
                    long_run_peak_i = i
                    long_run_floor = lows[i]
                    long_run_bars = 1
                    long_run_peak_rsi = rsis[i]
                else:
                    long_run_bars += 1
                    long_run_floor = min(long_run_floor, lows[i])

                    if highs[i] > long_run_peak:
                        long_run_peak = highs[i]
                        long_run_peak_i = i
                        long_run_peak_rsi = rsis[i]

            elif prev_state == "LONG" and state == "SHORT":
                # Keep the completed LONG hill for this first SHORT candle.
                pass
            elif state == "FLAT":
                long_run_peak = None
                long_run_peak_i = None
                long_run_floor = None
                long_run_bars = 0
                long_run_peak_rsi = None

            if long_run_peak is not None and long_run_floor not in (None, 0):
                peak_age = i - long_run_peak_i
                hill_rise_pct = (
                    (long_run_peak / long_run_floor) - 1.0
                ) * 100.0

                # "Big hill" = at least two trailing-minus distances.
                # With the current 0.50% trailing-minus this is 1.00%.
                major_hill = (
                    hill_rise_pct
                    >= SHORT_MAJOR_HILL_MULTIPLE * float(trailing_minus_pct)
                )

                trigger_price = long_run_peak * (
                    1.0 - SHORT_ENTRY_PULLBACK_PCT / 100.0
                )

                # Fast reversal from the major peak. We allow the current
                # candle to cross the trigger intrabar; this is the earliest
                # causal signal available from OHLC data.
                turn_down = (
                    lows[i] <= trigger_price
                    and closes[i] < closes[i - 1]
                    and i > long_run_peak_i
                )

                same_bar_reversal = (
                    i == long_run_peak_i
                    and lows[i] <= trigger_price
                    and closes[i] < closes[i - 1]
                )

                peak_rsi = long_run_peak_rsi
                current_rsi = rsis[i]
                rsi_supports_reversal = (
                    peak_rsi is not None
                    and current_rsi is not None
                    and peak_rsi >= SHORT_ENTRY_RSI_MIN
                    and current_rsi < peak_rsi
                )

                if (
                    position is None
                    and long_run_bars >= 3
                    and peak_age <= SHORT_ENTRY_PEAK_MAX_AGE
                    and major_hill
                    and rsi_supports_reversal
                    and (turn_down or same_bar_reversal)
                ):
                    entry_i = i
                    entry = min(
                        float(rows[i]["open"]),
                        float(trigger_price),
                    )

                    position = {
                        "direction": direction,
                        "entry_i": entry_i,
                        "entry": entry,
                        "entry_transition": "LONG->SHORT",
                        "shape": "V-SHORT" if is_v_short(closes, i) else None,
                        "entry_reference_high": long_run_peak,
                        "entry_trigger_price": trigger_price,
                        "entry_peak_i": long_run_peak_i,
                        "short_reversal_pending": False,
                    }
                    peak = entry
                    trough = entry
                    max_fav = 0.0
                    max_adv = 0.0
                    pending_exit = None

                    long_run_peak = None
                    long_run_peak_i = None
                    long_run_floor = None
                    long_run_bars = 0
                    long_run_peak_rsi = None

        else:
            # LONG side remains unchanged for this controlled SHORT-only test.
            if pending_entry is not None:
                if state == pending_entry["to"]:
                    pending_entry["hits"] += 1
                pending_entry["checked"] += 1
                if pending_entry["checked"] >= CONFIRM_BARS:
                    if pending_entry["hits"] >= MIN_CONFIRM and position is None and pending_entry["to"] == direction:
                        entry_i = i
                        entry = closes[i]
                        position = {
                            "direction": direction,
                            "entry_i": entry_i,
                            "entry": entry,
                            "entry_transition": f"{pending_entry['from']}->{direction}",
                            "shape": pending_entry.get("shape"),
                        }
                        peak = entry
                        trough = entry
                        max_fav = 0.0
                        max_adv = 0.0
                    pending_entry = None

            if position is None and state != prev_state and state in {"LONG", "SHORT"}:
                pending_entry = {
                    "from": prev_state,
                    "to": state,
                    "hits": 0,
                    "checked": 0,
                    "shape": "V-LONG" if is_v_long(closes, i) else ("V-SHORT" if is_v_short(closes, i) else None),
                }

        # ---------------- Open position ----------------
        if position is not None:
            entry = position["entry"]
            price = closes[i]
            if position["direction"] == "LONG":
                peak = max(peak, highs[i])
                trough = min(trough, lows[i])
                max_fav = max(max_fav, (peak / entry - 1.0) * 100.0)
                max_adv = min(max_adv, (lows[i] / entry - 1.0) * 100.0)
                trail_hit = price < peak * (1.0 - float(trailing_minus_pct) / 100.0)
                emergency = rsis[i] is not None and rsis[i] < float(rsi_rescue_long)
                stop_hit = STOP_LOSS_PCT > 0 and price <= entry * (1.0 - STOP_LOSS_PCT)
                opposite = "SHORT"
            else:
                trough = min(trough, lows[i])
                peak = max(peak, highs[i])
                max_fav = max(max_fav, (entry / trough - 1.0) * 100.0)
                max_adv = min(max_adv, (entry / highs[i] - 1.0) * 100.0)
                trail_hit = price > trough * (1.0 + float(trailing_minus_pct) / 100.0)
                emergency = rsis[i] is not None and rsis[i] > float(rsi_rescue_short)
                stop_hit = STOP_LOSS_PCT > 0 and price >= entry * (1.0 + STOP_LOSS_PCT)
                opposite = "LONG"

            if position["direction"] == "SHORT":
                # SHORT EXIT V4:
                # A brief FLAT pause is part of the reversal and must not
                # erase the SHORT position. Exit on the FIRST FLAT->LONG
                # confirmation after the SHORT move, rather than waiting for
                # a later LONG->... state transition.
                #
                # The trailing reversal remains available only as an
                # emergency/protection mechanism; normal exit is the first
                # causal SHORT -> FLAT -> LONG turn.
                reason = None
                short_trail_level = None
                short_trail_hit = False

                if i > position["entry_i"] and trough is not None:
                    short_trail_level = trough * (
                        1.0 + float(trailing_minus_pct) / 100.0
                    )
                    short_trail_hit = highs[i] >= short_trail_level

                short_to_flat = prev_state == "SHORT" and state == "FLAT"
                flat_to_long = prev_state == "FLAT" and state == "LONG"
                short_to_long_direct = prev_state == "SHORT" and state == "LONG"

                # Preserve a pending SHORT reversal across the FLAT candle.
                if state == "FLAT" and short_to_flat:
                    position["short_reversal_pending"] = True

                pending_flat_to_long = bool(
                    position.get("short_reversal_pending", False)
                ) and flat_to_long

                # V-LONG profit protection for SHORT:
                # If price makes a causal V-Long (down -> up) while the
                # SHORT is already profitable enough to cover the full
                # round-trip commission, protect the profit immediately.
                # If the SHORT is not profitable enough, do NOT exit merely
                # because of the V; allow the market to prove the reversal.
                current_short_pnl_pct = ((entry / price) - 1.0) * 100.0
                round_trip_commission_pct = float(commission_pct) * 2.0
                profitable_v_long = (
                    is_v_long(closes, i)
                    and current_short_pnl_pct > round_trip_commission_pct
                )

                if profitable_v_long:
                    reason = "V_PROFIT"
                elif pending_flat_to_long or short_to_long_direct:
                    reason = "TREND_CHANGE"
                elif emergency:
                    reason = "RSI_EMERGENCY"
                elif stop_hit:
                    reason = "STOP_LOSS"
                elif short_trail_hit:
                    reason = "TRAILING_REVERSE"
            else:
                # LONG side remains unchanged for this controlled SHORT-only test.
                # A trailing retracement is still followed by the existing 2-of-3
                # confirmation logic on LONG.
                if pending_exit is None and (trail_hit or state == opposite):
                    pending_exit = {
                        "to": opposite,
                        "started": i,
                        "hits": 0,
                        "checked": 0,
                        "reason": "TRAILING_TREND_CHANGE" if trail_hit else "TREND_CHANGE",
                    }

                if pending_exit is not None:
                    if state == pending_exit["to"]:
                        pending_exit["hits"] += 1
                    pending_exit["checked"] += 1

                reason = None
                if emergency:
                    reason = "RSI_EMERGENCY"
                elif stop_hit:
                    reason = "STOP_LOSS"
                elif pending_exit is not None and pending_exit["checked"] >= CONFIRM_BARS and pending_exit["hits"] >= MIN_CONFIRM:
                    reason = pending_exit["reason"]

            if reason:
                if position["direction"] == "SHORT" and reason == "TRAILING_REVERSE" and short_trail_level is not None:
                    # Model the trailing stop fill at the trigger level unless
                    # the candle opened through it, in which case use the open.
                    exit_price = max(float(rows[i]["open"]), float(short_trail_level))
                else:
                    # For the structural SHORT->FLAT->LONG exit, exit on this
                    # actual reversal candle at the available close price.
                    exit_price = price
                pnl = ((exit_price / entry) - 1.0) * 100.0 if position["direction"] == "LONG" else ((entry / exit_price) - 1.0) * 100.0
                trades.append(KISSTrade(
                    trade_id=f"KISS-{len(trades)+1:05d}",
                    symbol=symbol,
                    direction=position["direction"],
                    entry_time=_ts(rows[position["entry_i"]].get("timestamp")),
                    exit_time=_ts(rows[i].get("timestamp")),
                    entry_price=round(entry, 8),
                    exit_price=round(exit_price, 8),
                    pnl_pct=round(pnl, 6),
                    entry_transition=position["entry_transition"],
                    transition_shape=position["shape"],
                    exit_reason=reason,
                    max_favorable_pct=round(max_fav, 6),
                    max_adverse_pct=round(max_adv, 6),
                    entry_rsi=rsis[position["entry_i"]],
                    exit_rsi=rsis[i],
                    entry_reference_high=round(position.get("entry_reference_high"), 8) if position.get("entry_reference_high") is not None else None,
                    entry_trigger_price=round(position.get("entry_trigger_price"), 8) if position.get("entry_trigger_price") is not None else None,
                    entry_peak_time=_ts(rows[position["entry_peak_i"]].get("timestamp")) if position.get("entry_peak_i") is not None else None,
                    entry_peak_age_candles=(position["entry_i"] - position["entry_peak_i"]) if position.get("entry_peak_i") is not None else None,
                    entry_pullback_from_peak_pct=round(((entry / position["entry_reference_high"]) - 1.0) * 100.0, 6) if position.get("entry_reference_high") not in (None, 0) else None,
                ))
                position = None
                peak = trough = None
                pending_exit = None

        i += 1

    # Close an open position at the final available candle.
    if position is not None:
        i = len(rows) - 1
        entry = position["entry"]
        exit_price = closes[i]
        pnl = ((exit_price / entry) - 1.0) * 100.0 if position["direction"] == "LONG" else ((entry / exit_price) - 1.0) * 100.0
        trades.append(KISSTrade(
            trade_id=f"KISS-{len(trades)+1:05d}", symbol=symbol, direction=position["direction"],
            entry_time=_ts(rows[position["entry_i"]].get("timestamp")), exit_time=_ts(rows[i].get("timestamp")),
            entry_price=round(entry, 8), exit_price=round(exit_price, 8), pnl_pct=round(pnl, 6),
            entry_transition=position["entry_transition"], transition_shape=position["shape"],
            exit_reason="END_OF_DATA", max_favorable_pct=round(max_fav, 6), max_adverse_pct=round(max_adv, 6),
            entry_rsi=rsis[position["entry_i"]], exit_rsi=rsis[i]
        ))

    payload = [asdict(t) for t in trades]
    for t in payload:
        t["commission_pct"] = round(float(commission_pct) * 2.0, 6)
        t["net_pnl_pct"] = round(float(t["pnl_pct"]) - t["commission_pct"], 6)
    total = sum(t["pnl_pct"] for t in payload)
    total_commission = sum(t["commission_pct"] for t in payload)
    total_net = sum(t["net_pnl_pct"] for t in payload)
    winners = sum(1 for t in payload if t["net_pnl_pct"] > 0)
    losers = len(payload) - winners
    return asdict(KISSResult(
        symbol=symbol, direction=direction, timeframe="5m", candle_count=len(rows),
        trades=payload, total_pnl_pct=round(total, 6),
        win_rate_pct=round((winners / len(payload) * 100.0) if payload else 0.0, 4),
        avg_pnl_pct=round((total / len(payload)) if payload else 0.0, 6),
        loser_count=losers, winner_count=winners, transition_count=transitions,
        rsi_rescue_long=round(float(rsi_rescue_long), 6),
        rsi_rescue_short=round(float(rsi_rescue_short), 6),
        total_commission_pct=round(total_commission, 6),
        total_net_pnl_pct=round(total_net, 6),
        data_warning=(
            "Commission model is 0.0% unless a broker-specific commission is supplied."
            if float(commission_pct) == 0.0 else None
        ),
    ))
