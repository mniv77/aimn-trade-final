#!/usr/bin/env python3
"""EXP72: audit actual V15/V16/V17 entries and post-exit continuation.

Research-only diagnostics, NOT an alternative trading backtest.
Future bars are used for evaluation only. No broker connection.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from engine.kiss_backtest import run_kiss_backtest


def audit(rows, mode="V15", horizon=12):
    rows = sorted(rows, key=lambda x: str(x["timestamp"]))
    result = run_kiss_backtest(
        rows, symbol="NVDA", direction="SHORT", timeframe="5m",
        entry_mode=mode, trailing_minus_pct=0.50,
        commission_pct=0.10, rsi_rescue_long=20, rsi_rescue_short=80,
    )
    by_time = {str(r["timestamp"]): i for i, r in enumerate(rows)}
    output = []
    for t in result["trades"]:
        ei = by_time.get(str(t["entry_time"]))
        xi = by_time.get(str(t["exit_time"]))
        if ei is None or xi is None:
            continue
        entry = float(t["entry_price"])
        exit_price = float(t["exit_price"])
        entry_day = str(rows[ei]["timestamp"])[:10]
        left = rows[max(0, ei - 30):ei + 1]
        peak = max(float(x["high"]) for x in left)
        # A short's peak-to-entry distance measures entry timing, not profitability.
        peak_distance = (peak / entry - 1) * 100
        held = rows[ei:xi + 1]
        lowest_while_held = min(float(x["low"]) for x in held)
        # Future evaluation is restricted to the same trading session.
        future = [r for r in rows[xi + 1:xi + 1 + horizon]
                  if str(r["timestamp"])[:10] == entry_day]
        best_future = min((float(x["low"]) for x in future), default=None)
        additional = ((exit_price / best_future - 1) * 100
                      if best_future is not None else None)
        output.append({
            "entry_time":t["entry_time"],"exit_time":t["exit_time"],
            "entry_price":entry,"exit_price":exit_price,
            "entry_shape":t.get("transition_shape"),"exit_reason":t["exit_reason"],
            "net_pct":t["net_pnl_pct"],
            "entry_distance_below_30bar_peak_pct":round(peak_distance,4),
            "best_intratrade_short_move_pct":round((entry/lowest_while_held-1)*100,4),
            "best_additional_short_move_after_exit_pct":round(additional,4) if additional is not None else None,
            "future_candles_evaluated":len(future),
            "chart_window_start":str(rows[max(0,ei-30)]["timestamp"]),
            "chart_window_end":str(rows[min(len(rows)-1,xi+horizon)]["timestamp"]),
        })
    future_valid = [x for x in output if x["best_additional_short_move_after_exit_pct"] is not None]
    premature = [x for x in future_valid if x["best_additional_short_move_after_exit_pct"] > 0.30]
    summary = {
        "mode":mode,"trades":len(output),
        "wins":sum(x["net_pct"]>0 for x in output),
        "net_pct_sum":round(sum(x["net_pct"] for x in output),4),
        "exit_reasons":dict(Counter(x["exit_reason"] for x in output)),
        "median_entry_distance_below_peak_pct":round(sorted(x["entry_distance_below_30bar_peak_pct"] for x in output)[len(output)//2],4) if output else None,
        "same_day_followups":len(future_valid),
        "post_exit_move_over_0_30pct":len(premature),
        "note":"Post-exit best lows are hindsight diagnostics, not realizable returns or proven bad exits. Entry fills and P&L are inherited from the existing KISS research engine."
    }
    return {"summary":summary,"trades":output}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--candles",default="kiss/visual_research/aimn_nvda_candles.json")
    parser.add_argument("--output",default="/tmp/exp72_peak_exit_audit.json")
    args=parser.parse_args()
    rows=json.loads(Path(args.candles).read_text(encoding="utf-8"))
    results={mode:audit(rows,mode) for mode in ("V15","V16","V17")}
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(results,indent=2),encoding="utf-8")
    for mode, r in results.items():
        print("EXP72",mode,json.dumps(r["summary"],sort_keys=True))
    print("Saved",p)


if __name__=="__main__":
    main()
