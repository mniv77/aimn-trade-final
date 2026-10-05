"""Independent KISS 30m-trend / 5m-execution experiment.

This version deliberately fixes EXIT timing first.
- 30m candles decide the major/global trend.
- 5m candles execute exits.
- A known 30m reversal against an open trade exits on the first available 5m candle.
- A 5m trailing reversal is confirmed by 2 of the next 3 candles and exits on the
  second confirming candle, rather than waiting for the third.
- RSI remains emergency protection only.
- Entry logic is intentionally left conservative for the next experiment.

Trailing parameters are explicit so every report shows exactly what was tested:
START = 0.0% (active from entry), MINUS = 1.5% from the favorable peak/trough.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
import math

TREND_WINDOW = 20
TREND_BAND = 0.002
CONFIRM_BARS = 3
MIN_CONFIRM = 2
TRAIL_START_PCT = 0.0
TRAIL_MINUS_PCT = 0.015
# Backward-compatible alias: the KISS document calls this the 1.5% trail.
TRAIL_PCT = TRAIL_MINUS_PCT
RSI_PERIOD = 14
RSI_LONG_EMERGENCY = 20.0
RSI_SHORT_EMERGENCY = 80.0


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _ts(v: Any) -> str:
    return v.isoformat(sep=" ") if isinstance(v, datetime) else str(v)


def rsi_wilder(closes: Sequence[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def value(g: float, l: float) -> float:
        return 100.0 if l == 0 else 100.0 - (100.0 / (1.0 + g / l))

    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, len(out)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i - 1]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i - 1]) / period
        out[i] = value(avg_gain, avg_loss)
    return out


def get_market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def _v_shape(closes: Sequence[float], idx: int) -> Optional[str]:
    if idx < 2:
        return None
    a, b, c = closes[idx - 2], closes[idx - 1], closes[idx]
    if a > b < c:
        return "V-LONG"
    if a < b > c:
        return "V-SHORT"
    return None


def _exit_confirm_index(closes: Sequence[float], start: int, direction: str) -> Optional[int]:
    """Return the earliest of the next 3 candles with 2 confirming moves.

    LONG exits need two down moves; SHORT exits need two up moves.
    This deliberately exits on the second confirmation instead of waiting for
    all three candles, reducing the delay that produced the observed late exits.
    """
    hits = 0
    end = min(len(closes), start + CONFIRM_BARS + 1)
    for j in range(start + 1, end):
        if direction == "LONG" and closes[j] < closes[j - 1]:
            hits += 1
        elif direction == "SHORT" and closes[j] > closes[j - 1]:
            hits += 1
        if hits >= MIN_CONFIRM:
            return j
    return None


def _entry_confirmed(closes: Sequence[float], start: int, direction: str) -> bool:
    """Keep the original conservative entry rule unchanged."""
    if start + CONFIRM_BARS >= len(closes):
        return False
    hits = 0
    for j in range(start + 1, start + CONFIRM_BARS + 1):
        if direction == "LONG" and closes[j] > closes[j - 1]:
            hits += 1
        elif direction == "SHORT" and closes[j] < closes[j - 1]:
            hits += 1
    return hits >= MIN_CONFIRM


@dataclass
class KISS5Trade:
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
    exit_transition: Optional[str]
    exit_reason: str
    max_favorable_pct: float
    max_adverse_pct: float
    entry_rsi: Optional[float]
    exit_rsi: Optional[float]


def _make_trade(
    trades: List[KISS5Trade], symbol: str, direction: str,
    execution_rows: Sequence[Dict[str, Any]], rsis: Sequence[Optional[float]],
    position: Dict[str, Any], exit_i: int, exit_reason: str,
    exit_transition: Optional[str], max_fav: float, max_adv: float,
) -> KISS5Trade:
    entry_i = position["entry_i"]
    entry = position["entry"]
    exit_price = _num(execution_rows[exit_i].get("close"))
    pnl = ((exit_price / entry) - 1.0) * 100.0 if direction == "LONG" else ((entry / exit_price) - 1.0) * 100.0
    return KISS5Trade(
        trade_id=f"KISS5-{len(trades)+1:05d}",
        symbol=symbol,
        direction=direction,
        entry_time=_ts(execution_rows[entry_i].get("timestamp")),
        exit_time=_ts(execution_rows[exit_i].get("timestamp")),
        entry_price=round(entry, 8),
        exit_price=round(exit_price, 8),
        pnl_pct=round(pnl, 6),
        entry_transition=position["transition"],
        transition_shape=position.get("shape"),
        exit_transition=exit_transition,
        exit_reason=exit_reason,
        max_favorable_pct=round(max_fav, 6),
        max_adverse_pct=round(max_adv, 6),
        entry_rsi=rsis[entry_i],
        exit_rsi=rsis[exit_i],
    )


def run_kiss_30m_5m(
    trend_rows: Sequence[Dict[str, Any]],
    execution_rows: Sequence[Dict[str, Any]],
    symbol: str,
    direction: str,
) -> Dict[str, Any]:
    """Run the KISS experiment with 30m trend decisions and 5m execution."""
    trend_rows = sorted(list(trend_rows), key=lambda r: r.get("timestamp"))
    execution_rows = sorted(list(execution_rows), key=lambda r: r.get("timestamp"))
    if not trend_rows or not execution_rows:
        raise ValueError("Both 30m trend data and 5m execution data are required")

    direction = direction.upper()
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("Direction must be LONG or SHORT")

    trend_closes = [_num(r.get("close")) for r in trend_rows]
    ex_closes = [_num(r.get("close")) for r in execution_rows]
    ex_highs = [_num(r.get("high")) for r in execution_rows]
    ex_lows = [_num(r.get("low")) for r in execution_rows]
    if any(math.isnan(x) for x in trend_closes + ex_closes + ex_highs + ex_lows):
        raise ValueError("Candle data contains invalid OHLC prices")

    trend_states = [get_market_state(trend_closes, i) for i in range(len(trend_rows))]
    trend_events = []
    for i in range(TREND_WINDOW + 1, len(trend_rows)):
        if trend_states[i] != trend_states[i - 1]:
            trend_events.append({
                "time": trend_rows[i].get("timestamp"),
                "from": trend_states[i - 1],
                "to": trend_states[i],
                "shape": _v_shape(trend_closes, i),
            })

    rsis = rsi_wilder(ex_closes)
    trades: List[KISS5Trade] = []
    position: Optional[Dict[str, Any]] = None
    peak = None
    trough = None
    max_fav = 0.0
    max_adv = 0.0
    pending_entry = None
    pending_trail = None
    event_index = 0

    for i, row in enumerate(execution_rows):
        ts = row.get("timestamp")

        # Every 30m transition is explicit: from -> to. While in a trade,
        # ONLY a transition TO the opposite direction can close it. A move to
        # FLAT is intentionally not an exit, per the KISS strategy document.
        while event_index < len(trend_events) and trend_events[event_index]["time"] <= ts:
            event = trend_events[event_index]
            event_index += 1
            target = event["to"]
            if position is None:
                if target == direction:
                    pending_entry = {
                        "start": i,
                        "from": event["from"],
                        "to": target,
                        "shape": event["shape"],
                    }
            else:
                opposite = "SHORT" if position["direction"] == "LONG" else "LONG"
                if target == opposite:
                    trade = _make_trade(
                        trades, symbol, position["direction"], execution_rows, rsis,
                        position, i, "30M_TREND_REVERSAL",
                        f"{event['from']}->{event['to']}", max_fav, max_adv,
                    )
                    trades.append(trade)
                    position = None
                    pending_trail = None
                    peak = trough = None
                    max_fav = max_adv = 0.0
                    if target == direction:
                        pending_entry = {
                            "start": i, "from": event["from"],
                            "to": target, "shape": event["shape"],
                        }

        # Conservative ENTRY is unchanged: only use 5m confirmation after the
        # 30m decision. This experiment is about EXIT first.
        if position is None and pending_entry is not None:
            start = pending_entry["start"]
            if i >= start + CONFIRM_BARS and _entry_confirmed(ex_closes, start, direction):
                entry_i = start + CONFIRM_BARS
                entry = ex_closes[entry_i]
                position = {
                    "direction": direction,
                    "entry_i": entry_i,
                    "entry": entry,
                    "transition": f"{pending_entry['from']}->{direction}",
                    "shape": pending_entry.get("shape"),
                }
                peak = trough = entry
                max_fav = max_adv = 0.0
                pending_entry = None

        if position is None:
            continue

        entry = position["entry"]
        price = ex_closes[i]
        if position["direction"] == "LONG":
            peak = max(peak, ex_highs[i])
            trough = min(trough, ex_lows[i])
            max_fav = max(max_fav, (peak / entry - 1.0) * 100.0)
            max_adv = min(max_adv, (ex_lows[i] / entry - 1.0) * 100.0)
            trail_hit = peak >= entry * (1.0 + TRAIL_START_PCT) and price < peak * (1.0 - TRAIL_MINUS_PCT)
            emergency = rsis[i] is not None and rsis[i] < RSI_LONG_EMERGENCY
            opposite = "SHORT"
        else:
            trough = min(trough, ex_lows[i])
            peak = max(peak, ex_highs[i])
            max_fav = max(max_fav, (entry / trough - 1.0) * 100.0)
            max_adv = min(max_adv, (entry / ex_highs[i] - 1.0) * 100.0)
            trail_hit = trough <= entry * (1.0 - TRAIL_START_PCT) and price > trough * (1.0 + TRAIL_MINUS_PCT)
            emergency = rsis[i] is not None and rsis[i] > RSI_SHORT_EMERGENCY
            opposite = "LONG"

        if emergency:
            trades.append(_make_trade(
                trades, symbol, position["direction"], execution_rows, rsis,
                position, i, "RSI_EMERGENCY", None, max_fav, max_adv,
            ))
            position = None
            pending_trail = None
            peak = trough = None
            max_fav = max_adv = 0.0
            continue

        # Trailing take-profit: the retracement is a real exit trigger. We still
        # protect against one-candle noise by requiring 2 of the next 3 5m moves,
        # but the exit occurs on the SECOND confirmation, not after a full 3-bar wait.
        if pending_trail is None and trail_hit:
            pending_trail = {
                "start": i,
                "target": opposite,
                "reason": "TRAILING_TAKE_PROFIT",
            }
        if pending_trail is not None and i > pending_trail["start"]:
            exit_i = _exit_confirm_index(ex_closes, pending_trail["start"], position["direction"])
            if exit_i == i:
                trades.append(_make_trade(
                    trades, symbol, position["direction"], execution_rows, rsis,
                    position, i, pending_trail["reason"],
                    f"{position['direction']}->{pending_trail['target']}", max_fav, max_adv,
                ))
                position = None
                pending_trail = None
                peak = trough = None
                max_fav = max_adv = 0.0

    if position is not None:
        i = len(execution_rows) - 1
        trades.append(_make_trade(
            trades, symbol, position["direction"], execution_rows, rsis,
            position, i, "END_OF_DATA", None, max_fav, max_adv,
        ))

    payload = [asdict(t) for t in trades]
    total = sum(t["pnl_pct"] for t in payload)
    winners = sum(t["pnl_pct"] > 0 for t in payload)
    return {
        "symbol": symbol,
        "direction": direction,
        "decision_timeframe": "30m",
        "execution_timeframe": "5m",
        "candle_count_30m": len(trend_rows),
        "candle_count_5m": len(execution_rows),
        "trailing_start_pct": TRAIL_START_PCT * 100.0,
        "trailing_minus_pct": TRAIL_MINUS_PCT * 100.0,
        "trailing_description": f"Starts at +{TRAIL_START_PCT * 100.0:.1f}% and exits after a {TRAIL_MINUS_PCT * 100.0:.1f}% retracement from peak/trough with 2-of-3 5m confirmation.",
        "trades": payload,
        "total_pnl_pct": round(total, 6),
        "win_rate_pct": round((winners / len(payload) * 100.0) if payload else 0.0, 4),
        "avg_pnl_pct": round((total / len(payload)) if payload else 0.0, 6),
        "loser_count": sum(t["pnl_pct"] <= 0 for t in payload),
        "winner_count": winners,
        "transition_count": len(trend_events),
    }