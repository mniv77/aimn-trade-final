"""Independent KISS execution experiment.

V4 experiment:
- 30m candles decide the major/global trend.
- 5m candles decide when to execute entries and exits.
- Broker/symbol/direction selection is untouched.
- No MACD, no entry-indicator grid, no new prediction logic.
- RSI remains emergency protection only.

This file is intentionally separate from the existing tuner and backtest engine
so the experiment can be compared cleanly with the previous KISS result.
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
TRAIL_PCT = 0.015
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


def _confirm_5m(closes: Sequence[float], start: int, direction: str) -> bool:
    """Confirm a move with 2 of the next 3 completed 5m candles."""
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
    exit_reason: str
    max_favorable_pct: float
    max_adverse_pct: float
    entry_rsi: Optional[float]
    exit_rsi: Optional[float]


def run_kiss_30m_5m(
    trend_rows: Sequence[Dict[str, Any]],
    execution_rows: Sequence[Dict[str, Any]],
    symbol: str,
    direction: str,
) -> Dict[str, Any]:
    """30m trend decision + 5m execution backtest."""
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
    position = None
    peak = None
    trough = None
    max_fav = 0.0
    max_adv = 0.0
    pending = None
    event_index = 0
    transition_count = len(trend_events)

    for i, row in enumerate(execution_rows):
        ts = row.get("timestamp")

        # Apply every 30m trend transition that has become known by this 5m bar.
        current_event = None
        while event_index < len(trend_events) and trend_events[event_index]["time"] <= ts:
            current_event = trend_events[event_index]
            event_index += 1

        if current_event is not None:
            target = current_event["to"]
            if position is None and target in {"LONG", "SHORT"} and target == direction:
                pending = {
                    "kind": "ENTRY",
                    "target": target,
                    "from": current_event["from"],
                    "shape": current_event["shape"],
                    "start": i,
                }
            elif position is not None and target == ("SHORT" if position["direction"] == "LONG" else "LONG"):
                pending = {
                    "kind": "EXIT",
                    "target": target,
                    "start": i,
                    "reason": "TREND_CHANGE",
                }

        # 5m execution: after a major 30m transition, confirm 2 of 3 5m candles.
        if pending is not None and i >= pending["start"] + CONFIRM_BARS:
            if _confirm_5m(ex_closes, pending["start"], pending["target"]):
                if pending["kind"] == "ENTRY" and position is None:
                    entry_i = pending["start"] + CONFIRM_BARS
                    entry = ex_closes[entry_i]
                    position = {
                        "direction": direction,
                        "entry_i": entry_i,
                        "entry": entry,
                        "transition": f"{pending['from']}->{direction}",
                        "shape": pending.get("shape"),
                    }
                    peak = trough = entry
                    max_fav = max_adv = 0.0
                    pending = None
                elif pending["kind"] == "EXIT" and position is not None:
                    exit_i = pending["start"] + CONFIRM_BARS
                    entry = position["entry"]
                    exit_price = ex_closes[exit_i]
                    pnl = ((exit_price / entry) - 1.0) * 100.0 if position["direction"] == "LONG" else ((entry / exit_price) - 1.0) * 100.0
                    trades.append(KISS5Trade(
                        trade_id=f"KISS5-{len(trades)+1:05d}",
                        symbol=symbol,
                        direction=position["direction"],
                        entry_time=_ts(execution_rows[position["entry_i"]].get("timestamp")),
                        exit_time=_ts(execution_rows[exit_i].get("timestamp")),
                        entry_price=round(entry, 8),
                        exit_price=round(exit_price, 8),
                        pnl_pct=round(pnl, 6),
                        entry_transition=position["transition"],
                        transition_shape=position["shape"],
                        exit_reason=pending["reason"],
                        max_favorable_pct=round(max_fav, 6),
                        max_adverse_pct=round(max_adv, 6),
                        entry_rsi=rsis[position["entry_i"]],
                        exit_rsi=rsis[exit_i],
                    ))
                    position = None
                    peak = trough = None
                    pending = None

        if position is None:
            continue

        entry = position["entry"]
        price = ex_closes[i]
        if position["direction"] == "LONG":
            peak = max(peak, ex_highs[i])
            trough = min(trough, ex_lows[i])
            max_fav = max(max_fav, (peak / entry - 1.0) * 100.0)
            max_adv = min(max_adv, (ex_lows[i] / entry - 1.0) * 100.0)
            trail_hit = price < peak * (1.0 - TRAIL_PCT)
            emergency = rsis[i] is not None and rsis[i] < RSI_LONG_EMERGENCY
            opposite = "SHORT"
        else:
            trough = min(trough, ex_lows[i])
            peak = max(peak, ex_highs[i])
            max_fav = max(max_fav, (entry / trough - 1.0) * 100.0)
            max_adv = min(max_adv, (entry / ex_highs[i] - 1.0) * 100.0)
            trail_hit = price > trough * (1.0 + TRAIL_PCT)
            emergency = rsis[i] is not None and rsis[i] > RSI_SHORT_EMERGENCY
            opposite = "LONG"

        # A 5m trail starts the same 2-of-3 confirmation window; one noisy bar
        # therefore does not throw us out of the trade.
        if pending is None and trail_hit:
            pending = {"kind": "EXIT", "target": opposite, "start": i, "reason": "TRAILING_TREND_CHANGE"}

        if emergency:
            exit_price = price
            pnl = ((exit_price / entry) - 1.0) * 100.0 if position["direction"] == "LONG" else ((entry / exit_price) - 1.0) * 100.0
            trades.append(KISS5Trade(
                trade_id=f"KISS5-{len(trades)+1:05d}", symbol=symbol,
                direction=position["direction"],
                entry_time=_ts(execution_rows[position["entry_i"]].get("timestamp")),
                exit_time=_ts(row.get("timestamp")), entry_price=round(entry, 8),
                exit_price=round(exit_price, 8), pnl_pct=round(pnl, 6),
                entry_transition=position["transition"], transition_shape=position["shape"],
                exit_reason="RSI_EMERGENCY", max_favorable_pct=round(max_fav, 6),
                max_adverse_pct=round(max_adv, 6), entry_rsi=rsis[position["entry_i"]],
                exit_rsi=rsis[i],
            ))
            position = None
            pending = None

    if position is not None:
        i = len(execution_rows) - 1
        entry = position["entry"]
        exit_price = ex_closes[i]
        pnl = ((exit_price / entry) - 1.0) * 100.0 if position["direction"] == "LONG" else ((entry / exit_price) - 1.0) * 100.0
        trades.append(KISS5Trade(
            trade_id=f"KISS5-{len(trades)+1:05d}", symbol=symbol,
            direction=position["direction"], entry_time=_ts(execution_rows[position["entry_i"]].get("timestamp")),
            exit_time=_ts(execution_rows[i].get("timestamp")), entry_price=round(entry, 8),
            exit_price=round(exit_price, 8), pnl_pct=round(pnl, 6),
            entry_transition=position["transition"], transition_shape=position["shape"],
            exit_reason="END_OF_DATA", max_favorable_pct=round(max_fav, 6),
            max_adverse_pct=round(max_adv, 6), entry_rsi=rsis[position["entry_i"]], exit_rsi=rsis[i],
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
        "trades": payload,
        "total_pnl_pct": round(total, 6),
        "win_rate_pct": round((winners / len(payload) * 100.0) if payload else 0.0, 4),
        "avg_pnl_pct": round((total / len(payload)) if payload else 0.0, 6),
        "loser_count": sum(t["pnl_pct"] <= 0 for t in payload),
        "winner_count": winners,
        "transition_count": transition_count,
    }
