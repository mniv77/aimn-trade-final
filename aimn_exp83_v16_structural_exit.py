#!/usr/bin/env python3
"""EXP83 — V16 SHORT: structural exit transfer check, NVDA and AAPL.

READ-ONLY BACKTEST. No live orders or production engine changes.

The candidate exit requires a rebound from the lowest completed close, enough
prior SHORT profit to cover the round-trip commission, and (for D/E) a close
above the highest high of the previous six completed candles since entry.
All exit signals are evaluated at candle close, filled at next candle open.
Intrabar stops use stop-or-open (whichever is worse), as in EXP79.

Rules D and E were suggested by NVDA's EXP82 diagnostics: NVDA is IN-SAMPLE.
AAPL is a CROSS-SYMBOL check, not proof of out-of-sample predictive validity.
"""
import csv
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "kiss"))
import aimn_exp79_v16_early_exit as exp79
from kiss_exp53_supertrend import calculate_supertrend
from exp74_kiss_hybrid_engine import (
    get_market_state, is_major_long_to_short_reversal, rsi_wilder,
)

OUT = ROOT / "kiss/results/exp83_v16_structural_exit"
DATA = {
    "NVDA": ROOT / "kiss/visual_research/aimn_nvda_candles.json",
    "AAPL": ROOT / "kiss/visual_research/aimn_aapl_candles.json",
}
VARIANTS = {
    "A_ST_BASELINE": (None, False),
    "B_REBOUND_0_3": (0.3, False),
    "C_REBOUND_0_5": (0.5, False),
    "D_REBOUND_0_3_BREAK_HIGH": (0.3, True),
    "E_REBOUND_0_5_BREAK_HIGH": (0.5, True),
}

