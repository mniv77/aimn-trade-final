"""Controlled AutoTuner layered on top of the independent KISS backtest.

This module is intentionally research-only:
- uses the same KISS backtest engine for every combination
- uses one fixed candle dataset for the whole sweep
- does not write strategy parameters back to the database
- returns every tested combination, not only a "best" answer
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from engine.kiss_backtest import run_kiss_backtest

RSI_LONG_DEFAULT = 20.0
RSI_SHORT_DEFAULT = 80.0


def _clean_values(values: Iterable[float]) -> List[float]:
    out: List[float] = []
    for value in values:
        v = float(value)
        if v not in out:
            out.append(v)
    return out


def run_kiss_autotune(
    rows: Sequence[Dict[str, Any]],
    symbol: str,
    direction: str,
    rsi_long_values: Iterable[float],
    rsi_short_values: Iterable[float],
    trailing_minus_values: Iterable[float],
    commission_pct: float = 0.0,
) -> Dict[str, Any]:
    """Run a small research sweep and return ALL combinations."""
    long_values = _clean_values(rsi_long_values)
    short_values = _clean_values(rsi_short_values)
    trail_values = _clean_values(trailing_minus_values)

    if not long_values or not short_values or not trail_values:
        raise ValueError("AutoTuner requires at least one value for every parameter")

    direction = direction.upper()
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("Direction must be LONG or SHORT")

    # The selected direction is the only side whose RSI rescue can fire.
    # Keep the opposite-side value visible, but do not create redundant runs.
    if direction == "LONG":
        active_pairs = [(rsi_long, RSI_SHORT_DEFAULT) for rsi_long in long_values]
        active_parameter = "rsi_rescue_long"
    else:
        active_pairs = [(RSI_LONG_DEFAULT, rsi_short) for rsi_short in short_values]
        active_parameter = "rsi_rescue_short"

    combinations = len(active_pairs) * len(trail_values)
    if combinations > 100:
        raise ValueError("AutoTuner sweep is limited to 100 combinations per run")

    results: List[Dict[str, Any]] = []
    run_no = 0

    for rsi_long, rsi_short in active_pairs:
        for trailing_minus in trail_values:
                run_no += 1
                result = run_kiss_backtest(
                    rows,
                    symbol,
                    direction,
                    "5m",
                    rsi_rescue_long=rsi_long,
                    rsi_rescue_short=rsi_short,
                    trailing_minus_pct=trailing_minus,
                    commission_pct=commission_pct,
                )
                trades = result.get("trades", [])
                net_values = [float(t.get("net_pnl_pct", 0.0)) for t in trades]

                result_row = {
                    "run": run_no,
                    "rsi_rescue_long": float(rsi_long),
                    "rsi_rescue_short": float(rsi_short),
                    "trailing_minus_pct": float(trailing_minus),
                    "trades": len(trades),
                    "winners": int(result.get("winner_count", 0)),
                    "losers": int(result.get("loser_count", 0)),
                    "win_rate_pct": float(result.get("win_rate_pct", 0.0)),
                    "gross_pnl_pct": float(result.get("total_pnl_pct", 0.0)),
                    "commission_pct": float(result.get("total_commission_pct", 0.0)),
                    "net_pnl_pct": float(result.get("total_net_pnl_pct", 0.0)),
                    "avg_net_pnl_pct": round(
                        sum(net_values) / len(net_values), 6
                    ) if net_values else 0.0,
                    "best_net_pnl_pct": round(max(net_values), 6) if net_values else 0.0,
                    "worst_net_pnl_pct": round(min(net_values), 6) if net_values else 0.0,
                    "end_of_data_open_trade": any(
                        t.get("exit_reason") == "END_OF_DATA" for t in trades
                    ),
                }
                results.append(result_row)

    ranked = sorted(
        results,
        key=lambda r: (
            r["net_pnl_pct"],
            r["win_rate_pct"],
            -r["losers"],
        ),
        reverse=True,
    )

    return {
        "status": "success",
        "symbol": symbol,
        "direction": direction.upper(),
        "timeframe": "5m",
        "combinations": combinations,
        "results": results,
        "ranked": ranked,
        "active_parameter": active_parameter,
        "research_note": (
            "Ranking is descriptive only. The RSI Rescue parameter for the selected "
            "direction is tuned; the opposite-side RSI is held at its baseline value. "
            "No combination is automatically promoted to production and no "
            "strategy_params row is changed."
        ),
    }
