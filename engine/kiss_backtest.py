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
CONFIRM_BARS = 3
MIN_CONFIRM = 2
RSI_PERIOD = 14
RSI_LONG_EMERGENCY = 20.0
RSI_SHORT_EMERGENCY = 80.0
# The strategy document specifies a stop-loss but not its percentage.
# Keep it disabled for the first clean baseline rather than inventing a value.
STOP_LOSS_PCT = 0.0


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rsi_wilder(closes: Sequence[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    """Small self-contained Wilder RSI used ONLY as emergency protection."""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out
    gains = []
    losses = []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    def value(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return 100.0 - (100.0 / (1.0 + rs))
    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = ((avg_gain * (period - 1)) + gains[i - 1]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i - 1]) / period
        out[i] = value(avg_gain, avg_loss)
    return out


def get_market_state(closes: Sequence[float], idx: int, window: int = TREND_WINDOW) -> str:
    """Return LONG/SHORT/FLAT from price location versus its recent mean."""
    if idx < window or idx >= len(closes):
        return "FLAT"
    segment = closes[idx - window:idx]
    ma = sum(segment) / window
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


def find_transition(closes: Sequence[float], idx: int) -> Optional[Dict[str, Any]]:
    """Find the latest state transition ending at idx without scanning beyond it."""
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
    data_warning: Optional[str] = None


def _ts(v: Any) -> str:
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    return str(v)


def run_kiss_backtest(rows: Sequence[Dict[str, Any]], symbol: str, direction: str, timeframe: str) -> Dict[str, Any]:
    """Run the independent KISS strategy on chronological candle dictionaries."""
    rows = list(rows)
    if not rows:
        raise ValueError("No candles available for this symbol/timeframe")
    rows.sort(key=lambda r: r.get("timestamp"))
    closes = [_num(r.get("close")) for r in rows]
    highs = [_num(r.get("high")) for r in rows]
    lows = [_num(r.get("low")) for r in rows]
    if any(math.isnan(x) for x in closes):
        raise ValueError("Candle data contains invalid close prices")
    rsis = rsi_wilder(closes)
    direction = direction.upper()
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("Direction must be LONG or SHORT")

    trades: List[KISSTrade] = []
    transitions = 0
    position = None
    transition_info = None
    peak = None
    trough = None
    max_fav = 0.0
    max_adv = 0.0
    pending = None

    for i in range(TREND_WINDOW + 1, len(rows)):
        state = get_market_state(closes, i)
        prev_state = get_market_state(closes, i - 1)
        if state != prev_state:
            transitions += 1

        # Confirm a new directional state with 2 of the next 3 candles.
        if pending is not None:
            target = pending["to"]
            if state == target:
                pending["hits"] += 1
            pending["checked"] += 1
            if pending["checked"] >= CONFIRM_BARS:
                confirmed = pending["hits"] >= MIN_CONFIRM
                if confirmed and position is None and target == direction:
                    entry_i = i
                    entry = closes[entry_i]
                    position = {
                        "direction": target,
                        "entry_i": entry_i,
                        "entry": entry,
                        "entry_transition": f"{pending['from']}->{target}",
                        "shape": pending.get("shape"),
                    }
                    peak = entry
                    trough = entry
                    max_fav = 0.0
                    max_adv = 0.0
                pending = None

        if state != prev_state and state in {"LONG", "SHORT"}:
            pending = {
                "from": prev_state,
                "to": state,
                "hits": 0,
                "checked": 0,
                "shape": "V-LONG" if is_v_long(closes, i) else ("V-SHORT" if is_v_short(closes, i) else None),
            }

        if position is not None:
            entry = position["entry"]
            price = closes[i]
            if position["direction"] == "LONG":
                peak = max(peak, highs[i])
                trough = min(trough, lows[i])
                fav = (peak / entry - 1.0) * 100.0
                adv = (lows[i] / entry - 1.0) * 100.0
                max_fav = max(max_fav, fav)
                max_adv = min(max_adv, adv)
                trail_hit = price < peak * (1.0 - TRAIL_PCT)
                emergency = rsis[i] is not None and rsis[i] < RSI_LONG_EMERGENCY
                stop_hit = STOP_LOSS_PCT > 0 and price <= entry * (1.0 - STOP_LOSS_PCT)
            else:
                trough = min(trough, lows[i])
                peak = max(peak, highs[i])
                fav = (entry / trough - 1.0) * 100.0
                adv = (entry / highs[i] - 1.0) * 100.0
                max_fav = max(max_fav, fav)
                max_adv = min(max_adv, adv)
                trail_hit = price > trough * (1.0 + TRAIL_PCT)
                emergency = rsis[i] is not None and rsis[i] > RSI_SHORT_EMERGENCY
                stop_hit = STOP_LOSS_PCT > 0 and price >= entry * (1.0 + STOP_LOSS_PCT)

            meaningful_reverse = state in {"LONG", "SHORT"} and state != position["direction"]
            reason = None
            if emergency:
                reason = "RSI_EMERGENCY"
            elif stop_hit:
                reason = "STOP_LOSS"
            elif trail_hit:
                reason = "TRAILING_TREND_CHANGE"
            elif meaningful_reverse:
                reason = "TREND_CHANGE"

            if reason:
                exit_price = price
                if position["direction"] == "LONG":
                    pnl = (exit_price / entry - 1.0) * 100.0
                else:
                    pnl = (entry / exit_price - 1.0) * 100.0
                trade = KISSTrade(
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
                )
                trades.append(trade)
                position = None
                peak = trough = None

    # Close an open position at the last candle for an honest finite backtest.
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
    total = sum(t["pnl_pct"] for t in payload)
    winners = sum(1 for t in payload if t["pnl_pct"] > 0)
    losers = len(payload) - winners
    return asdict(KISSResult(
        symbol=symbol, direction=direction, timeframe=timeframe, candle_count=len(rows),
        trades=payload, total_pnl_pct=round(total, 6),
        win_rate_pct=round((winners / len(payload) * 100.0) if payload else 0.0, 4),
        avg_pnl_pct=round((total / len(payload)) if payload else 0.0, 6),
        loser_count=losers, winner_count=winners, transition_count=transitions,
    ))