def simulate(rows, st, rsi, market, rebound_threshold, require_break):
    closes = [float(r["close"]) for r in rows]
    opens = [float(r["open"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    times = [str(r["timestamp"]) for r in rows]
    n = len(rows)
    pos = None
    pending = None
    trades = []
    candidates = 0
    rejected = Counter()
    blocked_by_structure = 0

    for i in range(35, n):
        day = times[i][:10]
        if day != times[i-1][:10]:
            # Match EXP79's planned session-end liquidation assumption.
            if pos is not None:
                trades.append(exp79.finish(pos, i-1, closes[i-1], "SESSION_END", times))
                pos = None
            pending = None

        exited_at_open = False
        if pending is not None:
            action = pending
            pending = None
            if action == "ENTER" and pos is None:
                pos = {
                    "entry_time": times[i], "entry_price": opens[i],
                    "entry_index": i, "lowest_close": opens[i],
                }
            elif action != "ENTER" and pos is not None:
                trades.append(exp79.finish(pos, i, opens[i], action, times))
                pos = None
                exited_at_open = True

        if pos is not None:
            stop_price = pos["entry_price"] * (1 + exp79.STOP_PCT / 100)
            if highs[i] >= stop_price:
                trades.append(exp79.finish(
                    pos, i, max(stop_price, opens[i]), "STOP_LOSS", times))
                pos = None
                pending = None
            else:
                pos["lowest_close"] = min(pos["lowest_close"], closes[i])
                if i + 1 < n and times[i+1][:10] == day:
                    if st[i-1] == "SHORT" and st[i] == "LONG":
                        pending = "ST_REVERSE"
                    elif rsi[i] is not None and rsi[i] >= exp79.RSI_LIMIT:
                        pending = "RSI_RESCUE"
                    elif rebound_threshold is not None:
                        gross = (pos["entry_price"] / pos["lowest_close"] - 1) * 100
                        rebound = (closes[i] / pos["lowest_close"] - 1) * 100
                        if gross > exp79.PROFIT_ARM_PCT and rebound >= rebound_threshold:
                            breaks_high = False
                            if i > pos["entry_index"]:
                                prior_high = max(highs[max(pos["entry_index"], i-6):i])
                                breaks_high = closes[i] > prior_high
                            if not require_break or breaks_high:
                                pending = "EARLY_REBOUND_BREAK" if require_break else "EARLY_REBOUND"
                            else:
                                blocked_by_structure += 1

        signal = is_major_long_to_short_reversal(
            highs, lows, closes, market, i) is not None
        if signal:
            candidates += 1
            reason = None
            if pos is not None or exited_at_open or pending in (
                "ST_REVERSE", "RSI_RESCUE", "EARLY_REBOUND", "EARLY_REBOUND_BREAK"
            ):
                reason = "IN_TRADE_OR_EXITING"
            elif pending == "ENTER":
                reason = "ALREADY_QUEUED"
            elif st[i] != "LONG":
                reason = "ST_NOT_LONG"
            elif i+1 >= n or times[i+1][:10] != day:
                reason = "SESSION_BOUNDARY"
            else:
                pending = "ENTER"
            if reason is not None:
                rejected[reason] += 1

    if pos is not None:
        trades.append(exp79.finish(pos, n-1, closes[-1], "DATA_END", times))
    return trades, candidates, dict(rejected), blocked_by_structure

def write_csv(path, trades):
    fields = [
        "entry_time", "exit_time", "entry_price", "exit_price", "exit_reason",
        "gross_pnl_pct", "net_pnl_pct", "best_close_short_pct", "bars_held"
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(trades)

def run_symbol(symbol, path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: str(r["timestamp"]))
    if len(rows) < 100:
        raise ValueError("Not enough candles for " + symbol)
    closes = [float(r["close"]) for r in rows]
    st = calculate_supertrend(rows, atr_period=10, multiplier=3.0)["st_trend"].tolist()
    rsi = rsi_wilder(closes)
    market = [get_market_state(closes, i) for i in range(len(rows))]
    result = {}
    entry_sets = {}
    for name, (threshold, require_break) in VARIANTS.items():
        trades, candidates, rejected, blocked = simulate(
            rows, st, rsi, market, threshold, require_break)
        entry_sets[name] = {trade["entry_time"] for trade in trades}
        write_csv(OUT / (symbol.lower() + "_" + name.lower() + ".csv"), trades)
        result[name] = {
            "candidates": candidates,
            "trades": len(trades),
            "winners": sum(t["net_pnl_pct"] > 0 for t in trades),
            "losers": sum(t["net_pnl_pct"] <= 0 for t in trades),
            "gross_pct_sum": round(sum(t["gross_pnl_pct"] for t in trades), 4),
            "net_pct_sum": round(sum(t["net_pnl_pct"] for t in trades), 4),
            "exit_reasons": dict(Counter(t["exit_reason"] for t in trades)),
            "rejected_signals": rejected,
            "rebound_events_blocked_by_structure": blocked,
        }
    base = result["A_ST_BASELINE"]["net_pct_sum"]
    for name in result:
        result[name]["net_delta_vs_st_pp"] = round(result[name]["net_pct_sum"] - base, 4)
        result[name]["entry_set_matches_baseline"] = (
            entry_sets[name] == entry_sets["A_ST_BASELINE"])
    return {"candles": len(rows), "results": result}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment": "EXP83",
        "research_only": True,
        "rule": "Completed-close rebound + prior six-candle high break (D/E)",
        "execution": "Signals on completed candle, next open fill; stop is intrabar; flat by session close.",
        "limitations": "NVDA rule motivated by its previous data; AAPL cross-symbol test. Small samples; transaction fees are 0.10% per side; P&L is sum of trade returns, not portfolio gain.",
        "symbols": {},
    }
    for symbol, path in DATA.items():
        report["symbols"][symbol] = run_symbol(symbol, path)
    (OUT / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("EXP83 — V16 STRUCTURAL EXIT TRANSFER CHECK — RESEARCH ONLY")
    print(json.dumps(report, indent=2))
    print("Detailed trades:", OUT)

if __name__ == "__main__":
    main()
