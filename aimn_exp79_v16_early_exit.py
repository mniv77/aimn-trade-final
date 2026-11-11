#!/usr/bin/env python3
"""EXP79: independent V16 SHORT entries with ST baseline vs causal profit protection.
Research only. Does not import or modify any live trading modules.
Signals are evaluated at candle close and normally filled at next candle open.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "kiss"))
from kiss_exp53_supertrend import calculate_supertrend
from exp74_kiss_hybrid_engine import (
    get_market_state, is_major_long_to_short_reversal, rsi_wilder
)

DATA = ROOT / "kiss/visual_research/aimn_nvda_candles.json"
OUT = ROOT / "kiss/results/exp79_v16_early_exit"
FEE = 0.10
STOP_PCT = 1.5
RSI_LIMIT = 80.0
# Require enough gross profit to cover both sides of commission.
PROFIT_ARM_PCT = 2 * FEE
VARIANTS = {"A_ST_BASELINE": None, "B_REBOUND_0_3": 0.3, "C_REBOUND_0_5": 0.5}

def finish(pos, i, price, reason, times):
    entry = pos["entry_price"]
    gross = (entry / price - 1) * 100
    return {
        "entry_time": pos["entry_time"], "exit_time": times[i],
        "entry_price": round(entry, 6), "exit_price": round(price, 6),
        "exit_reason": reason, "gross_pnl_pct": round(gross, 6),
        "net_pnl_pct": round(gross - 2 * FEE, 6),
        "best_close_short_pct": round((entry / pos["lowest_close"] - 1) * 100, 6),
        "bars_held": i - pos["entry_index"] + 1,
    }

def simulate(rows, st, rsi, market, threshold):
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    opens = [float(r["open"]) for r in rows]
    times = [str(r["timestamp"]) for r in rows]
    n = len(rows)
    pos = None
    pending = None
    trades = []
    candidate_count = 0
    skipped = Counter()
    signals = []
    # At each bar open, process signals from previous completed bar.
    for i in range(35, n):
        today = times[i][:10]
        yesterday = times[i - 1][:10]
        if today != yesterday:
            # The previous session's last close is the explicit liquidation price.
            # Do not process a pending action across sessions.
            if pos is not None:
                trades.append(finish(pos, i - 1, closes[i - 1], "SESSION_END", times))
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
                trades.append(finish(pos, i, opens[i], action, times))
                pos = None
                exited_at_open = True

        if pos is not None:
            stop_price = pos["entry_price"] * (1 + STOP_PCT / 100)
            if highs[i] >= stop_price:
                # Gaps worse than the stop are filled at the open.
                fill = max(stop_price, opens[i])
                trades.append(finish(pos, i, fill, "STOP_LOSS", times))
                pos = None
                pending = None
            else:
                pos["lowest_close"] = min(pos["lowest_close"], closes[i])
                if i + 1 < n and times[i + 1][:10] == today:
                    if st[i - 1] == "SHORT" and st[i] == "LONG":
                        pending = "ST_REVERSE"
                    elif rsi[i] is not None and rsi[i] >= RSI_LIMIT:
                        pending = "RSI_RESCUE"
                    elif threshold is not None:
                        gross = (pos["entry_price"] / pos["lowest_close"] - 1) * 100
                        rebound = (closes[i] / pos["lowest_close"] - 1) * 100
                        if gross > PROFIT_ARM_PCT and rebound >= threshold:
                            pending = "EARLY_REBOUND"

        signal = is_major_long_to_short_reversal(highs, lows, closes, market, i) is not None
        if signal:
            candidate_count += 1
            if pos is not None or exited_at_open or pending in ("ST_REVERSE", "RSI_RESCUE", "EARLY_REBOUND"):
                reason = "IN_TRADE_OR_EXITING"
            elif pending == "ENTER":
                reason = "ALREADY_QUEUED"
            elif st[i] != "LONG":
                reason = "ST_NOT_LONG"
            elif i + 1 >= n or times[i + 1][:10] != today:
                reason = "SESSION_BOUNDARY"
            else:
                reason = "ACCEPTED"
                pending = "ENTER"
            signals.append({"time": times[i], "decision": reason, "st": st[i]})
            if reason != "ACCEPTED":
                skipped[reason] += 1
        # All remaining positions liquidate at final available close.
    if pos is not None:
        trades.append(finish(pos, n - 1, closes[-1], "DATA_END", times))
    return trades, candidate_count, skipped, signals

def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: str(r["timestamp"]))
    if len(rows) < 100:
        raise ValueError("Insufficient candles")
    closes = [float(r["close"]) for r in rows]
    st = calculate_supertrend(rows, atr_period=10, multiplier=3.0)["st_trend"].tolist()
    rsi = rsi_wilder(closes)
    market = [get_market_state(closes, i) for i in range(len(rows))]
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, threshold in VARIANTS.items():
        trades, candidates, skipped, signals = simulate(rows, st, rsi, market, threshold)
        write_csv(OUT / (name.lower() + "_trades.csv"), trades,
            ["entry_time", "exit_time", "entry_price", "exit_price", "exit_reason",
             "gross_pnl_pct", "net_pnl_pct", "best_close_short_pct", "bars_held"])
        write_csv(OUT / (name.lower() + "_signals.csv"), signals, ["time", "decision", "st"])
        results[name] = {
            "candidates": candidates, "trades": len(trades),
            "winners": sum(t["net_pnl_pct"] > 0 for t in trades),
            "losers": sum(t["net_pnl_pct"] <= 0 for t in trades),
            "gross_pct_sum": round(sum(t["gross_pnl_pct"] for t in trades), 4),
            "net_pct_sum": round(sum(t["net_pnl_pct"] for t in trades), 4),
            "exit_reasons": dict(Counter(t["exit_reason"] for t in trades)),
            "rejected_signals": dict(skipped),
        }
    report = {
        "experiment": "EXP79", "symbol": "NVDA", "direction": "SHORT",
        "candles": len(rows), "fee_pct_per_side": FEE,
        "stop_pct": STOP_PCT, "rsi_rescue": RSI_LIMIT,
        "assumptions": "V16 close signal/next-open entry; ST(10,3) exit; next-open rebound exit; session-close liquidation; intrabar stop; commission on each completed trade.",
        "caution": "Small in-sample research; results are percentage-point sums, not compounded portfolio returns. This is a fresh baseline replay; compare to EXP77 and investigate any differences.",
        "results": results,
    }
    (OUT / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("EXP79 — V16 EARLY EXIT COMPARISON — RESEARCH ONLY")
    print(json.dumps(report, indent=2))
    print("Detailed reports:", OUT)

if __name__ == "__main__":
    main()
